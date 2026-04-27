import { createContext, useContext, useState, ReactNode } from 'react';

// Data types based on requirements
export interface Review {
  review_text: string;
  sentiment: 'positive' | 'negative' | 'neutral';
  game_name: string;
  topic_description?: string;
  player_type?: string;
  playtime_forever?: number;
  timestamp_created?: Date;
  // Derived fields
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
  clearData: () => void;
}

const DataContext = createContext<DataContextType | undefined>(undefined);

export function DataProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<Review[]>([]);
  const [sources, setSources] = useState<string[]>([]);

  const appendData = (newData: Review[], sourceName: string) => {
    setData((prev) => [...prev, ...newData]);
    if (!sources.includes(sourceName)) {
      setSources((prev) => [...prev, sourceName]);
    }
  };

  const clearData = () => {
    setData([]);
    setSources([]);
  };

  const games: string[] = Array.from(new Set(data.map((r) => r.game_name)));

  const gameStats = games.reduce((acc, game) => {
    acc[game] = {
      count: data.filter((r) => r.game_name === game).length,
      source: 'Mixed', // simplification
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
    <DataContext.Provider value={{ data, status, appendData, clearData }}>
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
