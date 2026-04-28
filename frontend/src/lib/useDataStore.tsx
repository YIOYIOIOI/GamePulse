import { createContext, useContext, useEffect, useMemo, useState, ReactNode } from 'react';

export interface Review {
  review_text: string;
  sentiment: 'positive' | 'negative' | 'neutral';
  game_name: string;
  topic_description?: string;
  player_type?: string;
  playtime_forever?: number;
  timestamp_created?: Date;
  topic_source?: string;
  value_potential_score?: number;
  churn_risk_proxy?: number;
  crm_priority?: 'High' | 'Medium' | 'Low';
}

export interface DatasetStatus {
  totalRecords: number;
  gamesCount: number;
  dataSources: string[];
  isMerged: boolean;
  gameStats: Record<string, { count: number; source: string }>;
}

interface DataContextType {
  data: Review[];
  status: DatasetStatus;
  appendData: (newData: Review[], sourceName: string) => void;
  replaceData: (nextData: Review[], sourceName?: string) => void;
  clearData: () => void;
  cacheInfo: { restored: boolean; updatedAt?: string; rows: number };
}

type PersistedDataset = { version: 1; data: Review[]; sources: string[]; updatedAt: string };
const DATASET_STORAGE_KEY = 'gamepulse.dataset.current.v1';

function reviveReview(row: Review): Review {
  return {
    ...row,
    timestamp_created: row.timestamp_created ? new Date(row.timestamp_created as unknown as string) : undefined,
  };
}

function loadPersistedDataset(): PersistedDataset | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(DATASET_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PersistedDataset;
    if (!Array.isArray(parsed.data)) return null;
    return {
      version: 1,
      data: parsed.data.map(reviveReview),
      sources: Array.isArray(parsed.sources) ? parsed.sources : [],
      updatedAt: parsed.updatedAt || new Date().toISOString(),
    };
  } catch {
    return null;
  }
}

function savePersistedDataset(data: Review[], sources: string[]) {
  if (typeof window === 'undefined') return;
  try {
    const payload: PersistedDataset = { version: 1, data, sources, updatedAt: new Date().toISOString() };
    window.localStorage.setItem(DATASET_STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // localStorage may be full or disabled; keep in-memory data usable.
  }
}

function clearPersistedDataset() {
  if (typeof window === 'undefined') return;
  try { window.localStorage.removeItem(DATASET_STORAGE_KEY); } catch { /* noop */ }
}

const DataContext = createContext<DataContextType | undefined>(undefined);

export function DataProvider({ children }: { children: ReactNode }) {
  const initial = useMemo(() => loadPersistedDataset(), []);
  const [data, setData] = useState<Review[]>(() => initial?.data || []);
  const [sources, setSources] = useState<string[]>(() => initial?.sources || []);
  const [cacheInfo, setCacheInfo] = useState(() => ({ restored: Boolean(initial?.data?.length), updatedAt: initial?.updatedAt, rows: initial?.data?.length || 0 }));

  useEffect(() => {
    if (data.length === 0 && sources.length === 0) return;
    savePersistedDataset(data, sources);
    setCacheInfo({ restored: cacheInfo.restored, updatedAt: new Date().toISOString(), rows: data.length });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, sources]);

  const appendData = (newData: Review[], sourceName: string) => {
    setData((prev) => [...prev, ...newData]);
    setSources((prev) => prev.includes(sourceName) ? prev : [...prev, sourceName]);
  };

  const replaceData = (nextData: Review[], sourceName?: string) => {
    setData(nextData);
    if (sourceName) setSources((prev) => prev.includes(sourceName) ? prev : [...prev, sourceName]);
  };

  const clearData = () => {
    setData([]);
    setSources([]);
    clearPersistedDataset();
    setCacheInfo({ restored: false, updatedAt: undefined, rows: 0 });
  };

  const games: string[] = Array.from(new Set(data.map((r) => r.game_name)));

  const gameStats = games.reduce((acc, game) => {
    acc[game] = {
      count: data.filter((r) => r.game_name === game).length,
      source: 'Mixed',
    };
    return acc;
  }, {} as Record<string, { count: number; source: string }>);

  const status: DatasetStatus = {
    totalRecords: data.length,
    gamesCount: games.length,
    dataSources: sources,
    isMerged: sources.length > 1 || games.length > 1,
    gameStats,
  };

  return (
    <DataContext.Provider value={{ data, status, appendData, replaceData, clearData, cacheInfo }}>
      {children}
    </DataContext.Provider>
  );
}

export function useDataStore() {
  const context = useContext(DataContext);
  if (context === undefined) {
    throw new Error('useDataStore must be used within a DataProvider');
  }
  return context;
}
