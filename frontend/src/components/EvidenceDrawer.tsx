import { Bot, ExternalLink, ListPlus } from "lucide-react";
import { useEffect, useState } from "react";
import { api, download } from "../api";
import { useApp } from "../context";
import { CATEGORIES, dateTime, errorText, language, num } from "../format";
import type { EvidenceDetail } from "../types";
import { FullText } from "./EvidenceText";
import { Badge, Drawer, Spinner } from "./ui";

export function EvidenceDrawer({
  id,
  runId,
  onClose,
}: {
  id: string;
  runId: string;
  onClose: () => void;
}) {
  const app = useApp();
  const [detail, setDetail] = useState<EvidenceDetail | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    setDetail(null);
    api
      .evidenceDetail(id, runId)
      .then((d) => alive && setDetail(d))
      .catch((e) => alive && setError(errorText(e)));
    return () => {
      alive = false;
    };
  }, [id, runId]);

  const e = detail?.evidence;
  const steam = e?.source === "steam";
  const terms =
    detail?.mentions.flatMap((m) => m.cues.map((c) => c.text)) ?? [];
  const title = !e ? "反馈详情" : steam ? "Steam 玩家评论" : e.title;

  return (
    <Drawer
      title={title}
      subtitle={e && <Meta detail={detail!} />}
      onClose={onClose}
    >
      {error ? (
        <p className="error-text">{error}</p>
      ) : !detail || !e ? (
        <Spinner label="正在读取" />
      ) : (
        <>
          <div className="drawer-actions">
            <a
              className="btn"
              href={e.source_url}
              target="_blank"
              rel="noreferrer"
            >
              <ExternalLink size={14} />
              {steam ? "在 Steam 查看" : "在 GitHub 查看"}
            </a>
            {app.can.analyze && (
              <>
                <button
                  className="btn"
                  onClick={() => app.createFollowUp([e.id], undefined, runId)}
                >
                  <ListPlus size={14} />
                  创建跟进
                </button>
                <button
                  className="btn"
                  onClick={() =>
                    app.openAssistant({
                      scope: "evidence",
                      label: "1 条反馈",
                      evidence_ids: [e.id],
                      question:
                        "这条反馈描述了什么问题？区分玩家明确说的和推测的部分，并给出排查建议。",
                    })
                  }
                >
                  <Bot size={14} />让 AI 分析
                </button>
              </>
            )}
          </div>

          <FullText evidence={e} terms={terms} />

          {detail.mentions.length > 0 && (
            <div className="detail-block">
              <h3>识别到的问题类型</h3>
              <div className="tag-row">
                {detail.mentions.map((m) => (
                  <span className="tag" key={m.category}>
                    {CATEGORIES[m.category] || m.category}
                    <small>
                      {[...new Set(m.cues.map((c) => c.text.toLowerCase()))]
                        .slice(0, 4)
                        .join("、")}
                    </small>
                  </span>
                ))}
              </div>
            </div>
          )}

          <details className="detail-block source-block">
            <summary>数据来源</summary>
            <dl className="facts">
              <dt>抓取时间</dt>
              <dd>
                {dateTime(
                  detail.lineage.source_fetched_at || detail.lineage.fetched_at,
                )}
              </dd>
              <dt>原始请求</dt>
              <dd>
                <a
                  href={detail.lineage.request_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {new URL(detail.lineage.request_url).host}
                  <ExternalLink size={12} />
                </a>
              </dd>
              <dt>记录位置</dt>
              <dd>
                <code>{detail.lineage.json_pointer}</code>
              </dd>
              <dt>内容校验</dt>
              <dd>
                <code title={detail.lineage.sha256}>
                  SHA-256 {detail.lineage.sha256.slice(0, 16)}…
                </code>
              </dd>
            </dl>
            <button
              className="btn small"
              onClick={() =>
                void download(
                  "/pages/" + detail.lineage.page_id,
                  detail.lineage.page_id + ".json",
                ).catch((err) => app.notify(errorText(err), "error"))
              }
            >
              下载原始响应
            </button>
          </details>
        </>
      )}
    </Drawer>
  );
}

function Meta({ detail }: { detail: EvidenceDetail }) {
  const e = detail.evidence;
  if (e.source === "steam") {
    const minutes = e.playtime_at_review_minutes;
    return (
      <span className="meta-line">
        <Badge tone={e.recommended === 0 ? "bad" : "good"}>
          {e.recommended === 0 ? "不推荐" : "推荐"}
        </Badge>
        {dateTime(e.created_at)} · {language(e.language)}
        {minutes != null &&
          ` · 评论时已玩 ${minutes < 60 ? minutes + " 分钟" : num(Math.round(minutes / 60)) + " 小时"}`}
        {!!e.helpful_votes && ` · ${num(e.helpful_votes)} 人觉得有用`}
      </span>
    );
  }
  return (
    <span className="meta-line">
      <Badge tone={e.state === "open" ? "warn" : "neutral"}>
        {e.state === "open" ? "未关闭" : "已关闭"}
      </Badge>
      GitHub issue · {dateTime(e.created_at)}
      {e.labels?.length ? " · " + e.labels.join("、") : ""}
    </span>
  );
}
