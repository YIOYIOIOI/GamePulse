"""Team roles, workspace isolation, task leases and backups. Identities here are test fixtures."""

from __future__ import annotations

import copy
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from test_quality_workflow import populated as populated

from src.quality.access import Access
from src.quality.api import create_app
from src.quality.operations import Operations
from src.quality.store import ConflictError, Store


def test_leases_survive_other_worker_recovery_then_expire(populated):
    store, rid = populated
    op = Operations(store)
    owner = op.acquire("collection", "preparing", ttl=60)
    running = store.new_run({"products": ["mindustry"]}, ("collection", owner))
    other = Store(store.root)
    other.recover_interrupted()
    assert other.run(running)["status"] == "queued"
    with pytest.raises(ConflictError):
        Operations(other).acquire("collection", "competing")
    with store.connect() as conn:
        conn.execute("UPDATE task_leases SET expires_at=0 WHERE resource='collection'")
    other.recover_interrupted()
    assert other.run(running)["status"] == "failed"
    assert store.latest()["id"] == rid


def test_backup_restore_roundtrip_and_hash_failure(populated):
    store, rid = populated
    op = Operations(store)
    backup = op.backup()
    assert [b["id"] for b in op.backups()] == [backup["id"]]
    result = op.restore_drill(backup["id"])
    assert result["status"] == "passed" and result["original_untouched"]
    assert result["fingerprint"] == store.run(rid)["fingerprint"]
    restored = Store(result["restored_to"])
    for page in restored.pages(rid):
        restored.read_raw(page["path"], page["sha256"])
    assert restored.latest()["fingerprint"] == store.latest()["fingerprint"]
    with pytest.raises(ValueError):
        op.restore_drill("../escape")
    # Corrupt only a backup created by this test, never the original raw page.
    archive = Path(backup["path"])
    with zipfile.ZipFile(archive) as z:
        files = {name: z.read(name) for name in z.namelist()}
    raw = next(name for name in files if name.startswith("raw/"))
    files[raw] += b" "
    with zipfile.ZipFile(archive, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    with pytest.raises(ValueError, match="校验不通过"):
        op.restore_drill(backup["id"])
    assert store.latest()["fingerprint"] == restored.latest()["fingerprint"]


def test_expired_worker_cannot_publish_over_successful_snapshot(populated):
    store, rid = populated
    operations = Operations(store)
    owner = operations.acquire("collection", "preparing")
    new_run = store.new_run({"products": ["mindustry"]}, ("collection", owner))
    operations.release("collection", owner)
    operations.acquire("collection", "replacement-worker")
    original = store.run(rid)
    with pytest.raises(ConflictError, match="拒绝旧进程"):
        store.complete(new_run, original["report"], original["fingerprint"])
    assert store.latest()["id"] == rid


def headers(access, name, role, workspace):
    row = access.create(name, role, workspace)
    # Isolated fixture token is consumed internally, never printed.
    return {
        "Authorization": "Bearer " + Path(row["token_file"]).read_text(),
        "X-Workspace-ID": workspace,
    }, row


def test_team_roles_tenant_boundaries_and_revocation(populated):
    store, rid = populated
    app = create_app(store, serve_frontend=False, team=True)
    access = app.state.access
    viewer, v = headers(access, "fixture viewer", "viewer", "main")
    analyst, _ = headers(access, "fixture analyst", "analyst", "main")
    reviewer, _ = headers(access, "fixture reviewer", "reviewer", "main")
    owner, _ = headers(access, "fixture owner", "owner", "main")
    foreign, f = headers(access, "fixture foreign", "owner", "team_b")
    eid = store.query("SELECT id FROM evidence WHERE run_id=? LIMIT 1", (rid,))[0]["id"]
    item = {"run_id": rid, "product": "mindustry", "title": "权限验收测试事项", "evidence_ids": [eid]}
    with TestClient(app) as client:
        assert client.get("/api/quality/snapshot").status_code == 401
        assert client.get("/api/quality/snapshot", headers=viewer).status_code == 200
        assert client.post("/api/quality/triage", headers=viewer, json=item).status_code == 403
        created = client.post("/api/quality/triage", headers=analyst, json=item)
        assert created.status_code == 201
        tid = created.json()["id"]
        update = {"revision": 1, "status": "investigating", "owner": "测试负责人", "note": "开始核对"}
        assert (
            client.patch(f"/api/quality/triage/{tid}", headers=analyst, json=update).status_code
            == 200
        )
        confirm = {**update, "revision": 2, "status": "confirmed", "note": "复核通过"}
        assert (
            client.patch(f"/api/quality/triage/{tid}", headers=analyst, json=confirm).status_code
            == 403
        )
        confirmed = client.patch(f"/api/quality/triage/{tid}", headers=reviewer, json=confirm)
        assert confirmed.status_code == 200
        assert [h["actor"] for h in confirmed.json()["history"]] == [
            "fixture analyst",
            "fixture analyst",
            "fixture reviewer",
        ]
        assert [h["status"] for h in confirmed.json()["history"]] == [
            "pending",
            "investigating",
            "confirmed",
        ]
        # Another workspace neither sees nor edits this follow-up.
        assert client.get("/api/quality/triage", headers=foreign).json() == []
        assert (
            client.patch(f"/api/quality/triage/{tid}", headers=foreign, json=confirm).status_code
            == 403
        )
        assert client.post("/api/quality/backups", headers=analyst).status_code == 403
        assert client.get("/api/quality/backups", headers=foreign).status_code == 403
        assert client.get("/api/quality/backups", headers=owner).status_code == 200
        assert client.get("/api/quality/access/identities", headers=analyst).status_code == 403
        member = client.post(
            "/api/quality/access/identities",
            headers=owner,
            json={"name": "fixture member", "role": "analyst"},
        )
        assert member.status_code == 201 and member.json()["workspace"] == "main"
        assert (
            client.post(
                "/api/quality/access/identities",
                headers=owner,
                json={"name": "fixture member", "role": "collector"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/quality/access/identities/" + f["id"] + "/revoke", headers=owner
            ).status_code
            == 403
        )
        wrong = {**viewer, "X-Workspace-ID": "team_b"}
        assert client.get("/api/quality/snapshot", headers=wrong).status_code == 403
        access.revoke(v["id"])
        assert client.get("/api/quality/snapshot", headers=viewer).status_code == 403


@pytest.mark.parametrize("fault", ["expired", "audience", "issuer", "signature", "none"])
def test_oidc_signed_claim_validation_and_minimum_role(tmp_path, monkeypatch, fault):
    monkeypatch.setenv("GAMEPULSE_OIDC_ISSUER", "https://test-issuer.invalid")
    monkeypatch.setenv("GAMEPULSE_OIDC_AUDIENCE", "test-audience")
    access = Access(Store(tmp_path), True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    access.jwks = SimpleNamespace(
        get_signing_key_from_jwt=lambda _: SimpleNamespace(key=key.public_key())
    )
    claims = {
        "iss": access.issuer,
        "aud": access.audience,
        "sub": "test-subject",
        "iat": int(time.time()),
        "exp": int(time.time()) + 300,
        "role": "owner",
    }
    good = jwt.encode(claims, key, algorithm="RS256")
    assert access.principal("Bearer " + good, "main")["role"] == "viewer"
    bad = copy.deepcopy(claims)
    signer = key
    if fault == "expired":
        bad["exp"] = int(time.time()) - 1
    if fault == "audience":
        bad["aud"] = "wrong"
    if fault == "issuer":
        bad["iss"] = "https://wrong.invalid"
    if fault == "signature":
        signer = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = (
        jwt.encode(bad, signer, algorithm="RS256")
        if fault != "none"
        else jwt.encode(bad, None, algorithm="none")
    )
    with pytest.raises(PermissionError):
        access.principal("Bearer " + token, "main")
