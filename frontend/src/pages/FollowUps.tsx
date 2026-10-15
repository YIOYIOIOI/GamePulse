import { Plus } from "lucide-react";
import { useEffect } from "react";
import { StatusBadge } from "../components/FollowUpDialogs";
import { Card, Empty, PageHeader } from "../components/ui";
import { useApp } from "../context";
import { dateTime, num, relative, STATUS, STATUS_ORDER } from "../format";
import { href, navigate } from "../route";
import type { FollowUpStatus } from "../types";

export function FollowUps({ params }: { params: URLSearchParams }) {
  const { game, followUps, can, showFollowUp, notify } = useApp();
  const status = (params.get("status") || "") as FollowUpStatus | "";
  const opened = params.get("open");

  useEffect(() => {
    if (!opened) return;
    showFollowUp(opened);
    navigate(
      href("follow-ups", undefined, { status: status || undefined }),
      true,
    );
  }, [opened, status, showFollowUp]);

  const mine = followUps.filter((f) => f.product === game?.key);
  const rows = mine
    .filter((f) => !status || f.status === status)
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at));

  return (
    <>
      <PageHeader
        title="跟进"
        description="从玩家反馈中挑出需要处理的问题，记录负责人、状态和每一次处理。"
        actions={
          can.analyze && (
            <button
              className="btn primary"
              onClick={() => {
                navigate(href("feedback"));
                notify(
                  "在反馈列表里勾选相关的评论或 issue，然后点「创建跟进」",
                );
              }}
            >
              <Plus size={15} />
              新建跟进
            </button>
          )
        }
      />
      <div className="tabs" role="tablist">
        {(["", ...STATUS_ORDER] as const).map((s) => (
          <a
            key={s || "all"}
            role="tab"
            aria-selected={status === s}
            className={status === s ? "active" : ""}
            href={href("follow-ups", undefined, { status: s || undefined })}
          >
            {s ? STATUS[s] : "全部"}
            <span>
              {num(s ? mine.filter((f) => f.status === s).length : mine.length)}
            </span>
          </a>
        ))}
      </div>
      <Card flush>
        {rows.length === 0 ? (
          <Empty title={mine.length ? "这个状态下没有跟进" : "还没有跟进"}>
            {mine.length
              ? null
              : "在「反馈」里勾选需要处理的评论或 issue，点「创建跟进」，再指定负责人。"}
          </Empty>
        ) : (
          <table className="table selectable">
            <thead>
              <tr>
                <th>问题</th>
                <th>状态</th>
                <th>负责人</th>
                <th className="num">关联反馈</th>
                <th>最近更新</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((f) => {
                const last = f.history.at(-1);
                return (
                  <tr key={f.id} onClick={() => showFollowUp(f.id)}>
                    <td className="title-cell">{f.title}</td>
                    <td>
                      <StatusBadge status={f.status} />
                    </td>
                    <td>{f.owner || <span className="muted">未指定</span>}</td>
                    <td className="num">{num(f.evidence_ids.length)}</td>
                    <td title={dateTime(f.updated_at)}>
                      {relative(f.updated_at)}
                      {last?.actor && (
                        <span className="muted"> · {last.actor}</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
