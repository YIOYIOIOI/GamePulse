import { ExternalLink, Plus, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { RemoveGameDialog, RepoDialog } from "../components/GameDialogs";
import { Badge, Card, Empty, PageHeader, Spinner } from "../components/ui";
import { useApp } from "../context";
import { dateTime, day, errorText, num, ROLES } from "../format";
import { href } from "../route";
import type { Backup, Coverage, Game, Member, Role } from "../types";

const TABS = [
  ["games", "游戏"],
  ["sources", "数据源"],
  ["members", "成员与权限"],
  ["backups", "备份"],
  ["method", "指标口径"],
] as const;

export function SettingsPage({ tab = "games" }: { tab?: string }) {
  const current = TABS.some(([key]) => key === tab) ? tab : "games";
  return (
    <>
      <PageHeader title="设置" />
      <div className="tabs" role="tablist">
        {TABS.map(([key, label]) => (
          <a
            key={key}
            role="tab"
            aria-selected={current === key}
            className={current === key ? "active" : ""}
            href={href("settings", key)}
          >
            {label}
          </a>
        ))}
      </div>
      {current === "games" && <Games />}
      {current === "sources" && <Sources />}
      {current === "members" && <Members />}
      {current === "backups" && <Backups />}
      {current === "method" && <Method />}
    </>
  );
}

function Games() {
  const { games, can, busyJob, refreshGames, openAddGame, openSync, notify } =
    useApp();
  const [linking, setLinking] = useState<Game | null>(null);
  const [removing, setRemoving] = useState<Game | null>(null);
  return (
    <>
      <Card
        title="监控的游戏"
        description="每次同步会抓取这些游戏的 Steam 评论；关联了 GitHub 仓库的，还会抓取 issue 和版本发布记录。"
        actions={
          can.admin && (
            <button className="btn small primary" onClick={openAddGame}>
              <Plus size={13} />
              添加游戏
            </button>
          )
        }
        flush
      >
        {games.length === 0 ? (
          <Empty title="还没有添加游戏">
            {can.admin
              ? "点右上角「添加游戏」，按名称或 App ID 在 Steam 上查找。"
              : "请联系管理员添加游戏。"}
          </Empty>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>游戏</th>
                <th className="num">Steam App ID</th>
                <th>GitHub 仓库</th>
                <th className="num">当前数据</th>
                <th>添加时间</th>
                {can.admin && <th />}
              </tr>
            </thead>
            <tbody>
              {games.map((g) => (
                <tr key={g.key}>
                  <td>
                    <a
                      href={`https://store.steampowered.com/app/${g.app_id}/`}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-link"
                    >
                      {g.name}
                      <ExternalLink size={12} />
                    </a>
                  </td>
                  <td className="num">{g.app_id}</td>
                  <td>
                    {g.repo ? (
                      <a
                        href={`https://github.com/${g.repo}`}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-link"
                      >
                        {g.repo}
                        <ExternalLink size={12} />
                      </a>
                    ) : (
                      <span className="muted">未关联</span>
                    )}
                  </td>
                  <td className="num">
                    {g.latest ? (
                      `${num(g.latest.reviews)} 条评论`
                    ) : (
                      <span className="muted">还没有数据</span>
                    )}
                  </td>
                  <td>{day(g.added_at)}</td>
                  {can.admin && (
                    <td className="num nowrap">
                      {!g.latest && (
                        <button
                          className="link-button"
                          disabled={!!busyJob}
                          onClick={() => openSync([g.key])}
                        >
                          同步
                        </button>
                      )}
                      <button
                        className="link-button"
                        onClick={() => setLinking(g)}
                      >
                        {g.repo ? "修改仓库" : "关联仓库"}
                      </button>
                      <button
                        className="link-button danger"
                        onClick={() => setRemoving(g)}
                      >
                        移除
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      {linking && (
        <RepoDialog
          game={linking}
          onClose={() => setLinking(null)}
          onSaved={(saved) => {
            setLinking(null);
            void refreshGames();
            notify(
              saved.repo
                ? `已关联 ${saved.repo}，下次同步开始抓取`
                : "已取消关联 GitHub 仓库",
            );
          }}
        />
      )}
      {removing && (
        <RemoveGameDialog
          game={removing}
          onClose={() => setRemoving(null)}
          onRemoved={() => {
            notify(`已移除 ${removing.name}`);
            setRemoving(null);
            void refreshGames();
          }}
        />
      )}
    </>
  );
}

const SOURCE_NAMES: Record<string, string> = {
  steam: "Steam 评论",
  github_issues: "GitHub issue",
  github_releases: "GitHub Release",
};

function coverageNote(source: string, c: Coverage) {
  if (c.stop_reason === "not_linked") return "没有关联 GitHub 仓库";
  if (c.complete)
    return source === "steam" ? "时间范围内的评论已全部采集" : "已全部采集";
  if (c.stop_reason === "page_cap") return "达到单次采集的分页上限，只有一部分";
  return "未全部采集（" + c.stop_reason + "）";
}

function Sources() {
  const {
    report,
    runs,
    games,
    can,
    busyJob,
    latestRunId,
    openSync,
    startJob,
    viewSnapshot,
    notify,
  } = useApp();
  const recompute = async () => {
    if (!report) return;
    try {
      await startJob((await api.recompute(report.run_id)).run_id);
      notify("已开始用当前规则重新计算");
    } catch (e) {
      notify(errorText(e), "error");
    }
  };
  return (
    <>
      <Card
        title="当前数据"
        actions={
          can.admin && (
            <>
              {report && (
                <button
                  className="btn small"
                  disabled={!!busyJob}
                  onClick={() => void recompute()}
                  title="不重新抓取，用已保存的原始数据和当前规则重新计算指标"
                >
                  重新计算
                </button>
              )}
              <button
                className="btn small primary"
                disabled={!!busyJob || games.length === 0}
                onClick={() => openSync()}
              >
                <RefreshCw size={13} />
                同步数据
              </button>
            </>
          )
        }
      >
        {!report ? (
          <p className="muted">
            {games.length === 0
              ? "还没有添加游戏。先在「游戏」里添加要监控的游戏，再同步数据。"
              : "还没有同步过数据。"}
          </p>
        ) : (
          <dl className="facts wide">
            <dt>数据截至</dt>
            <dd>{dateTime(report.as_of)}</dd>
            <dt>评论时间范围</dt>
            <dd>
              {day(report.window_start)} 至 {day(report.as_of)}
            </dd>
            <dt>原始数据</dt>
            <dd>
              {num(report.raw_page_count)} 个 API
              响应页，每条反馈都可以追溯到所在的响应页
            </dd>
            <dt>快照编号</dt>
            <dd>
              <code>{report.run_id}</code>
            </dd>
          </dl>
        )}
        {busyJob && <Spinner label={busyJob.progress.message || "正在同步"} />}
      </Card>

      {report && (
        <Card title="采集范围" flush>
          <table className="table">
            <thead>
              <tr>
                <th>游戏</th>
                <th>来源</th>
                <th className="num">采集条数</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {report.products.flatMap((p) =>
                Object.entries(p.coverage).map(([source, c], i) => (
                  <tr key={p.key + source}>
                    <td>{i === 0 ? p.name : ""}</td>
                    <td>{SOURCE_NAMES[source] || source}</td>
                    <td className="num">
                      {c.stop_reason === "not_linked" ? "—" : num(c.accepted)}
                    </td>
                    <td>
                      {c.stop_reason === "not_linked" ? (
                        <Badge tone="muted">未关联</Badge>
                      ) : (
                        <Badge tone={c.complete ? "good" : "warn"}>
                          {c.complete ? "完整" : "部分"}
                        </Badge>
                      )}{" "}
                      <span className="muted">{coverageNote(source, c)}</span>
                    </td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </Card>
      )}

      {runs.length > 0 && (
        <Card title="同步记录" flush>
          <table className="table">
            <thead>
              <tr>
                <th>开始时间</th>
                <th>类型</th>
                <th>游戏</th>
                <th>结果</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td>{dateTime(r.started_at)}</td>
                  <td>{r.config.replayed_from ? "重新计算" : "同步"}</td>
                  <td>{r.config.products?.length ?? 0} 款</td>
                  <td>
                    {r.status === "completed" ? (
                      <Badge tone="good">完成</Badge>
                    ) : r.status === "failed" ? (
                      <span title={r.error || ""}>
                        <Badge tone="bad">失败</Badge>{" "}
                        <span className="muted">
                          {(r.error || "").slice(0, 60)}
                        </span>
                      </span>
                    ) : (
                      <Badge tone="info">进行中</Badge>
                    )}
                  </td>
                  <td className="num">
                    {r.status === "completed" &&
                      (r.id === report?.run_id ? (
                        <span className="muted">
                          {r.id === latestRunId ? "当前" : "正在查看"}
                        </span>
                      ) : (
                        <button
                          className="link-button"
                          onClick={() => viewSnapshot(r.id)}
                        >
                          查看这份数据
                        </button>
                      ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}

function Members() {
  const { session, can, notify } = useApp();
  const [members, setMembers] = useState<Member[] | null>(null);
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("analyst");
  const [created, setCreated] = useState<string>("");
  const load = useCallback(
    () => api.members().then(setMembers, (e) => notify(errorText(e), "error")),
    [notify],
  );
  useEffect(() => {
    if (can.admin) void load();
  }, [can.admin, load]);
  return (
    <>
      <Card title="当前身份">
        <p>
          {session?.principal.name} ·{" "}
          {ROLES[session?.principal.role ?? "viewer"].label} · 工作区{" "}
          {session?.principal.workspace}
        </p>
        {!session?.team_mode && (
          <p className="muted">
            服务以本机单人模式运行，所有操作都以本地管理员身份执行。多人使用时，请以团队模式启动服务，成员凭访问令牌或企业单点登录进入，详见运行手册。
          </p>
        )}
      </Card>
      <Card title="角色说明" flush>
        <table className="table">
          <tbody>
            {(Object.keys(ROLES) as Role[]).map((r) => (
              <tr key={r}>
                <td className="nowrap">{ROLES[r].label}</td>
                <td className="muted">{ROLES[r].description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      {can.admin && (
        <Card title="成员" flush>
          {members === null ? (
            <div className="list-loading">
              <Spinner />
            </div>
          ) : members.length === 0 ? (
            <Empty title="还没有添加成员" />
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>名称</th>
                  <th>角色</th>
                  <th>添加时间</th>
                  <th>状态</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {members.map((m) => (
                  <tr key={m.id}>
                    <td>{m.name}</td>
                    <td>{ROLES[m.role]?.label ?? m.role}</td>
                    <td>{dateTime(m.created_at)}</td>
                    <td>
                      {m.revoked ? (
                        <Badge tone="muted">已停用</Badge>
                      ) : (
                        <Badge tone="good">有效</Badge>
                      )}
                    </td>
                    <td className="num">
                      {!m.revoked && (
                        <button
                          className="link-button danger"
                          onClick={() =>
                            void api
                              .revokeMember(m.id)
                              .then(load, (e) => notify(errorText(e), "error"))
                          }
                        >
                          停用
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <form
            className="inline-form"
            onSubmit={(e) => {
              e.preventDefault();
              void api.addMember(name.trim(), role).then(
                (m) => {
                  setName("");
                  setCreated(m.token_file);
                  void load();
                },
                (err) => notify(errorText(err), "error"),
              );
            }}
          >
            <input
              placeholder="成员名称"
              value={name}
              maxLength={100}
              onChange={(e) => setName(e.target.value)}
            />
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
            >
              {(Object.keys(ROLES) as Role[]).map((r) => (
                <option key={r} value={r}>
                  {ROLES[r].label}
                </option>
              ))}
            </select>
            <button className="btn primary small" disabled={!name.trim()}>
              添加成员
            </button>
          </form>
          {created && (
            <p className="table-note">
              已添加。访问令牌只写在服务器上的文件里：<code>{created}</code>
              ，请把令牌交给成员本人。
            </p>
          )}
        </Card>
      )}
    </>
  );
}

function Backups() {
  const { can, session, notify } = useApp();
  const [backups, setBackups] = useState<Backup[] | null>(null);
  const [busy, setBusy] = useState(false);
  const allowed = can.admin && session?.principal.workspace === "main";
  const load = useCallback(
    () => api.backups().then(setBackups, (e) => notify(errorText(e), "error")),
    [notify],
  );
  useEffect(() => {
    if (allowed) void load();
  }, [allowed, load]);
  if (!allowed)
    return (
      <Card>
        <Empty title="只有主工作区的管理员可以管理备份" />
      </Card>
    );
  return (
    <Card
      title="备份"
      description="备份包含数据库和全部原始数据，不包含访问令牌。从备份恢复请使用命令行，见运行手册。"
      actions={
        <button
          className="btn small primary"
          disabled={busy}
          onClick={() => {
            setBusy(true);
            void api
              .createBackup()
              .then(
                () => {
                  notify("备份已创建");
                  return load();
                },
                (e) => notify(errorText(e), "error"),
              )
              .finally(() => setBusy(false));
          }}
        >
          {busy ? "正在备份…" : "立即备份"}
        </button>
      }
      flush
    >
      {backups === null ? (
        <div className="list-loading">
          <Spinner />
        </div>
      ) : backups.length === 0 ? (
        <Empty title="还没有备份" />
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>时间</th>
              <th className="num">文件数</th>
              <th className="num">大小</th>
              <th>位置</th>
            </tr>
          </thead>
          <tbody>
            {backups.map((b) => (
              <tr key={b.id}>
                <td>{b.at ? dateTime(b.at) : b.id.slice(0, 15)}</td>
                <td className="num">{num(b.files)}</td>
                <td className="num">{(b.bytes / 1024 / 1024).toFixed(1)} MB</td>
                <td>
                  <code className="path">{b.path}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

// Same limits as the method notes in every exported report (src/quality/analytics.py).
const BOUNDARIES = [
  "写评论的玩家是主动发声的一部分人；置信区间只反映抽样误差，不能消除这种偏差。",
  "GitHub issue 主要来自开发者和核心玩家，与 Steam 评论是不同人群，两者的数量不合并计算。",
  "GitHub 发布时间不等于玩家在 Steam 上收到更新的时间；没有对照组，版本前后的变化不能当作版本造成的效果。",
  "问题分类基于可解释的关键词匹配，没有经过人工抽检验收，需结合原文判断。",
];

function Method() {
  const { report } = useApp();
  return (
    <Card title="指标口径">
      <dl className="definitions">
        <dt>不推荐率</dt>
        <dd>
          不推荐评论数 ÷ 评论总数。来自玩家在 Steam 写评论时选择的「推荐 /
          不推荐」，反映评论者的推荐意愿，不等于全部玩家的满意度，也不是对评论文字的情绪判断。
        </dd>
        <dt>最近 30 天的变化</dt>
        <dd>
          比较最近 30 天和之前 30 天的不推荐率，两段时间各需至少 50
          条评论。差值的 95% 置信区间不包含 0
          时判断为「明显变差」或「明显好转」；「需要排查」还要求按评论语言调整构成、按周重新抽样后结论依然成立。
        </dd>
        <dt>版本前后对比</dt>
        <dd>
          比较版本发布前 14 天和发布后 14 天，两段各需至少 30
          条评论，且时间段完整落在采集范围内。发布时间取自 GitHub Release；前后
          14 天内还有其他版本时会标出，这时变化不能单独归因到某一个版本。
        </dd>
        <dt>问题类型</dt>
        <dd>
          用关键词把评论和 issue 归入 6 类问题，评论支持英文、中文和俄文。GitHub
          issue 会先去掉模板里的固定标题、勾选项和注释，避免「(Crash)
          logs」这类模板文字被当成玩家反馈。一条反馈可以同时属于多类。关键词归类没有经过人工抽检验收，判断问题前请阅读原文。
        </dd>
        <dt>游玩时长分组</dt>
        <dd>
          按写评论时的累计游玩时长分为 2 小时以内、2–20 小时和 20
          小时以上，用来区分新玩家和老玩家的评价。
        </dd>
        <dt>数据边界</dt>
        <dd>
          <ul>
            {BOUNDARIES.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        </dd>
        <dt>版本</dt>
        <dd className="muted">
          {report
            ? `指标 ${report.metric_version} · 问题分类 ${report.taxonomy_version}`
            : "同步数据后显示"}
        </dd>
      </dl>
    </Card>
  );
}
