import { createContext, useContext } from "react";
import type {
  FollowUp,
  Game,
  ProductReport,
  Report,
  Run,
  Session,
} from "./types";

export interface AssistantContext {
  scope: "overview" | "monitor" | "release" | "evidence" | "category";
  /** Shown in the panel header, e.g. "版本 v160.5". */
  label: string;
  release_id?: string;
  category?: string;
  evidence_ids?: string[];
  question?: string;
}

export interface AppState {
  games: Game[];
  /** The game chosen in the sidebar; null until a game is added. */
  game: Game | null;
  /** The snapshot on screen; null before the first sync. */
  report: Report | null;
  /** The chosen game's data in that snapshot; null until the game is synced. */
  product: ProductReport | null;
  /** Newest completed snapshot; differs from report.run_id while an older one is open. */
  latestRunId: string | null;
  runs: Run[];
  followUps: FollowUp[];
  session: Session | null;
  can: { analyze: boolean; review: boolean; admin: boolean };
  busyJob: Run | null;
  selectGame: (key: string) => void;
  refreshGames: () => Promise<void>;
  viewSnapshot: (runId: string | null) => void;
  showEvidence: (id: string, runId?: string) => void;
  showFollowUp: (id: string) => void;
  openAssistant: (context: AssistantContext) => void;
  createFollowUp: (
    evidenceIds: string[],
    title?: string,
    runId?: string,
  ) => void;
  refreshFollowUps: () => Promise<void>;
  startJob: (runId: string) => Promise<void>;
  /** Opens the sync dialog, optionally with only these games ticked. */
  openSync: (keys?: string[]) => void;
  openAddGame: () => void;
  notify: (message: string, tone?: "error" | "info") => void;
}

export const AppContext = createContext<AppState | null>(null);

export function useApp(): AppState {
  const value = useContext(AppContext);
  if (!value) throw new Error("useApp must be used inside AppContext");
  return value;
}

/** For pages that show the chosen game's data; App renders them only once that data exists. */
export function useData() {
  const app = useApp();
  if (!app.report || !app.product || !app.game)
    throw new Error("useData needs a synced game");
  return { ...app, report: app.report, product: app.product, game: app.game };
}
