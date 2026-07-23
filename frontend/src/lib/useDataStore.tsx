import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { clearCurrentDataset, loadCurrentDataset, saveCurrentDataset } from './localDatasetDb';
import { fetchAnalysisPackage, isEngineAvailable } from './analysisApi';

/** Python 引擎 /api/analyze 的质量评估（src/analysis/product_metrics.py DataQualityResult） */
export interface EngineQuality {
  sample_size: number;
  date_span_days: number | null;
  games_count: number;
  has_sentiment: boolean;
  has_topics: boolean;
  has_player_type: boolean;
  has_playtime: boolean;
  grade: string;
  supported_modules: string[];
  limitations: string[];
}

export interface EngineGate {
  enabled: boolean;
  reason: string;
}

/** /api/analyze 返回的统一分析包（引擎口径，与 CLI 批处理同一事实源） */
export interface EnginePackage {
  quality: EngineQuality;
  summary?: Record<string, unknown>;
  gates: Record<string, EngineGate>;
  field_status: Record<string, boolean>;
  next_steps: string[];
  actions?: unknown[];
  campaign_cards?: unknown[];
  competitors?: unknown[];
  top_topics?: Record<string, number>;
  sentiment_counts?: Record<string, number>;
}

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
  cacheInfo: { restored: boolean; loading: boolean; updatedAt?: string; rows: number; backend: 'IndexedDB' | 'localStorage'; };
  /** 引擎分析包：数据集变化后自动从 /api/analyze 获取；引擎不可用时为 null（各页面本地降级） */
  enginePackage: EnginePackage | null;
}

const DataContext = createContext<DataContextType | undefined>(undefined);

export function DataProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<Review[]>([]);
  const [sources, setSources] = useState<string[]>([]);
  const [cacheInfo, setCacheInfo] = useState<{ restored: boolean; loading: boolean; updatedAt?: string; rows: number; backend: 'IndexedDB' | 'localStorage'; }>(
    { restored: false, loading: true, rows: 0, backend: 'IndexedDB' }
  );

  useEffect(() => {
    let cancelled = false;
    loadCurrentDataset().then(payload => {
      if (cancelled) return;
      if (payload?.data?.length) {
        setData(payload.data);
        setSources(payload.sources);
        setCacheInfo({ restored: true, loading: false, updatedAt: payload.updatedAt, rows: payload.data.length, backend: 'IndexedDB' });
      } else {
        setCacheInfo(prev => ({ ...prev, loading: false }));
      }
    });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (cacheInfo.loading) return;
    if (data.length === 0 && sources.length === 0) return;
    let cancelled = false;
    saveCurrentDataset(data, sources).then(payload => {
      if (cancelled) return;
      setCacheInfo(prev => ({ ...prev, restored: prev.restored, loading: false, updatedAt: payload.updatedAt, rows: data.length, backend: 'IndexedDB' }));
    });
    return () => { cancelled = true; };
  }, [data, sources, cacheInfo.loading]);

  // 引擎口径统一：数据集变化后（防抖 800ms）调 /api/analyze light，
  // 让工作台/健康检查等页面消费与 CLI 批处理同一事实源的分析包；引擎不在时保持 null 降级本地
  const [enginePackage, setEnginePackage] = useState<EnginePackage | null>(null);
  useEffect(() => {
    if (cacheInfo.loading) return;
    if (data.length === 0) {
      setEnginePackage(null);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        if (!(await isEngineAvailable())) return;
        const pkg = await fetchAnalysisPackage<EnginePackage>(data);
        if (!cancelled) setEnginePackage(pkg);
      } catch {
        if (!cancelled) setEnginePackage(null);
      }
    }, 800);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [data, cacheInfo.loading]);

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
    clearCurrentDataset();
    setCacheInfo({ restored: false, loading: false, updatedAt: undefined, rows: 0, backend: 'IndexedDB' });
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
    <DataContext.Provider value={{ data, status, appendData, replaceData, clearData, cacheInfo, enginePackage }}>
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
