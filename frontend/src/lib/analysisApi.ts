// 后端分析引擎客户端：让前端复用 Python 引擎的口径（单一事实源），
// 后端不可达时由调用方降级到本地 TS 计算（dataProcessor.ts）。
//
// 端点由 scripts/gamepulse_api_server.py 提供：
//   POST /api/analyze                         -> 完整分析包（质量门槛/gates/行动建议）
//   POST /api/analysis/segments               -> KMeans 玩家分层（口径元数据 + 可选行级标签）
//   POST /api/analysis/sentiment-eval         -> 情感 vs vote_up 弱标签一致性评测
//   POST /api/analysis/language-distribution  -> 语言分布

const API_BASE = import.meta.env.VITE_GAMEPULSE_API_BASE || 'http://127.0.0.1:8765';

export interface SegmentProfile {
  n: number;
  share: number;
  avg_playtime_hours: number;
  avg_votes_up: number | null;
  avg_review_length: number | null;
}

export interface SegmentMeta {
  method: 'kmeans_multifeature' | 'playtime_cut_fallback';
  k: number;
  silhouette?: number;
  features?: string[];
  scaling?: string;
  k_selection?: string;
  random_state?: number;
  reason?: string; // fallback 时的降级原因
  note?: string;
  cluster_profiles?: Record<string, SegmentProfile>;
}

export interface SentimentEvalMetrics {
  n: number;
  agreement: number;
  precision_pos: number;
  recall_pos: number;
  f1_pos: number;
}

export interface SentimentEvaluation {
  overall: SentimentEvalMetrics;
  by_language: Record<string, SentimentEvalMetrics>;
  non_english_overall?: SentimentEvalMetrics;
  en_minus_non_en_agreement?: number;
  caveats: string[];
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} -> HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

/** 后端引擎是否可用（用于优雅降级到本地 TS 计算）。 */
export async function isEngineAvailable(timeoutMs = 1200): Promise<boolean> {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const res = await fetch(`${API_BASE}/api/health`, { signal: controller.signal });
    clearTimeout(timer);
    return res.ok;
  } catch {
    return false;
  }
}

export async function fetchSegments(rows: unknown[]): Promise<SegmentMeta> {
  const data = await post<{ ok: boolean; meta: SegmentMeta }>('/api/analysis/segments', { reviews: rows });
  return data.meta;
}

export async function fetchSentimentEvaluation(rows: unknown[]): Promise<SentimentEvaluation> {
  const data = await post<{ ok: boolean; evaluation: SentimentEvaluation }>(
    '/api/analysis/sentiment-eval',
    { reviews: rows },
  );
  return data.evaluation;
}

export async function fetchAnalysisPackage<T = unknown>(rows: unknown[]): Promise<T> {
  const data = await post<{ ok: boolean; package: T }>('/api/analyze', { reviews: rows });
  return data.package;
}
