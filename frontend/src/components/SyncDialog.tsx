import { useState } from "react";
import { api } from "../api";
import { errorText } from "../format";
import { Modal } from "./ui";

export function SyncDialog({
  games,
  initial,
  onClose,
  onStarted,
}: {
  games: { key: string; name: string }[];
  /** Keys ticked when the dialog opens; every game when absent. */
  initial?: string[];
  onClose: () => void;
  onStarted: (runId: string) => void;
}) {
  const [selected, setSelected] = useState(
    initial?.length ? initial : games.map((g) => g.key),
  );
  const [days, setDays] = useState(180);
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const start = async () => {
    setSending(true);
    setError("");
    try {
      onStarted((await api.sync(selected, days)).run_id);
    } catch (e) {
      setError(errorText(e));
      setSending(false);
    }
  };
  return (
    <Modal
      title="同步数据"
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>
            取消
          </button>
          <button
            className="btn primary"
            disabled={!selected.length || sending}
            onClick={() => void start()}
          >
            开始同步
          </button>
        </>
      }
    >
      <div className="form">
        <p className="muted">
          重新抓取 Steam 评论、GitHub issue 和版本发布记录，通常需要 2–5
          分钟。同步期间仍显示当前数据，完成后自动切换。
        </p>
        <fieldset>
          <legend>游戏</legend>
          {games.map((p) => (
            <label className="check" key={p.key}>
              <input
                type="checkbox"
                checked={selected.includes(p.key)}
                onChange={(e) =>
                  setSelected(
                    e.target.checked
                      ? [...selected, p.key]
                      : selected.filter((k) => k !== p.key),
                  )
                }
              />
              {p.name}
            </label>
          ))}
        </fieldset>
        <label>
          评论时间范围
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={90}>最近 90 天</option>
            <option value={180}>最近 180 天</option>
            <option value={365}>最近 365 天</option>
          </select>
        </label>
        <p className="muted">
          每款游戏最多抓取 6,000 条评论和 4 页
          issue，达到上限时会标记为部分数据。
        </p>
        {error && <p className="error-text">{error}</p>}
      </div>
    </Modal>
  );
}
