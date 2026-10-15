"""Workspace-scoped capability identities; local mode stays loopback-only."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
import uuid
from urllib.parse import urlsplit

import jwt

from src.quality.contracts import iso, utc_now
from src.quality.store import Store

SCHEMA = """
CREATE TABLE IF NOT EXISTS access_identities(id TEXT PRIMARY KEY,name TEXT NOT NULL,workspace TEXT NOT NULL,role TEXT NOT NULL,token_hash TEXT UNIQUE NOT NULL,created_at TEXT NOT NULL,revoked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS security_audit(id INTEGER PRIMARY KEY,actor TEXT NOT NULL,workspace TEXT NOT NULL,at TEXT NOT NULL,action TEXT NOT NULL,object_id TEXT NOT NULL);
"""
# viewer reads; analyst also opens and updates follow-ups and asks the assistant; reviewer may also
# confirm or close follow-ups; owner may also sync data, manage members and create backups.
ROLES = {
    "owner": {"read", "analyze", "review", "admin"},
    "reviewer": {"read", "analyze", "review"},
    "analyst": {"read", "analyze"},
    "viewer": {"read"},
}


class Access:
    def __init__(self, store: Store, enabled=False):
        self.store, self.enabled = store, enabled
        with store.connect() as conn:
            conn.executescript(SCHEMA)
        self.issuer = os.environ.get("GAMEPULSE_OIDC_ISSUER")
        self.audience = os.environ.get("GAMEPULSE_OIDC_AUDIENCE")
        self.jwks = None
        if self.issuer:
            endpoint = os.environ.get(
                "GAMEPULSE_OIDC_JWKS_URL", self.issuer.rstrip("/") + "/.well-known/jwks.json"
            )
            if (
                urlsplit(self.issuer).scheme != "https"
                or urlsplit(endpoint).scheme != "https"
                or not self.audience
            ):
                raise ValueError("OIDC需要HTTPS issuer/JWKS地址及明确audience")
            self.jwks = jwt.PyJWKClient(endpoint, cache_jwk_set=True, lifespan=300, timeout=8)

    def create(self, name, role, workspace="main"):
        if (
            role not in ROLES
            or not re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", workspace)
            or not name.strip()
            or len(name) > 100
        ):
            raise ValueError("无效工作区、名称或角色")
        token = secrets.token_urlsafe(32)
        identity = uuid.uuid4().hex
        with self.store.connect() as conn:
            conn.execute(
                "INSERT INTO access_identities(id,name,workspace,role,token_hash,created_at,revoked) VALUES(?,?,?,?,?,?,0)",
                (
                    identity,
                    name,
                    workspace,
                    role,
                    hashlib.sha256(token.encode()).hexdigest(),
                    iso(utc_now()),
                ),
            )
        directory = self.store.root / "access"
        directory.mkdir(exist_ok=True)
        path = directory / (identity + ".token")
        path.write_text(token, encoding="utf-8")
        try:
            if os.name == "nt":
                account = os.environ.get("USERDOMAIN", "") + "\\" + os.environ.get("USERNAME", "")
                subprocess.run(
                    ["icacls", str(path), "/inheritance:r", "/grant:r", account + ":(F)"],
                    capture_output=True,
                    check=True,
                    timeout=8,
                )
            else:
                path.chmod(0o600)
        except (OSError, subprocess.SubprocessError) as exc:
            self.revoke(identity)
            path.unlink(missing_ok=True)
            raise ValueError("无法限制令牌文件权限，已撤销此身份") from exc
        return {
            "id": identity,
            "name": name,
            "workspace": workspace,
            "role": role,
            "token_file": str(path),
        }

    def principal(self, authorization: str | None, workspace: str | None):
        if not authorization:
            if self.enabled:
                raise PermissionError("团队模式需要工作区访问令牌")
            if workspace and workspace != "main":
                raise PermissionError("其他工作区需要访问令牌")
            return {
                "id": "local-operator",
                "name": "本地操作者",
                "workspace": "main",
                "role": "owner",
            }
        if not authorization.startswith("Bearer "):
            raise PermissionError("需要 Bearer 身份")
        token = authorization.removeprefix("Bearer ")
        rows = self.store.query(
            "SELECT id,name,workspace,role FROM access_identities WHERE token_hash=? AND revoked=0",
            (hashlib.sha256(token.encode()).hexdigest(),),
        )
        if not rows or workspace and rows[0]["workspace"] != workspace:
            if self.jwks:
                try:
                    key = self.jwks.get_signing_key_from_jwt(token).key
                    claims = jwt.decode(
                        token,
                        key,
                        algorithms=["RS256", "ES256"],
                        audience=self.audience,
                        issuer=self.issuer,
                        options={"require": ["exp", "iat", "iss", "aud", "sub"]},
                    )
                    target = os.environ.get("GAMEPULSE_OIDC_WORKSPACE", "main")
                    if workspace and workspace != target:
                        raise PermissionError("OIDC身份不属于此工作区")
                    mapping = json.loads(os.environ.get("GAMEPULSE_OIDC_GROUP_ROLES", "{}"))
                    groups = claims.get("groups", [])
                    if not isinstance(groups, list):
                        raise ValueError("OIDC groups必须为数组")
                    role = next(
                        (
                            r
                            for r in ("owner", "analyst", "reviewer", "viewer")
                            if any(mapping.get(g) == r for g in groups)
                        ),
                        "viewer",
                    )
                    return {
                        "id": "oidc:"
                        + hashlib.sha256((self.issuer + ":" + claims["sub"]).encode()).hexdigest(),
                        "name": "企业身份",
                        "workspace": target,
                        "role": role,
                    }
                except (jwt.PyJWTError, ValueError, TypeError) as exc:
                    raise PermissionError("OIDC签名、issuer、audience或有效期验证失败") from exc
            raise PermissionError("令牌无效、已撤销或工作区不匹配")
        return rows[0]

    def require(self, principal, permission):
        if permission not in ROLES[principal["role"]]:
            raise PermissionError("当前角色没有此操作权限")

    def audit(self, principal, action, object_id):
        with self.store.connect() as conn:
            conn.execute(
                "INSERT INTO security_audit(actor,workspace,at,action,object_id) VALUES(?,?,?,?,?)",
                (principal["id"], principal["workspace"], iso(utc_now()), action, object_id),
            )

    def list(self):
        return self.store.query(
            "SELECT id,name,workspace,role,created_at,revoked FROM access_identities ORDER BY created_at,rowid"
        )

    def revoke(self, identity):
        with self.store.connect() as conn:
            conn.execute("UPDATE access_identities SET revoked=1 WHERE id=?", (identity,))
