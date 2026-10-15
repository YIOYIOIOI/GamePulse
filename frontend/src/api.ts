import type {
  Backup,
  EvidenceDetail,
  EvidencePage,
  FollowUp,
  FollowUpStatus,
  Game,
  GameSearchResult,
  Member,
  Report,
  Role,
  Run,
  Session,
} from "./types";

export const apiBase = import.meta.env.VITE_QUALITY_API || "/api/quality";

const TOKEN_KEY = "gamepulse-access";
const WORKSPACE_KEY = "gamepulse-workspace";

function headers(extra?: HeadersInit): Headers {
  const result = new Headers(extra);
  result.set("Content-Type", "application/json");
  const token = sessionStorage.getItem(TOKEN_KEY);
  const workspace = sessionStorage.getItem(WORKSPACE_KEY);
  if (token) result.set("Authorization", "Bearer " + token);
  if (workspace) result.set("X-Workspace-ID", workspace);
  return result;
}

/** Stores a team-mode token for this browser session only. An empty token signs out. */
export function setAccess(token: string, workspace: string) {
  if (token.trim()) sessionStorage.setItem(TOKEN_KEY, token.trim());
  else sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.setItem(WORKSPACE_KEY, workspace.trim() || "main");
}

export function currentWorkspace() {
  return sessionStorage.getItem(WORKSPACE_KEY) || "main";
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiBase + path, {
    ...init,
    headers: headers(init?.headers),
  });
  const body = await response.json().catch(() => undefined);
  if (!response.ok) {
    if (response.status === 401)
      window.dispatchEvent(new Event("gamepulse-auth-needed"));
    const detail =
      typeof body?.detail === "string"
        ? body.detail
        : `服务返回 HTTP ${response.status}`;
    throw new ApiError(detail, response.status);
  }
  if (body === undefined)
    throw new ApiError("服务没有返回数据", response.status);
  return body as T;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });

/** Downloads an authenticated export as a file. */
export async function download(path: string, filename: string) {
  const response = await fetch(apiBase + path, { headers: headers() });
  if (!response.ok)
    throw new ApiError("导出失败：HTTP " + response.status, response.status);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export interface EvidenceQuery {
  product: string;
  runId: string;
  source?: string;
  category?: string;
  language?: string;
  recommended?: string;
  search?: string;
  limit: number;
  offset: number;
}

export const api = {
  session: () => request<Session>("/access/session"),
  checkToken: async (token: string, workspace: string) => {
    const response = await fetch(apiBase + "/access/session", {
      headers: {
        Authorization: "Bearer " + token.trim(),
        "X-Workspace-ID": workspace.trim(),
      },
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok)
      throw new ApiError(body.detail || "身份验证失败", response.status);
    return body as Session;
  },
  /** A snapshot by id, or the newest one that collected the given game. */
  snapshot: (query: { runId?: string; game?: string }) =>
    request<{ status: string; report: Report | null }>(
      "/snapshot?" +
        new URLSearchParams(
          query.runId ? { run_id: query.runId } : { product: query.game || "" },
        ),
    ),
  runs: () => request<Run[]>("/runs"),
  run: (id: string) => request<Run>("/runs/" + encodeURIComponent(id)),
  sync: (products: string[], days: number) =>
    post<{ run_id: string }>("/sync", {
      products,
      days,
      max_reviews: 6000,
      max_issue_pages: 4,
    }),
  games: () => request<Game[]>("/games"),
  searchGames: (q: string) =>
    request<GameSearchResult[]>("/games/search?q=" + encodeURIComponent(q)),
  addGame: (app_id: number, repo: string) =>
    post<Game>("/games", { app_id, repo }),
  linkRepo: (key: string, repo: string) =>
    request<Game>("/games/" + encodeURIComponent(key), {
      method: "PATCH",
      body: JSON.stringify({ repo }),
    }),
  removeGame: (key: string) =>
    request<{ removed: string }>("/games/" + encodeURIComponent(key), {
      method: "DELETE",
    }),
  recompute: (runId: string) =>
    post<{ run_id: string }>("/replay/" + encodeURIComponent(runId)),
  evidence: (q: EvidenceQuery) => {
    const params = new URLSearchParams({
      product: q.product,
      run_id: q.runId,
      limit: String(q.limit),
      offset: String(q.offset),
    });
    for (const key of [
      "source",
      "category",
      "language",
      "recommended",
      "search",
    ] as const)
      if (q[key]) params.set(key, q[key]!);
    return request<EvidencePage>("/evidence?" + params);
  },
  evidenceDetail: (id: string, runId: string) =>
    request<EvidenceDetail>(
      "/evidence/" +
        encodeURIComponent(id) +
        "?run_id=" +
        encodeURIComponent(runId),
    ),
  followUps: () => request<FollowUp[]>("/triage"),
  createFollowUp: (body: {
    run_id: string;
    product: string;
    title: string;
    evidence_ids: string[];
    owner: string;
    note: string;
  }) => post<FollowUp>("/triage", body),
  updateFollowUp: (
    id: string,
    body: {
      revision: number;
      status: FollowUpStatus;
      owner: string;
      note: string;
    },
  ) =>
    request<FollowUp>("/triage/" + encodeURIComponent(id), {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  members: () => request<Member[]>("/access/identities"),
  addMember: (name: string, role: Role) =>
    post<Member & { token_file: string }>("/access/identities", { name, role }),
  revokeMember: (id: string) =>
    post<{ revoked: boolean }>(
      "/access/identities/" + encodeURIComponent(id) + "/revoke",
    ),
  backups: () => request<Backup[]>("/backups"),
  createBackup: () => post<Backup>("/backups"),
};

export { request, post };
