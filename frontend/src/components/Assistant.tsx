import { Bot, ChevronRight, Plus, Send, Square, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { post, request } from "../api";
import { useData, type AssistantContext } from "../context";
import { errorText, pct } from "../format";
import { Spinner } from "./ui";

interface AgentStatus {
  available: boolean;
  logged_in: boolean;
  version: string | null;
  reason: string;
}
interface Conversation {
  id: string;
  title: string;
  created_at: string;
  status: string;
}
interface Turn {
  id: string;
  status:
    "queued" | "running" | "completed" | "rejected" | "failed" | "cancelled";
  error: string | null;
  request: {
    message: string;
    scope: AssistantContext["scope"];
    release_id?: string;
    category?: string;
    evidence_ids?: string[];
  };
  packet: {
    facts: Record<string, unknown>;
    tool_results: {
      index: number;
      sql: string;
      request: { tool: string };
      result: unknown;
    }[];
  };
  events: { at: string; message: string }[];
  answer: null | {
    summary: string;
    limitations: string[];
    next_actions: string[];
    claims: {
      text: string;
      status: "supported" | "hypothesis" | "insufficient";
      fact_ids: string[];
      evidence_ids: string[];
    }[];
  };
  verification: null | {
    status: string;
    errors: string[];
    checked_metrics: number;
    checked_citations: number;
  };
}

const CLAIM: Record<string, string> = {
  supported: "有数据支持",
  hypothesis: "待验证",
  insufficient: "证据不足",
};
const STATE: Record<string, string> = {
  queued: "排队中",
  running: "分析中",
  completed: "已完成",
  rejected: "未通过核验",
  failed: "失败",
  cancelled: "已取消",
};
const active = (t: Turn) => t.status === "queued" || t.status === "running";

const SUGGESTIONS: Record<AssistantContext["scope"], string[]> = {
  overview: [
    "最近玩家主要在抱怨什么？按问题类型列出，并引用原文。",
    "新玩家（游玩 2 小时以内）为什么更容易给差评？",
    "不同语言的玩家评价有什么差异？",
  ],
  monitor: ["最近 30 天的口碑变化是真实的吗？考虑样本量和语言构成。"],
  release: [
    "这个版本发布后玩家反馈有什么变化？哪些结论站得住？",
    "这个版本前后，玩家抱怨的问题类型有变化吗？",
  ],
  category: [
    "总结这类问题的主要表现，给出可以复现和排查的线索。",
    "这类问题集中在哪些语言或游玩时长的玩家？",
  ],
  evidence: ["这些反馈描述的是同一个问题吗？给出排查步骤。"],
};

/** Plain name for a computed number the assistant cited, e.g. "release.x.after.rate". */
function factName(id: string) {
  const field = id.split(".").at(-1) || id;
  const names: Record<string, string> = {
    n: "评论数",
    negative: "不推荐数",
    rate: "不推荐率",
    delta: "变化",
    ci_low: "区间下限",
    ci_high: "区间上限",
    total: "合计",
    mentions: "提及数",
    review_mentions: "评论提及数",
    negative_reviews: "不推荐评论提及数",
    github_mentions: "issue 提及数",
    open_issues: "未关闭 issue",
  };
  const prefix = id.includes(".before.")
    ? "前期"
    : id.includes(".after.")
      ? "后期"
      : "";
  return prefix + (names[field] || field);
}

function factValue(id: string, value: unknown) {
  if (typeof value === "number" && /(rate|delta|ci_low|ci_high)$/.test(id))
    return pct(value);
  return typeof value === "number"
    ? value.toLocaleString("zh-CN")
    : String(value);
}

export function Assistant({
  context,
  onContext,
  onClose,
}: {
  context: AssistantContext;
  onContext: (c: AssistantContext) => void;
  onClose: () => void;
}) {
  const app = useData();
  const { report, product } = app;
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversation, setConversation] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [message, setMessage] = useState(context.question || "");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const running = turns.some(active);
  const busy = submitting || running;

  const refreshConversations = useCallback(async () => {
    const params = new URLSearchParams({
      run_id: report.run_id,
      product: product.key,
    });
    setConversations(
      await request<Conversation[]>("/agent/conversations?" + params),
    );
  }, [report.run_id, product.key]);

  useEffect(() => {
    void request<AgentStatus>("/agent/status").then(setStatus, (e) =>
      setError(errorText(e)),
    );
    void refreshConversations().catch((e) => setError(errorText(e)));
  }, [refreshConversations]);
  useEffect(() => setMessage(context.question || ""), [context]);
  useEffect(() => {
    if (!conversation) {
      setTurns([]);
      return;
    }
    let alive = true;
    const read = () =>
      request<Turn[]>("/agent/conversations/" + conversation).then(
        (data) => alive && setTurns(data),
        (e) => alive && setError(errorText(e)),
      );
    void read();
    const timer = running ? window.setInterval(read, 1500) : undefined;
    return () => {
      alive = false;
      if (timer) window.clearInterval(timer);
    };
  }, [conversation, running]);
  useEffect(() => {
    if (conversation && !running)
      void refreshConversations().catch(() => undefined);
  }, [conversation, running, refreshConversations]);
  useEffect(
    () => bottom.current?.scrollIntoView({ block: "end" }),
    [turns.length, running],
  );

  const send = async () => {
    if (!message.trim() || busy) return;
    setSubmitting(true);
    setError("");
    try {
      const response = await post<{ conversation_id: string }>("/agent/turns", {
        run_id: report.run_id,
        product: product.key,
        message,
        conversation_id: conversation || null,
        scope: context.scope,
        release_id: context.release_id || null,
        category: context.category || null,
        evidence_ids: context.evidence_ids || [],
        effort: "medium",
      });
      setConversation(response.conversation_id);
      setTurns(
        await request<Turn[]>(
          "/agent/conversations/" + response.conversation_id,
        ),
      );
      setMessage("");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setSubmitting(false);
    }
  };

  const openConversation = async (id: string) => {
    setConversation(id);
    setError("");
    if (!id) return;
    try {
      const history = await request<Turn[]>("/agent/conversations/" + id);
      const last = history.at(-1)?.request;
      if (last) {
        const tag = product.release_studies.find(
          (s) => s.release_id === last.release_id,
        )?.tag;
        onContext({
          scope: last.scope,
          release_id: last.release_id || undefined,
          category: last.category || undefined,
          evidence_ids: last.evidence_ids || [],
          label: tag
            ? `版本 ${tag}`
            : last.evidence_ids?.length
              ? `${last.evidence_ids.length} 条反馈`
              : "历史对话",
        });
      }
      setTurns(history);
    } catch (e) {
      setError(errorText(e));
    }
  };

  const ready = status?.available && status.logged_in;
  return (
    <aside className="assistant" aria-label="AI 助手">
      <header className="assistant-head">
        <div>
          <h2>
            <Bot size={16} /> AI 助手
          </h2>
          <p>
            {product.name} · {context.label}
          </p>
        </div>
        <button
          className="icon-button"
          aria-label="关闭 AI 助手"
          onClick={onClose}
        >
          <X size={16} />
        </button>
      </header>

      <div className="assistant-bar">
        <select
          value={conversation}
          onChange={(e) => void openConversation(e.target.value)}
          disabled={busy}
          aria-label="历史对话"
        >
          <option value="">新对话</option>
          {conversations.map((c) => (
            <option key={c.id} value={c.id}>
              {c.created_at.slice(5, 16).replace("T", " ")} {c.title}
            </option>
          ))}
        </select>
        <button
          className="btn small"
          disabled={busy || !conversation}
          onClick={() => void openConversation("")}
        >
          <Plus size={13} />
          新对话
        </button>
      </div>

      <div className="assistant-messages" aria-live="polite">
        {status && !ready && (
          <div className="assistant-offline">
            <b>本机 AI 助手不可用</b>
            <p>{status.reason}</p>
          </div>
        )}
        {!turns.length && (
          <div className="assistant-welcome">
            <p>
              助手只读取当前数据快照，回答里的数字和引用会自动核对。可以这样问：
            </p>
            {SUGGESTIONS[context.scope].map((q) => (
              <button key={q} onClick={() => setMessage(q)}>
                {q}
                <ChevronRight size={14} />
              </button>
            ))}
          </div>
        )}
        {turns.map((t) => (
          <div className="turn" key={t.id}>
            <div className="turn-question">{t.request.message}</div>
            <div className="turn-answer">
              {active(t) && (
                <Spinner label={t.events.at(-1)?.message || "正在分析…"} />
              )}
              {t.error && <p className="error-text">{t.error}</p>}
              {!active(t) && !t.answer && !t.error && (
                <p className="muted">{STATE[t.status]}</p>
              )}
              {t.answer && (
                <>
                  <p className="turn-summary">{t.answer.summary}</p>
                  {t.answer.claims.length > 0 && (
                    <ul className="claims">
                      {t.answer.claims.map((c, i) => (
                        <li key={i}>
                          <span className={`claim-status ${c.status}`}>
                            {CLAIM[c.status]}
                          </span>
                          <p>{c.text}</p>
                          {(c.evidence_ids.length > 0 ||
                            c.fact_ids.length > 0) && (
                            <div className="refs">
                              {c.evidence_ids.map((id, j) => (
                                <button
                                  key={id}
                                  onClick={() => app.showEvidence(id)}
                                >
                                  原文 {j + 1}
                                </button>
                              ))}
                              {c.fact_ids.slice(0, 6).map((id) => (
                                <span key={id} className="ref-fact" title={id}>
                                  {factName(id)}{" "}
                                  {factValue(id, t.packet.facts[id])}
                                </span>
                              ))}
                            </div>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                  {t.answer.next_actions.length > 0 && (
                    <div className="turn-section">
                      <b>建议下一步</b>
                      <ul>
                        {t.answer.next_actions.map((a, i) => (
                          <li key={i}>{a}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {t.answer.limitations.length > 0 && (
                    <details className="turn-section">
                      <summary>
                        数据局限（{t.answer.limitations.length}）
                      </summary>
                      <ul>
                        {t.answer.limitations.map((a, i) => (
                          <li key={i}>{a}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                </>
              )}
              {t.verification && (
                <p className={`verification ${t.verification.status}`}>
                  {t.verification.status === "passed"
                    ? `已核对 ${t.verification.checked_metrics} 个数字、${t.verification.checked_citations} 处引用`
                    : "核对未通过：" + t.verification.errors.join("；")}
                </p>
              )}
              {t.packet.tool_results.length > 0 && (
                <details className="turn-section">
                  <summary>
                    查询过程（{t.packet.tool_results.length} 次）
                  </summary>
                  {t.packet.tool_results.map((q) => (
                    <pre key={q.index}>{q.sql}</pre>
                  ))}
                </details>
              )}
              {active(t) && (
                <button
                  className="btn small"
                  onClick={() =>
                    void post("/agent/turns/" + t.id + "/cancel").catch((e) =>
                      setError(errorText(e)),
                    )
                  }
                >
                  <Square size={12} />
                  停止
                </button>
              )}
            </div>
          </div>
        ))}
        <div ref={bottom} />
      </div>

      <form
        className="assistant-composer"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        {error && <p className="error-text">{error}</p>}
        <textarea
          aria-label="输入问题"
          placeholder="问一个关于当前数据的问题…"
          rows={3}
          maxLength={4000}
          value={message}
          disabled={busy}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) void send();
          }}
        />
        <div className="composer-foot">
          <small>Ctrl + Enter 发送 · 只读，不会修改数据</small>
          <button
            className="btn primary small"
            disabled={busy || !message.trim() || !ready}
          >
            <Send size={13} />
            发送
          </button>
        </div>
      </form>
    </aside>
  );
}
