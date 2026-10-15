import {
  Activity,
  AlertTriangle,
  Bot,
  ChevronsUpDown,
  Download,
  GitBranch,
  LayoutDashboard,
  ListChecks,
  MessagesSquare,
  Plus,
  RefreshCw,
  Settings,
  Tags,
  UserRound,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from "react";
import { api, download } from "./api";
import { AccessDialog } from "./components/AccessDialog";
import { Assistant } from "./components/Assistant";
import { EvidenceDrawer } from "./components/EvidenceDrawer";
import { CreateFollowUp, FollowUpDrawer } from "./components/FollowUpDialogs";
import { AddGameDialog } from "./components/GameDialogs";
import { SyncDialog } from "./components/SyncDialog";
import { Card, Empty, Spinner } from "./components/ui";
import {
  AppContext,
  useApp,
  type AppState,
  type AssistantContext,
} from "./context";
import { dateTime, errorText, num, ROLES } from "./format";
import { Feedback } from "./pages/Feedback";
import { FollowUps } from "./pages/FollowUps";
import { Issues } from "./pages/Issues";
import { Overview } from "./pages/Overview";
import { Releases } from "./pages/Releases";
import { SettingsPage } from "./pages/Settings";
import { href, navigate, useRoute, type Page } from "./route";
import type { FollowUp, Game, Report, Run, Session } from "./types";

const NAV: { page: Page; label: string; icon: typeof Activity }[] = [
  { page: "overview", label: "概览", icon: LayoutDashboard },
  { page: "issues", label: "问题", icon: Tags },
  { page: "releases", label: "版本", icon: GitBranch },
  { page: "feedback", label: "反馈", icon: MessagesSquare },
  { page: "follow-ups", label: "跟进", icon: ListChecks },
];

const GAME_KEY = "gamepulse-game";

export default function App() {
  const route = useRoute();
  const [games, setGames] = useState<Game[]>([]);
  // The snapshot on screen and the game it was loaded for.
  const [snapshot, setSnapshot] = useState<{
    game: string;
    report: Report | null;
  } | null>(null);
  const [snapshotVersion, reloadSnapshot] = useReducer((n: number) => n + 1, 0);
  const [runs, setRuns] = useState<Run[]>([]);
  const [followUps, setFollowUps] = useState<FollowUp[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [gameKey, setGameKey] = useState(
    () => localStorage.getItem(GAME_KEY) || "",
  );
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [job, setJob] = useState<Run | null>(null);
  const [toast, setToast] = useState<{
    message: string;
    tone: "error" | "info";
  } | null>(null);
  const [evidence, setEvidence] = useState<{
    id: string;
    runId: string;
  } | null>(null);
  const [followUpId, setFollowUpId] = useState<string | null>(null);
  const [creating, setCreating] = useState<{
    ids: string[];
    title?: string;
    runId?: string;
  } | null>(null);
  const [assistant, setAssistant] = useState<AssistantContext | null>(null);
  const [sync, setSync] = useState<{ keys?: string[] } | null>(null);
  const [addingGame, setAddingGame] = useState(false);
  const [accessOpen, setAccessOpen] = useState(false);

  const notify = useCallback(
    (message: string, tone: "error" | "info" = "info") => {
      setToast({ message, tone });
    },
    [],
  );
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(
      () => setToast(null),
      toast.tone === "error" ? 8000 : 4000,
    );
    return () => window.clearTimeout(timer);
  }, [toast]);

  const load = useCallback(async () => {
    setLoadError("");
    try {
      const [current, gameList, recentRuns, items] = await Promise.all([
        api.session(),
        api.games(),
        api.runs(),
        api.followUps(),
      ]);
      setSession(current);
      setGames(gameList);
      setRuns(recentRuns);
      setFollowUps(items);
      const active = recentRuns.find(
        (r) => r.status === "running" || r.status === "queued",
      );
      if (active) setJob(active);
    } catch (e) {
      setLoadError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  // Leaving a page closes its drawers and dialogs; the assistant panel stays open. A layout effect,
  // so it runs before a page's own effects, which may open a drawer from the URL (?open=).
  useLayoutEffect(() => {
    setEvidence(null);
    setFollowUpId(null);
    setCreating(null);
  }, [route.page]);
  useEffect(() => {
    const ask = () => setAccessOpen(true);
    window.addEventListener("gamepulse-auth-needed", ask);
    return () => window.removeEventListener("gamepulse-auth-needed", ask);
  }, []);

  // Poll a running sync until it finishes, then show the new snapshot.
  const loadRef = useRef(load);
  loadRef.current = load;
  useEffect(() => {
    if (!job || (job.status !== "queued" && job.status !== "running")) return;
    let stopped = false;
    const timer = window.setInterval(async () => {
      try {
        const next = await api.run(job.id);
        if (stopped) return;
        setJob(next);
        if (next.status === "completed") {
          await loadRef.current();
          reloadSnapshot();
          setToast({ message: "数据已更新", tone: "info" });
        } else if (next.status === "failed") {
          setRuns(await api.runs());
          setToast({
            message:
              "同步失败，已有数据不受影响：" + (next.error || "未知错误"),
            tone: "error",
          });
        }
      } catch (e) {
        if (!stopped) setToast({ message: errorText(e), tone: "error" });
      }
    }, 2000);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [job?.id, job?.status]);

  const game = games.find((g) => g.key === gameKey) || games[0] || null;
  // Each game shows the newest snapshot that collected it; games can be synced on their own.
  useEffect(() => {
    if (!game?.latest) return;
    let alive = true;
    api
      .snapshot({ game: game.key })
      .then((s) => alive && setSnapshot({ game: game.key, report: s.report }))
      .catch((e) => alive && notify(errorText(e), "error"));
    return () => {
      alive = false;
    };
  }, [game?.key, game?.latest?.run_id, snapshotVersion, notify]);
  const report =
    snapshot && game && snapshot.game === game.key ? snapshot.report : null;
  const latestRunId = game?.latest?.run_id ?? null;
  const loadingSnapshot = !!game?.latest && !report;
  const product =
    (game && report?.products.find((p) => p.key === game.key)) || null;
  const role = session?.principal.role;
  const can = useMemo(
    () => ({
      analyze: role === "owner" || role === "reviewer" || role === "analyst",
      review: role === "owner" || role === "reviewer",
      admin: role === "owner",
    }),
    [role],
  );
  const busyJob =
    job && (job.status === "queued" || job.status === "running") ? job : null;

  const selectGame = useCallback((key: string) => {
    setGameKey(key);
    localStorage.setItem(GAME_KEY, key);
  }, []);
  const state: AppState = {
    games,
    game,
    report,
    product,
    latestRunId,
    runs,
    followUps,
    session,
    can,
    busyJob,
    selectGame,
    refreshGames: async () => setGames(await api.games()),
    viewSnapshot: (runId) => {
      if (!runId) return reloadSnapshot();
      void api
        .snapshot({ runId })
        .then((s) => {
          if (!s.report) return;
          // An older snapshot may not include the game on screen; show one it does include.
          const shown = s.report.products.some((p) => p.key === game?.key)
            ? game?.key
            : s.report.products.find((p) => games.some((g) => g.key === p.key))
                ?.key;
          if (!shown) return notify("这份数据里没有当前添加的游戏", "error");
          selectGame(shown);
          setSnapshot({ game: shown, report: s.report });
        })
        .catch((e) => notify(errorText(e), "error"));
    },
    showEvidence: (id, runId) => {
      const target = runId || report?.run_id;
      if (target) setEvidence({ id, runId: target });
    },
    showFollowUp: (id) => setFollowUpId(id),
    openAssistant: setAssistant,
    createFollowUp: (ids, title, runId) => setCreating({ ids, title, runId }),
    refreshFollowUps: async () => setFollowUps(await api.followUps()),
    startJob: async (runId) => {
      setJob(await api.run(runId));
      setRuns(await api.runs());
    },
    openSync: (keys) => setSync({ keys }),
    openAddGame: () => setAddingGame(true),
    notify,
  };

  const openCount = followUps.filter(
    (f) =>
      f.product === game?.key &&
      (f.status === "pending" || f.status === "investigating"),
  ).length;
  const dataPage = route.page !== "settings" && route.page !== "follow-ups";

  return (
    <AppContext.Provider value={state}>
      <div className="app">
        <aside className="sidebar">
          <a className="brand" href={href("overview")}>
            <span className="brand-mark">
              <Activity size={16} strokeWidth={2.5} />
            </span>
            <span>
              GamePulse
              <small>玩家反馈监控</small>
            </span>
          </a>
          <GameSwitcher />
          <nav>
            {NAV.map((item) => (
              <a
                key={item.page}
                href={href(item.page)}
                className={route.page === item.page ? "active" : ""}
                aria-current={route.page === item.page ? "page" : undefined}
              >
                <item.icon size={16} />
                {item.label}
                {item.page === "follow-ups" && openCount > 0 && (
                  <span className="nav-count">{openCount}</span>
                )}
              </a>
            ))}
          </nav>
          <nav className="nav-bottom">
            <a
              href={href("settings")}
              className={route.page === "settings" ? "active" : ""}
            >
              <Settings size={16} />
              设置
            </a>
          </nav>
        </aside>

        <div className="main">
          <header className="topbar">
            {report && product ? (
              <span className="topbar-meta">
                数据截至 {dateTime(report.as_of)}
                {product.quality.warnings.length > 0 && (
                  <a
                    className="coverage-flag"
                    href={href("settings", "sources")}
                    title={product.quality.warnings.join("\n")}
                  >
                    <AlertTriangle size={13} />
                    部分数据不完整
                  </a>
                )}
              </span>
            ) : (
              <span />
            )}
            <div className="topbar-actions">
              {busyJob && (
                <span className="job-status">
                  <Spinner label={busyJob.progress.message || "正在同步数据"} />
                </span>
              )}
              {product && (
                <>
                  <button
                    className="btn"
                    onClick={() =>
                      setAssistant({ scope: "overview", label: "整体情况" })
                    }
                    disabled={!can.analyze}
                    title={can.analyze ? undefined : "当前角色不能使用 AI 助手"}
                  >
                    <Bot size={15} />
                    AI 助手
                  </button>
                  <ExportMenu
                    runId={report!.run_id}
                    productKey={product.key}
                    onError={(m) => notify(m, "error")}
                  />
                </>
              )}
              {can.admin && games.length > 0 && (
                <button
                  className="btn"
                  onClick={() => setSync({})}
                  disabled={!!busyJob}
                >
                  <RefreshCw size={15} />
                  同步数据
                </button>
              )}
              {session && (
                <button
                  className="user-chip"
                  onClick={() => setAccessOpen(true)}
                  title="切换身份"
                >
                  <UserRound size={15} />
                  {session.principal.name}
                  <span>
                    {ROLES[session.principal.role]?.label ??
                      session.principal.role}
                  </span>
                </button>
              )}
            </div>
          </header>

          {report && latestRunId && report.run_id !== latestRunId && (
            <div className="snapshot-notice">
              正在查看 {dateTime(report.as_of)} 的历史数据。
              <button
                className="link-button"
                onClick={() => state.viewSnapshot(null)}
              >
                回到最新数据
              </button>
            </div>
          )}

          <main className="content">
            {loading ? (
              <div className="page-loading">
                <Spinner label="正在加载" />
              </div>
            ) : loadError ? (
              <Empty
                title="无法连接分析服务"
                action={
                  <button className="btn" onClick={() => void load()}>
                    重试
                  </button>
                }
              >
                {loadError}
              </Empty>
            ) : route.page === "settings" ? (
              <SettingsPage tab={route.id} />
            ) : !game ? (
              <NoGames />
            ) : route.page === "follow-ups" ? (
              <FollowUps params={route.params} />
            ) : loadingSnapshot ? (
              <div className="page-loading">
                <Spinner label="正在加载" />
              </div>
            ) : !product ? (
              <NotSynced game={game} />
            ) : (
              dataPage && (
                <>
                  {route.page === "overview" && <Overview />}
                  {route.page === "issues" && <Issues selected={route.id} />}
                  {route.page === "releases" && (
                    <Releases selected={route.id} />
                  )}
                  {route.page === "feedback" && (
                    <Feedback params={route.params} />
                  )}
                </>
              )
            )}
          </main>
        </div>

        {/* Later overlays stack on top: feedback opened from a follow-up, a follow-up created from feedback. */}
        {followUpId && (
          <FollowUpDrawer id={followUpId} onClose={() => setFollowUpId(null)} />
        )}
        {evidence && (
          <EvidenceDrawer
            id={evidence.id}
            runId={evidence.runId}
            onClose={() => setEvidence(null)}
          />
        )}
        {creating && product && (
          <CreateFollowUp
            evidenceIds={creating.ids}
            title={creating.title}
            runId={creating.runId}
            onClose={() => setCreating(null)}
            onCreated={(item) => {
              setCreating(null);
              setEvidence(null);
              setFollowUps((list) => [item, ...list]);
              notify("已创建跟进：" + item.title);
              navigate(href("follow-ups", undefined, { open: item.id }));
            }}
          />
        )}
        {assistant && product && (
          <Assistant
            key={`${report!.run_id}-${product.key}`}
            context={assistant}
            onContext={setAssistant}
            onClose={() => setAssistant(null)}
          />
        )}
        {sync && (
          <SyncDialog
            games={games}
            initial={sync.keys}
            onClose={() => setSync(null)}
            onStarted={async (runId) => {
              setSync(null);
              setJob(await api.run(runId));
              setRuns(await api.runs());
            }}
          />
        )}
        {addingGame && (
          <AddGameDialog
            onClose={() => setAddingGame(false)}
            onAdded={(added) => {
              setAddingGame(false);
              setGames((list) => [...list, added]);
              selectGame(added.key);
              notify(`已添加 ${added.name}，同步后就能看到它的数据`);
              setSync({ keys: [added.key] });
            }}
          />
        )}
        {accessOpen && (
          <AccessDialog
            session={session}
            onClose={() => setAccessOpen(false)}
            onChanged={() => {
              setAccessOpen(false);
              setSnapshot(null);
              setAssistant(null);
              setLoading(true);
              void load();
            }}
          />
        )}
        {toast && (
          <div className={`toast ${toast.tone}`} role="status">
            {toast.message}
            <button
              className="icon-button"
              aria-label="关闭提示"
              onClick={() => setToast(null)}
            >
              ×
            </button>
          </div>
        )}
      </div>
    </AppContext.Provider>
  );
}

/** The game every page is about; switching here changes the whole console. */
function GameSwitcher() {
  const { games, game, can, selectGame, openAddGame } = useApp();
  const [open, setOpen] = useState(false);
  useDismiss(open, () => setOpen(false));
  if (!game)
    return can.admin ? (
      <button className="game-current add" onClick={openAddGame}>
        <Plus size={15} />
        添加要监控的游戏
      </button>
    ) : null;
  return (
    <div className="menu-anchor game-switcher">
      <button
        className="game-current"
        onClick={() => setOpen(!open)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span>
          <small>当前游戏</small>
          <b>{game.name}</b>
        </span>
        <ChevronsUpDown size={15} />
      </button>
      {open && (
        <div
          className="menu game-menu"
          role="listbox"
          onMouseDown={(e) => e.stopPropagation()}
        >
          {games.map((g) => (
            <button
              key={g.key}
              role="option"
              aria-selected={g.key === game.key}
              className={g.key === game.key ? "selected" : ""}
              onClick={() => {
                selectGame(g.key);
                setOpen(false);
              }}
            >
              <span>{g.name}</span>
              <small>
                {g.latest ? `${num(g.latest.reviews)} 条评论` : "还没有数据"}
              </small>
            </button>
          ))}
          <div className="menu-divider" />
          {can.admin && (
            <button
              onClick={() => {
                setOpen(false);
                openAddGame();
              }}
            >
              <span className="menu-action">
                <Plus size={14} />
                添加游戏
              </span>
            </button>
          )}
          <a
            className="menu-link"
            href={href("settings", "games")}
            onClick={() => setOpen(false)}
          >
            管理游戏
          </a>
        </div>
      )}
    </div>
  );
}

function NoGames() {
  const { can, openAddGame } = useApp();
  return (
    <Card>
      <Empty
        title="添加要监控的游戏"
        action={
          can.admin && (
            <button className="btn primary" onClick={openAddGame}>
              <Plus size={15} />
              添加游戏
            </button>
          )
        }
      >
        按名称在 Steam 上找到游戏后，GamePulse
        会定期抓取它的玩家评论；关联开发团队的 GitHub 仓库后，还会汇总公开 issue
        和版本发布记录。
        {!can.admin && " 请联系管理员添加游戏。"}
      </Empty>
    </Card>
  );
}

function NotSynced({ game }: { game: Game }) {
  const { can, busyJob, openSync } = useApp();
  return (
    <Card>
      <Empty
        title={`${game.name} 还没有数据`}
        action={
          can.admin && (
            <button
              className="btn primary"
              disabled={!!busyJob}
              onClick={() => openSync([game.key])}
            >
              <RefreshCw size={15} />
              {busyJob ? "正在同步…" : "同步数据"}
            </button>
          )
        }
      >
        同步会抓取 Steam 玩家评论
        {game.repo ? "、GitHub issue 和版本发布记录" : ""}
        ，通常需要几分钟。
        {!can.admin && " 请联系管理员同步数据。"}
      </Empty>
    </Card>
  );
}

function ExportMenu({
  runId,
  productKey,
  onError,
}: {
  runId: string;
  productKey: string;
  onError: (m: string) => void;
}) {
  const [open, setOpen] = useState(false);
  useDismiss(open, () => setOpen(false));
  const run = (path: string, name: string) => {
    setOpen(false);
    void download(path, name).catch((e) => onError(errorText(e)));
  };
  return (
    <div className="menu-anchor">
      <button
        className="btn"
        onClick={() => setOpen(!open)}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <Download size={15} />
        导出
      </button>
      {open && (
        <div
          className="menu align-right"
          role="menu"
          onMouseDown={(e) => e.stopPropagation()}
        >
          <button
            role="menuitem"
            onClick={() =>
              run(
                `/export?format=csv&run_id=${runId}&product=${productKey}`,
                `gamepulse-${productKey}-feedback.csv`,
              )
            }
          >
            <span>当前游戏的反馈明细</span>
            <small>CSV，可用 Excel 打开</small>
          </button>
          <button
            role="menuitem"
            onClick={() =>
              run(
                `/export?format=json&run_id=${runId}`,
                `gamepulse-report-${runId}.json`,
              )
            }
          >
            <span>完整分析报告</span>
            <small>JSON，含全部指标</small>
          </button>
        </div>
      )}
    </div>
  );
}

/** Closes a popup menu on the next click outside it. */
function useDismiss(open: boolean, close: () => void) {
  useEffect(() => {
    if (!open) return;
    const onDown = () => close();
    const timer = window.setTimeout(
      () => window.addEventListener("mousedown", onDown),
      0,
    );
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("mousedown", onDown);
    };
  }, [open, close]);
}
