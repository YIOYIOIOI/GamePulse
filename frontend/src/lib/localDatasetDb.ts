import type { Review } from './useDataStore';

export type PersistedDataset = {
  version: 1;
  data: Review[];
  sources: string[];
  updatedAt: string;
};

const DB_NAME = 'gamepulse-local-db';
const STORE_NAME = 'datasets';
const CURRENT_KEY = 'current';
const LOCAL_STORAGE_FALLBACK_KEY = 'gamepulse.dataset.current.v1';

function reviveReview(row: Review): Review {
  return {
    ...row,
    timestamp_created: row.timestamp_created ? new Date(row.timestamp_created as unknown as string) : undefined,
  };
}

function normalizeDataset(payload: PersistedDataset): PersistedDataset {
  return {
    version: 1,
    data: Array.isArray(payload.data) ? payload.data.map(reviveReview) : [],
    sources: Array.isArray(payload.sources) ? payload.sources : [],
    updatedAt: payload.updatedAt || new Date().toISOString(),
  };
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined' || !window.indexedDB) {
      reject(new Error('IndexedDB unavailable'));
      return;
    }
    const request = window.indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) db.createObjectStore(STORE_NAME);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error('IndexedDB open failed'));
  });
}

async function withStore<T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, mode);
    const store = tx.objectStore(STORE_NAME);
    const request = run(store);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error('IndexedDB request failed'));
    tx.oncomplete = () => db.close();
    tx.onerror = () => {
      db.close();
      reject(tx.error || new Error('IndexedDB transaction failed'));
    };
  });
}

function saveFallback(payload: PersistedDataset) {
  try {
    window.localStorage.setItem(LOCAL_STORAGE_FALLBACK_KEY, JSON.stringify(payload));
  } catch {
    // Ignore fallback quota errors. IndexedDB is the primary persistence layer.
  }
}

function loadFallback(): PersistedDataset | null {
  try {
    const raw = window.localStorage.getItem(LOCAL_STORAGE_FALLBACK_KEY);
    if (!raw) return null;
    return normalizeDataset(JSON.parse(raw) as PersistedDataset);
  } catch {
    return null;
  }
}

export async function loadCurrentDataset(): Promise<PersistedDataset | null> {
  try {
    const payload = await withStore<PersistedDataset | undefined>('readonly', store => store.get(CURRENT_KEY));
    return payload ? normalizeDataset(payload) : loadFallback();
  } catch {
    return loadFallback();
  }
}

export async function saveCurrentDataset(data: Review[], sources: string[]): Promise<PersistedDataset> {
  const payload: PersistedDataset = { version: 1, data, sources, updatedAt: new Date().toISOString() };
  saveFallback(payload);
  try {
    await withStore<IDBValidKey>('readwrite', store => store.put(payload, CURRENT_KEY));
  } catch {
    // localStorage fallback already attempted.
  }
  return payload;
}

export async function clearCurrentDataset(): Promise<void> {
  try { window.localStorage.removeItem(LOCAL_STORAGE_FALLBACK_KEY); } catch { /* noop */ }
  try { await withStore<undefined>('readwrite', store => store.delete(CURRENT_KEY)); } catch { /* noop */ }
}
