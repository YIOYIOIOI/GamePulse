import { Bot, ListPlus } from "lucide-react";
import { excerpt, Highlighted } from "../components/EvidenceText";
import { Badge, Card, PageHeader } from "../components/ui";
import { useData } from "../context";
import { num, pct } from "../format";
import { href, navigate } from "../route";
import type { Category } from "../types";

export function Issues({ selected }: { selected?: string }) {
  const { product: p } = useData();
  const rows = [...p.categories].sort(
    (a, b) =>
      b.trend.recent.mentions - a.trend.recent.mentions ||
      b.negative_reviews - a.negative_reviews,
  );
  const current = rows.find((c) => c.key === selected) || rows[0];

  return (
    <>
      <PageHeader
        title="问题"
        description="玩家评论和 GitHub issue 里提到的问题，按类型归类。点击一类问题查看原文。"
      />
      <div className="grid issues-layout">
        <Card title="问题类型" flush>
          <table className="table selectable">
            <thead>
              <tr>
                <th>类型</th>
                <th className="num">近 30 天</th>
                <th className="num">180 天</th>
                <th className="num">不推荐</th>
                <th className="num">issue</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => {
                const change =
                  c.trend.recent.mentions - c.trend.previous.mentions;
                return (
                  <tr
                    key={c.key}
                    className={c.key === current?.key ? "selected" : ""}
                    onClick={() => navigate(href("issues", c.key), true)}
                  >
                    <td>{c.label}</td>
                    <td className="num">
                      {num(c.trend.recent.mentions)}
                      {change !== 0 && (
                        <small
                          className={`delta ${change > 0 ? "up" : "down"}`}
                        >
                          {change > 0 ? " ↑" : " ↓"}
                          {Math.abs(change)}
                        </small>
                      )}
                    </td>
                    <td className="num">{num(c.review_mentions)}</td>
                    <td className="num">{num(c.negative_reviews)}</td>
                    <td className="num">
                      {p.repo ? num(c.github_mentions) : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="table-note">
            「近 30 天」「180 天」「不推荐」统计 Steam 评论；「issue」统计
            GitHub issue。箭头为与之前 30 天相比的变化。
          </p>
        </Card>
        {current && <CategoryDetail category={current} />}
      </div>
    </>
  );
}

function CategoryDetail({ category: c }: { category: Category }) {
  const {
    product: p,
    can,
    openAssistant,
    createFollowUp,
    showEvidence,
  } = useData();
  const share = p.recommendation.negative
    ? c.negative_reviews / p.recommendation.negative
    : null;
  const terms = c.examples.flatMap((e) => e.cues?.map((x) => x.text) ?? []);
  return (
    <Card
      title={c.label}
      actions={
        <>
          <a
            className="btn small"
            href={href("feedback", undefined, { category: c.key })}
          >
            查看全部反馈
          </a>
          {can.analyze && (
            <button
              className="btn small"
              onClick={() =>
                openAssistant({
                  scope: "category",
                  category: c.key,
                  label: c.label,
                  question: `总结「${c.label}」这类问题的主要表现，给出可以复现和排查的线索，并引用原文。`,
                })
              }
            >
              <Bot size={13} />
              AI 总结
            </button>
          )}
        </>
      }
    >
      <div className="mini-stats">
        <div>
          <small>近 30 天评论提及</small>
          <b>{num(c.trend.recent.mentions)}</b>
          <span>之前 30 天 {num(c.trend.previous.mentions)}</span>
        </div>
        <div>
          <small>不推荐评论中提及</small>
          <b>{num(c.negative_reviews)}</b>
          <span>占全部不推荐评论的 {pct(share)}</span>
        </div>
        <div>
          <small>GitHub issue 提及</small>
          <b>{p.repo ? num(c.github_mentions) : "—"}</b>
          <span>
            {p.repo
              ? `其中 ${num(c.open_issues)} 条未关闭`
              : "没有关联 GitHub 仓库"}
          </span>
        </div>
      </div>

      <div className="section-head">
        <h3>代表性反馈</h3>
        {can.analyze && c.examples.length > 0 && (
          <button
            className="btn small"
            onClick={() =>
              createFollowUp(
                c.examples.map((e) => e.id),
                c.label + "：",
              )
            }
          >
            <ListPlus size={13} />
            用这些反馈创建跟进
          </button>
        )}
      </div>
      {c.examples.length === 0 ? (
        <p className="muted">这段时间没有找到提到这类问题的评论或 issue。</p>
      ) : (
        <ul className="feedback-list">
          {c.examples.map((e) => (
            <li key={e.id}>
              <button
                className="feedback-item"
                onClick={() => showEvidence(e.id)}
              >
                <span className="feedback-meta">
                  {e.source === "steam" ? (
                    <Badge tone={e.recommended === 0 ? "bad" : "good"}>
                      {e.recommended === 0 ? "不推荐" : "推荐"}
                    </Badge>
                  ) : (
                    <Badge tone="info">GitHub</Badge>
                  )}
                  {e.source === "github_issues" && <b>{e.title}</b>}
                </span>
                <span className="feedback-text">
                  <Highlighted text={excerpt(e, 260)} terms={terms} />
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="table-note">
        归类方式：在评论和 issue
        正文中匹配这类问题的关键词，评论支持英文、中文和俄文（本游戏{" "}
        {num(p.quality.rules_language_covered)} /{" "}
        {num(p.quality.rule_denominator)}{" "}
        条评论可识别）。提及不代表问题已确认，请结合原文判断。
      </p>
    </Card>
  );
}
