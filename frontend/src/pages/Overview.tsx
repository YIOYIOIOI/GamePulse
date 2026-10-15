import { Bot } from "lucide-react";
import type { ReactNode } from "react";
import { MIN_WEEKLY_REVIEWS, WeeklyTrend } from "../components/Charts";
import { StatusBadge } from "../components/FollowUpDialogs";
import { Badge, Card, Delta, Hint, PageHeader, Stat } from "../components/ui";
import { useData } from "../context";
import {
  day,
  language,
  monitorVerdict,
  num,
  pct,
  PLAYTIME,
  PLAYTIME_ORDER,
  pointsText,
  relative,
  verdict,
} from "../format";
import { href } from "../route";
import type { ProductReport } from "../types";

export function Overview() {
  const { report, product: p, followUps, can, openAssistant } = useData();
  const m = p.monitor;
  const reading = monitorVerdict(m);
  const open = followUps.filter(
    (f) => f.product === p.key && f.status !== "closed",
  );
  const issuesTotal = (p.issues.open || 0) + (p.issues.closed || 0);

  return (
    <>
      <PageHeader
        title="概览"
        description={`${p.name} · ${day(report.window_start)} 至 ${day(report.as_of)} 的 Steam 评论与 GitHub issue`}
      />

      <div className="stat-strip">
        <Stat label="Steam 评论" value={num(p.recommendation.n)}>
          近 30 天 {num(m.after.n)} 条
        </Stat>
        <Stat
          label="不推荐率"
          value={pct(p.recommendation.rate)}
          hint="给出「不推荐」的评论占全部评论的比例，来自玩家在 Steam 上的推荐标记。"
        >
          近 30 天 {pct(m.after.rate)}，较前 30 天{" "}
          <Delta value={m.delta} unit=" 个百分点" />
        </Stat>
        <Stat
          label="未关闭的 GitHub issue"
          value={p.repo ? num(p.issues.open || 0) : "—"}
        >
          {p.repo ? `共采集 ${num(issuesTotal)} 条` : "没有关联 GitHub 仓库"}
        </Stat>
        <Stat label="进行中的跟进" value={num(open.length)}>
          {open.filter((f) => f.status === "pending").length} 条待处理
        </Stat>
      </div>

      <div className="grid cols-3">
        <Card
          className="span-2"
          title="评论量与不推荐率"
          description={`按周统计；评论少于 ${MIN_WEEKLY_REVIEWS} 条的周不显示不推荐率`}
        >
          <WeeklyTrend product={p} />
        </Card>
        <Card
          title="最近 30 天的变化"
          description={`与之前 30 天相比 · ${day(m.window.boundary)} 起`}
          actions={
            can.analyze && (
              <button
                className="btn small"
                onClick={() =>
                  openAssistant({
                    scope: "monitor",
                    label: "最近 30 天的变化",
                    question:
                      "最近 30 天的口碑变化是真实的吗？请考虑样本量和语言构成。",
                  })
                }
              >
                <Bot size={13} />
                解读
              </button>
            )
          }
        >
          <div className="change">
            <Badge tone={reading.tone}>{reading.label}</Badge>
            <p className="change-detail">{reading.detail}</p>
            <div className="change-compare">
              <div>
                <small>之前 30 天</small>
                <b>{pct(m.before.rate)}</b>
                <span>{num(m.before.n)} 条评论</span>
              </div>
              <div>
                <small>最近 30 天</small>
                <b>{pct(m.after.rate)}</b>
                <span>{num(m.after.n)} 条评论</span>
              </div>
            </div>
            <p className="muted">
              不推荐率变化 {pointsText(m.delta)}
              {m.language_adjusted.delta != null &&
                `；按语言构成调整后 ${pointsText(m.language_adjusted.delta)}`}
            </p>
          </div>
        </Card>
      </div>

      <div className="grid cols-3">
        <Card
          className="span-2"
          title="需要关注的问题"
          description="按最近 30 天在评论中被提及的次数排序"
          actions={
            <a className="btn small" href={href("issues")}>
              全部问题
            </a>
          }
          flush
        >
          <IssueTable product={p} />
        </Card>
        <div className="stack">
          <LatestRelease product={p} />
          <Card
            title="跟进动态"
            actions={
              <a className="btn small" href={href("follow-ups")}>
                全部
              </a>
            }
          >
            {followUps.filter((f) => f.product === p.key).length === 0 ? (
              <p className="muted">
                还没有跟进。在「反馈」里勾选评论或 issue，就可以创建跟进。
              </p>
            ) : (
              <ul className="mini-list">
                {followUps
                  .filter((f) => f.product === p.key)
                  .slice(0, 4)
                  .map((f) => (
                    <li key={f.id}>
                      <a href={href("follow-ups", undefined, { open: f.id })}>
                        {f.title}
                      </a>
                      <span>
                        <StatusBadge status={f.status} />
                        {relative(f.updated_at)}
                      </span>
                    </li>
                  ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      <div className="grid cols-2">
        <PlaytimeCard product={p} />
        <LanguageCard product={p} />
      </div>
    </>
  );
}

function IssueTable({ product: p }: { product: ProductReport }) {
  const rows = [...p.categories].sort(
    (a, b) =>
      b.trend.recent.mentions - a.trend.recent.mentions ||
      b.negative_reviews - a.negative_reviews,
  );
  return (
    <table className="table">
      <thead>
        <tr>
          <th>问题类型</th>
          <th className="num">近 30 天提及</th>
          <th className="num">较前 30 天</th>
          <th className="num">
            不推荐评论提及{" "}
            <Hint>180 天内，在给出「不推荐」的评论里提到这类问题的条数。</Hint>
          </th>
          <th className="num">未关闭 issue</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((c) => {
          const change = c.trend.recent.mentions - c.trend.previous.mentions;
          return (
            <tr
              key={c.key}
              className="clickable"
              onClick={() => (location.hash = href("issues", c.key))}
            >
              <td>
                <a href={href("issues", c.key)}>{c.label}</a>
              </td>
              <td className="num">{num(c.trend.recent.mentions)}</td>
              <td
                className={`num delta ${change > 0 ? "up" : change < 0 ? "down" : ""}`}
              >
                {change > 0 ? "+" : change < 0 ? "−" : ""}
                {change === 0 ? "持平" : Math.abs(change)}
              </td>
              <td className="num">{num(c.negative_reviews)}</td>
              <td className="num">{num(c.open_issues)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function LatestRelease({ product: p }: { product: ProductReport }) {
  const latest = p.release_studies[0];
  const comparable = p.release_studies.find(
    (s) => s.status === "descriptive_comparison",
  );
  const pending =
    latest &&
    latest.status === "incomplete_window" &&
    new Date(latest.window_after_end) > new Date(p.monitor.window.end);
  return (
    <Card
      title="最近的版本"
      actions={
        <a className="btn small" href={href("releases")}>
          全部版本
        </a>
      }
    >
      {!latest ? (
        <p className="muted">
          {p.releases_outside_window
            ? "评论时间范围内没有发布新版本。"
            : "这个项目没有在 GitHub 上发布 Release。"}
        </p>
      ) : (
        <div className="stack tight">
          <ReleaseTeaser
            tag={latest.tag}
            id={latest.release_id}
            published={latest.published_at}
            numbers={`${pct(latest.before.rate)} → ${pct(latest.after.rate)}`}
            badge={
              <Badge tone={verdict(latest).tone}>
                {pending ? "发布不满 14 天" : verdict(latest).label}
              </Badge>
            }
            note={
              pending
                ? "发布后的数据还在累积，暂不判断"
                : "发布前后各 14 天的不推荐率"
            }
          />
          {pending && comparable && comparable !== latest && (
            <p className="muted small-text">
              最近一个可对比的版本：
              <a href={href("releases", comparable.release_id)}>
                {comparable.tag}
              </a>
              ，{pct(comparable.before.rate)} → {pct(comparable.after.rate)}，
              {verdict(comparable).label}
            </p>
          )}
        </div>
      )}
    </Card>
  );
}

function ReleaseTeaser(props: {
  tag: string;
  id: string;
  published: string;
  numbers: string;
  badge: ReactNode;
  note: string;
}) {
  return (
    <a className="release-teaser" href={href("releases", props.id)}>
      <div>
        <b>{props.tag}</b>
        <span className="muted">{day(props.published)} 发布</span>
      </div>
      <div className="release-teaser-numbers">
        <span>{props.numbers}</span>
        {props.badge}
      </div>
      <span className="muted">{props.note}</span>
    </a>
  );
}

function PlaytimeCard({ product: p }: { product: ProductReport }) {
  const rows = PLAYTIME_ORDER.map((key) =>
    p.cohorts.find((c) => c.cohort === key),
  ).filter((c): c is NonNullable<typeof c> => !!c && c.n > 0);
  const newcomers = rows.find((c) => c.cohort === "0–2h");
  const overall = p.recommendation.rate;
  const ratio =
    newcomers && overall && newcomers.n >= 30 && newcomers.rate != null
      ? newcomers.rate / overall
      : null;
  return (
    <Card
      title="按游玩时长"
      description={
        ratio && ratio >= 1.5
          ? `游玩 2 小时以内的玩家，不推荐率是整体的 ${ratio.toFixed(1)} 倍`
          : "按写评论时的累计游玩时长分组"
      }
      flush
    >
      <RateTable
        rows={rows.map((c) => ({
          key: c.cohort,
          label: PLAYTIME[c.cohort] || c.cohort,
          n: c.n,
          rate: c.rate,
        }))}
        total={p.recommendation.n}
      />
    </Card>
  );
}

function LanguageCard({ product: p }: { product: ProductReport }) {
  const top = p.languages.slice(0, 5);
  const rest = p.languages.slice(5);
  const restN = rest.reduce((s, l) => s + l.n, 0);
  const restNegative = rest.reduce((s, l) => s + l.negative, 0);
  const rows = top.map((l) => ({
    key: l.language,
    label: language(l.language),
    n: l.n,
    rate: l.rate,
  }));
  if (restN)
    rows.push({
      key: "other",
      label: `其他 ${rest.length} 种语言`,
      n: restN,
      rate: restNegative / restN,
    });
  return (
    <Card title="按评论语言" description="Steam 上评论者选择的语言" flush>
      <RateTable rows={rows} total={p.recommendation.n} />
    </Card>
  );
}

function RateTable({
  rows,
  total,
}: {
  rows: { key: string; label: string; n: number; rate: number | null }[];
  total: number;
}) {
  const max = Math.max(...rows.map((r) => r.rate ?? 0), 0.0001);
  return (
    <table className="table">
      <thead>
        <tr>
          <th>分组</th>
          <th className="num">评论数</th>
          <th className="num">占比</th>
          <th>不推荐率</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.key}>
            <td>{r.label}</td>
            <td className="num">{num(r.n)}</td>
            <td className="num">{pct(r.n / total, 0)}</td>
            <td>
              <div className="bar-cell">
                <span className="bar-track">
                  <span
                    className="bar"
                    style={{ width: `${((r.rate ?? 0) / max) * 100}%` }}
                  />
                </span>
                {r.n < 30 ? (
                  <span title="样本少于 30 条，比例波动较大">
                    {pct(r.rate)}*
                  </span>
                ) : (
                  <span>{pct(r.rate)}</span>
                )}
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
