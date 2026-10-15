import {
  Bot,
  ChevronLeft,
  ChevronRight,
  ListPlus,
  Search,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { excerpt, Highlighted } from "../components/EvidenceText";
import { Badge, Card, Empty, PageHeader, Spinner } from "../components/ui";
import { useData } from "../context";
import { CATEGORIES, day, errorText, language, num } from "../format";
import { href, navigate } from "../route";
import type { EvidencePage } from "../types";

const PAGE_SIZE = 30;
const MAX_FOLLOW_UP = 30;
const MAX_ASSISTANT = 16;

export function Feedback({ params }: { params: URLSearchParams }) {
  const {
    report,
    product: p,
    can,
    showEvidence,
    createFollowUp,
    openAssistant,
    notify,
  } = useData();
  const filters = {
    source: params.get("source") || "",
    category: params.get("category") || "",
    recommended: params.get("recommended") || "",
    language: params.get("language") || "",
    q: params.get("q") || "",
  };
  const offset = Number(params.get("offset") || 0);
  const [search, setSearch] = useState(filters.q);
  const [page, setPage] = useState<EvidencePage | null>(null);
  const [pending, setPending] = useState(true);
  const [selected, setSelected] = useState<string[]>([]);

  const setFilter = (
    changes: Partial<typeof filters> & { offset?: string },
  ) => {
    const next = { ...filters, offset: "", ...changes };
    if (next.source === "github_issues") next.recommended = "";
    navigate(href("feedback", undefined, next), true);
  };

  useEffect(() => setSearch(filters.q), [filters.q]);
  useEffect(() => setSelected([]), [p.key, report.run_id]);
  const key = JSON.stringify([p.key, report.run_id, filters, offset]);
  useEffect(() => {
    let alive = true;
    setPending(true);
    api
      .evidence({
        product: p.key,
        runId: report.run_id,
        source: filters.source,
        category: filters.category,
        language: filters.language,
        recommended: filters.recommended,
        search: filters.q,
        limit: PAGE_SIZE,
        offset,
      })
      .then((data) => alive && setPage(data))
      .catch((e) => alive && notify(errorText(e), "error"))
      .finally(() => alive && setPending(false));
    return () => {
      alive = false;
    };
    // `key` serializes the product, snapshot, filters and offset read above.
  }, [key]);

  const toggle = (id: string) =>
    setSelected((list) =>
      list.includes(id)
        ? list.filter((x) => x !== id)
        : [...list, id].slice(0, MAX_FOLLOW_UP),
    );
  const filtered = Object.values(filters).some(Boolean);
  const total = page?.total ?? 0;

  return (
    <>
      <PageHeader
        title="反馈"
        description="Steam 评论和 GitHub issue 原文。勾选后可以创建跟进，或交给 AI 助手分析。"
      />

      <div className="filters">
        <div className="segmented" role="group" aria-label="来源">
          {[
            ["", "全部"],
            ["steam", "Steam 评论"],
            ...(p.repo ? [["github_issues", "GitHub issue"]] : []),
          ].map(([value, label]) => (
            <button
              key={value}
              className={filters.source === value ? "active" : ""}
              onClick={() => setFilter({ source: value })}
            >
              {label}
            </button>
          ))}
        </div>
        <select
          aria-label="问题类型"
          value={filters.category}
          onChange={(e) => setFilter({ category: e.target.value })}
        >
          <option value="">全部问题类型</option>
          {p.categories.map((c) => (
            <option key={c.key} value={c.key}>
              {c.label}
            </option>
          ))}
        </select>
        {filters.source !== "github_issues" && (
          <select
            aria-label="推荐"
            value={filters.recommended}
            onChange={(e) => setFilter({ recommended: e.target.value })}
          >
            <option value="">推荐与不推荐</option>
            <option value="false">只看不推荐</option>
            <option value="true">只看推荐</option>
          </select>
        )}
        {filters.source !== "github_issues" && (
          <select
            aria-label="语言"
            value={filters.language}
            onChange={(e) => setFilter({ language: e.target.value })}
          >
            <option value="">全部语言</option>
            {p.languages.map((l) => (
              <option key={l.language} value={l.language}>
                {language(l.language)}（{num(l.n)}）
              </option>
            ))}
          </select>
        )}
        <form
          className="search"
          onSubmit={(e) => {
            e.preventDefault();
            setFilter({ q: search.trim() });
          }}
        >
          <Search size={14} />
          <input
            aria-label="搜索原文"
            placeholder="搜索原文，回车确认"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </form>
        {filtered && (
          <button
            className="link-button"
            onClick={() => navigate(href("feedback"), true)}
          >
            清除筛选
          </button>
        )}
      </div>

      {selected.length > 0 && (
        <div className="selection-bar">
          <b>已选 {selected.length} 条</b>
          {can.analyze && (
            <>
              <button
                className="btn small primary"
                onClick={() => createFollowUp(selected)}
              >
                <ListPlus size={13} />
                创建跟进
              </button>
              <button
                className="btn small"
                disabled={selected.length > MAX_ASSISTANT}
                title={
                  selected.length > MAX_ASSISTANT
                    ? `AI 一次最多分析 ${MAX_ASSISTANT} 条`
                    : undefined
                }
                onClick={() =>
                  openAssistant({
                    scope: "evidence",
                    evidence_ids: selected,
                    label: `${selected.length} 条反馈`,
                    question:
                      "这些反馈描述的是同一个问题吗？总结共同点，给出排查步骤，并引用原文。",
                  })
                }
              >
                <Bot size={13} />让 AI 分析
              </button>
            </>
          )}
          <button className="btn small ghost" onClick={() => setSelected([])}>
            <X size={13} />
            取消选择
          </button>
          {selected.length >= MAX_FOLLOW_UP && (
            <span className="muted">
              一条跟进最多关联 {MAX_FOLLOW_UP} 条反馈
            </span>
          )}
        </div>
      )}

      <Card flush>
        {pending && !page ? (
          <div className="list-loading">
            <Spinner label="正在读取" />
          </div>
        ) : !page?.rows.length ? (
          <Empty title="没有符合条件的反馈">
            换一个问题类型、语言或关键词试试。
          </Empty>
        ) : (
          <ul className={`evidence-list ${pending ? "is-pending" : ""}`}>
            {page.rows.map((e) => (
              <li
                key={e.id}
                className={selected.includes(e.id) ? "selected" : ""}
              >
                <input
                  type="checkbox"
                  aria-label="选择这条反馈"
                  checked={selected.includes(e.id)}
                  disabled={
                    !selected.includes(e.id) && selected.length >= MAX_FOLLOW_UP
                  }
                  onChange={() => toggle(e.id)}
                />
                <button
                  className="evidence-row"
                  onClick={() => showEvidence(e.id)}
                >
                  <span className="evidence-meta">
                    {e.source === "steam" ? (
                      <Badge tone={e.recommended === 0 ? "bad" : "good"}>
                        {e.recommended === 0 ? "不推荐" : "推荐"}
                      </Badge>
                    ) : (
                      <Badge tone={e.state === "open" ? "warn" : "neutral"}>
                        {e.state === "open" ? "未关闭 issue" : "已关闭 issue"}
                      </Badge>
                    )}
                    <span>{day(e.created_at)}</span>
                    {e.source === "steam" && (
                      <span>{language(e.language)}</span>
                    )}
                    {e.source === "steam" &&
                      e.playtime_at_review_minutes != null && (
                        <span>
                          已玩{" "}
                          {num(
                            Math.max(
                              1,
                              Math.round(e.playtime_at_review_minutes / 60),
                            ),
                          )}{" "}
                          小时
                        </span>
                      )}
                    {e.categories?.map((c) => (
                      <span className="tag" key={c}>
                        {CATEGORIES[c] || c}
                      </span>
                    ))}
                  </span>
                  {e.source === "github_issues" && (
                    <span className="evidence-title">{e.title}</span>
                  )}
                  <span className="evidence-text">
                    <Highlighted
                      text={excerpt(e) || "（没有正文）"}
                      terms={filters.q ? [filters.q] : []}
                    />
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {page && page.total > 0 && (
          <footer className="pager">
            <span>
              第 {num(offset + 1)}–{num(Math.min(offset + PAGE_SIZE, total))}{" "}
              条，共 {num(total)} 条
            </span>
            <div>
              <button
                className="btn small"
                aria-label="上一页"
                disabled={offset === 0 || pending}
                onClick={() =>
                  setFilter({ offset: String(Math.max(0, offset - PAGE_SIZE)) })
                }
              >
                <ChevronLeft size={14} />
              </button>
              <button
                className="btn small"
                aria-label="下一页"
                disabled={offset + PAGE_SIZE >= total || pending}
                onClick={() =>
                  setFilter({ offset: String(offset + PAGE_SIZE) })
                }
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </footer>
        )}
      </Card>
    </>
  );
}
