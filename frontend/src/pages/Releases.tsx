import { Bot, ExternalLink } from "lucide-react";
import { ReleaseWindow } from "../components/Charts";
import { Badge, Card, Delta, Empty, PageHeader } from "../components/ui";
import { useData } from "../context";
import { day, num, pct, pointsText, verdict } from "../format";
import { href, navigate } from "../route";
import type { ReleaseStudy } from "../types";

export function Releases({ selected }: { selected?: string }) {
  const { product: p, can } = useData();
  const studies = p.release_studies;
  const outside = p.releases_outside_window || 0;
  const current =
    studies.find((s) => s.release_id === selected) ||
    studies.find((s) => s.status === "descriptive_comparison") ||
    studies[0];

  return (
    <>
      <PageHeader
        title="版本"
        description="对比每个版本发布前后各 14 天的不推荐率。发布时间取自 GitHub Release，可能早于玩家在 Steam 上收到更新的时间。"
      />
      {!p.repo ? (
        <Card>
          <Empty
            title="没有关联 GitHub 仓库"
            action={
              can.admin && (
                <a className="btn" href={href("settings", "games")}>
                  去关联仓库
                </a>
              )
            }
          >
            版本发布时间取自 GitHub Release。关联 {p.name}{" "}
            的公开仓库并重新同步后，就能对比每个版本发布前后的玩家评价。
          </Empty>
        </Card>
      ) : studies.length === 0 ? (
        <Card>
          <Empty
            title={outside ? "评论时间范围内没有版本发布" : "没有版本记录"}
          >
            {outside
              ? `${p.name} 最近的 ${outside} 个 GitHub Release 都早于本次采集的评论时间范围，无法对比发布前后的评论。`
              : `${p.name} 没有在 GitHub 上发布 Release，无法按版本对比。`}
          </Empty>
        </Card>
      ) : (
        <>
          <Card flush>
            <div className="table-scroll">
              <table className="table selectable sticky-head">
                <thead>
                  <tr>
                    <th>版本</th>
                    <th>发布日期</th>
                    <th className="num">发布前 14 天</th>
                    <th className="num">发布后 14 天</th>
                    <th className="num">变化（百分点）</th>
                    <th>判断</th>
                    <th className="num">同期其他版本</th>
                  </tr>
                </thead>
                <tbody>
                  {studies.map((s) => {
                    const v = verdict(s);
                    return (
                      <tr
                        key={s.release_id}
                        className={
                          s.release_id === current?.release_id ? "selected" : ""
                        }
                        onClick={() =>
                          navigate(href("releases", s.release_id), true)
                        }
                      >
                        <td>
                          <b>{s.tag}</b>
                        </td>
                        <td>{day(s.published_at)}</td>
                        <td className="num">
                          {pct(s.before.rate)}{" "}
                          <small className="muted">{num(s.before.n)} 条</small>
                        </td>
                        <td className="num">
                          {pct(s.after.rate)}{" "}
                          <small className="muted">{num(s.after.n)} 条</small>
                        </td>
                        <td className="num">
                          <Delta value={s.delta} />
                        </td>
                        <td>
                          <Badge tone={v.tone}>{v.label}</Badge>
                        </td>
                        <td className="num">
                          {s.other_releases.length || "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {outside > 0 && (
              <p className="table-note">
                另有 {outside} 个更早的版本不在评论时间范围内，未列出。
              </p>
            )}
          </Card>
          {current && <ReleaseDetail study={current} />}
        </>
      )}
    </>
  );
}

function ReleaseDetail({ study: s }: { study: ReleaseStudy }) {
  const { product: p, can, openAssistant } = useData();
  const v = verdict(s);
  return (
    <Card
      title={`${s.tag}${s.title && s.title !== s.tag ? " · " + s.title : ""}`}
      description={`${day(s.published_at)} 发布`}
      actions={
        <>
          <a
            className="btn small"
            href={s.source_url}
            target="_blank"
            rel="noreferrer"
          >
            <ExternalLink size={13} />
            发布说明
          </a>
          {can.analyze && (
            <button
              className="btn small"
              onClick={() =>
                openAssistant({
                  scope: "release",
                  release_id: s.release_id,
                  label: `版本 ${s.tag}`,
                  question: `版本 ${s.tag} 发布后玩家反馈有什么变化？哪些结论站得住？`,
                })
              }
            >
              <Bot size={13} />
              AI 复盘
            </button>
          )}
        </>
      }
    >
      <div className="grid release-detail">
        <div>
          <div className="mini-stats">
            <div>
              <small>发布前 14 天</small>
              <b>{pct(s.before.rate)}</b>
              <span>{num(s.before.n)} 条评论</span>
            </div>
            <div>
              <small>发布后 14 天</small>
              <b>{pct(s.after.rate)}</b>
              <span>{num(s.after.n)} 条评论</span>
            </div>
            <div>
              <small>变化</small>
              <b>
                <Delta value={s.delta} />
              </b>
              <span>
                <Badge tone={v.tone}>{v.label}</Badge>
              </span>
            </div>
          </div>
          <ul className="notes">
            <li>{v.detail}。</li>
            {s.language_adjusted.delta != null && (
              <li>
                按两段时间共同的评论语言调整构成后，变化为{" "}
                {pointsText(s.language_adjusted.delta)}。
              </li>
            )}
            {s.other_releases.length > 0 && (
              <li>
                前后 14 天内还有 {s.other_releases.length} 个版本（
                {s.other_releases.map((r) => r.tag).join("、")}
                ），变化不能单独归因到 {s.tag}。
              </li>
            )}
            <li>
              不推荐率受版本以外的因素影响，例如促销、节假日和评论者语言构成。
            </li>
          </ul>
        </div>
        <div>
          <h3 className="chart-title">每日评论（推荐 / 不推荐）</h3>
          <ReleaseWindow product={p} study={s} />
        </div>
      </div>
    </Card>
  );
}
