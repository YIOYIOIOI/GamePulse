import { useEffect, useState } from "react";
import { api } from "../api";
import { useApp, useData } from "../context";
import { dateTime, errorText, NEXT_STATUS, relative, STATUS } from "../format";
import type { Evidence, FollowUp, FollowUpStatus } from "../types";
import { excerpt } from "./EvidenceText";
import { Drawer, Modal } from "./ui";

export function StatusBadge({ status }: { status: FollowUpStatus }) {
  return <span className={`status ${status}`}>{STATUS[status]}</span>;
}

export function CreateFollowUp({
  evidenceIds,
  title: suggested = "",
  runId,
  onClose,
  onCreated,
}: {
  evidenceIds: string[];
  title?: string;
  /** Snapshot the feedback was read from; the one on screen when absent. */
  runId?: string;
  onClose: () => void;
  onCreated: (item: FollowUp) => void;
}) {
  const { report, product } = useData();
  const [title, setTitle] = useState(suggested);
  const [owner, setOwner] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const submit = async () => {
    setSaving(true);
    setError("");
    try {
      onCreated(
        await api.createFollowUp({
          run_id: runId ?? report.run_id,
          product: product.key,
          title: title.trim(),
          evidence_ids: evidenceIds,
          owner: owner.trim(),
          note: note.trim(),
        }),
      );
    } catch (e) {
      setError(errorText(e));
      setSaving(false);
    }
  };
  return (
    <Modal
      title="创建跟进"
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>
            取消
          </button>
          <button
            className="btn primary"
            form="create-follow-up"
            disabled={saving || title.trim().length < 3}
          >
            创建
          </button>
        </>
      }
    >
      <form
        id="create-follow-up"
        className="form"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <p className="muted">
          {product.name} · 关联 {evidenceIds.length}{" "}
          条反馈。创建后状态为「待处理」。
        </p>
        <label>
          问题描述
          <input
            autoFocus
            required
            minLength={3}
            maxLength={180}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="例如：Steam Deck 上教程结束后闪退"
          />
        </label>
        <label>
          <span>
            负责人 <span className="optional">可稍后指定</span>
          </span>
          <input
            maxLength={80}
            value={owner}
            onChange={(e) => setOwner(e.target.value)}
          />
        </label>
        <label>
          <span>
            备注 <span className="optional">可选</span>
          </span>
          <textarea
            maxLength={3000}
            rows={3}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="这些反馈为什么值得跟进，需要先确认什么"
          />
        </label>
        {error && <p className="error-text">{error}</p>}
      </form>
    </Modal>
  );
}

export function FollowUpDrawer({
  id,
  onClose,
}: {
  id: string;
  onClose: () => void;
}) {
  const app = useApp();
  const item = app.followUps.find((f) => f.id === id);
  if (!item)
    return (
      <Drawer title="跟进" onClose={onClose}>
        <p className="muted">这条跟进不存在，或不属于当前工作区。</p>
      </Drawer>
    );
  const productName =
    app.games.find((g) => g.key === item.product)?.name || item.product;
  return (
    <Drawer
      title={item.title}
      subtitle={
        <span className="meta-line">
          <StatusBadge status={item.status} />
          {productName} · 负责人：{item.owner || "未指定"} · 创建于{" "}
          {dateTime(item.created_at)}
        </span>
      }
      onClose={onClose}
    >
      <LinkedFeedback item={item} />
      {app.can.analyze && <UpdateForm key={item.revision} item={item} />}
      <div className="detail-block">
        <h3>处理记录</h3>
        <ol className="timeline">
          {[...item.history].reverse().map((h, i) => (
            <li key={i}>
              <div className="timeline-head">
                <b>{h.actor || "未记录操作人"}</b>
                {h.action === "created"
                  ? " 创建了跟进"
                  : h.previous_status && h.previous_status !== h.status
                    ? ` 将状态从「${STATUS[h.previous_status]}」改为「${STATUS[h.status]}」`
                    : " 更新了进展"}
                <time title={dateTime(h.at)}>{relative(h.at)}</time>
              </div>
              {h.note && <p>{h.note}</p>}
            </li>
          ))}
        </ol>
      </div>
    </Drawer>
  );
}

const SHOWN_FEEDBACK = 8;

function LinkedFeedback({ item }: { item: FollowUp }) {
  const app = useApp();
  const [rows, setRows] = useState<Evidence[] | null>(null);
  const shown = item.evidence_ids.slice(0, SHOWN_FEEDBACK);
  const key = shown.join(",");
  useEffect(() => {
    let alive = true;
    Promise.all(
      key
        .split(",")
        .map((eid) =>
          api.evidenceDetail(eid, item.run_id).then((d) => d.evidence),
        ),
    )
      .then((list) => alive && setRows(list))
      .catch(() => alive && setRows([]));
    return () => {
      alive = false;
    };
  }, [key, item.run_id]);
  return (
    <div className="detail-block">
      <h3>关联反馈（{item.evidence_ids.length}）</h3>
      <ul className="linked-list">
        {(rows ?? []).map((e) => (
          <li key={e.id}>
            <button
              className="linked"
              onClick={() => app.showEvidence(e.id, item.run_id)}
            >
              <span className="source-label">
                {e.source === "steam" ? "Steam" : "GitHub"}
              </span>
              <span>
                {e.source === "github_issues" ? e.title : excerpt(e, 120)}
              </span>
            </button>
          </li>
        ))}
        {rows === null && <li className="muted">正在读取…</li>}
      </ul>
      {item.evidence_ids.length > shown.length && (
        <p className="muted">
          另有 {item.evidence_ids.length - shown.length} 条未列出
        </p>
      )}
    </div>
  );
}

function UpdateForm({ item }: { item: FollowUp }) {
  const app = useApp();
  const options = NEXT_STATUS[item.status].filter(
    (s) => app.can.review || (s !== "confirmed" && s !== "closed"),
  );
  const [status, setStatus] = useState<FollowUpStatus>(item.status);
  const [owner, setOwner] = useState(item.owner);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const needsOwner = status === "investigating" || status === "confirmed";
  const submit = async () => {
    setSaving(true);
    setError("");
    try {
      await api.updateFollowUp(item.id, {
        revision: item.revision,
        status,
        owner: owner.trim(),
        note: note.trim(),
      });
      await app.refreshFollowUps();
      app.notify("已保存");
    } catch (e) {
      setError(errorText(e));
      setSaving(false);
    }
  };
  return (
    <form
      className="detail-block form update-form"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <h3>更新进展</h3>
      <div className="form-row">
        <label>
          状态
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as FollowUpStatus)}
          >
            <option value={item.status}>{STATUS[item.status]}（当前）</option>
            {options.map((s) => (
              <option key={s} value={s}>
                {STATUS[s]}
              </option>
            ))}
          </select>
        </label>
        <label>
          负责人
          <input
            value={owner}
            maxLength={80}
            required={needsOwner}
            onChange={(e) => setOwner(e.target.value)}
          />
        </label>
      </div>
      <label>
        说明
        <textarea
          rows={3}
          required
          maxLength={3000}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="做了哪些检查、结论是什么、还缺什么"
        />
      </label>
      {!app.can.review && (
        <p className="muted">确认或关闭问题需要复核人或管理员。</p>
      )}
      {error && <p className="error-text">{error}</p>}
      <div>
        <button
          className="btn primary"
          disabled={saving || !note.trim() || (needsOwner && !owner.trim())}
        >
          保存
        </button>
      </div>
    </form>
  );
}
