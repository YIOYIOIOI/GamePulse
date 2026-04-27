export interface SteamFetchOptions {
  appId: string;
  gameName: string;
  count: number;
  language?: string;
  reviewType?: string;
}

export interface SteamAppSearchResult {
  app_id: number;
  name: string;
  price?: string | null;
  tiny_image?: string;
  metacritic_score?: number | null;
}

const API_BASE = import.meta.env.VITE_GAMEPULSE_API_BASE || 'http://127.0.0.1:8765';

export async function searchSteamApps(query: string): Promise<SteamAppSearchResult[]> {
  const q = query.trim();
  if (!q) return [];
  const res = await fetch(`${API_BASE}/api/steam/search?q=${encodeURIComponent(q)}&limit=12`);
  const payload = await res.json();
  if (!res.ok || payload.status?.ok === false) {
    throw new Error(payload.status?.message || 'Steam search failed');
  }
  return payload.results || [];
}

export async function fetchSteamReviews(options: SteamFetchOptions) {
  const res = await fetch(`${API_BASE}/api/steam/reviews`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      appId: options.appId,
      gameName: options.gameName,
      count: options.count,
      language: options.language || 'all',
      reviewType: options.reviewType || 'all',
    }),
  });
  const payload = await res.json();
  if (!res.ok || payload.status?.ok === false) {
    throw new Error(payload.status?.message || 'Steam review collection failed');
  }
  return payload.reviews || [];
}
