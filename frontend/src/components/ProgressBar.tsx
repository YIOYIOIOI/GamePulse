export type ProgressState = {
  label: string;
  value: number;
} | null;

export function ProgressBar({ progress }: { progress: ProgressState }) {
  if (!progress) return null;
  return (
    <div className="mt-3 rounded-2xl border border-orange-200/70 dark:border-orange-900/40 bg-gradient-to-br from-orange-50 to-amber-50 dark:from-orange-950/20 dark:to-zinc-900 px-3 py-2 shadow-sm">
      <div className="flex items-center justify-between text-xs mb-2 gap-4">
        <span className="font-medium text-orange-800 dark:text-orange-200 truncate">{progress.label}</span>
        <span className="font-mono text-orange-700 dark:text-orange-300 shrink-0">{Math.round(progress.value)}%</span>
      </div>
      <div className="h-2 rounded-full bg-orange-100 dark:bg-orange-900/40 overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-orange-500 via-amber-500 to-stone-700 transition-all duration-300 ease-out"
          style={{ width: `${Math.min(100, Math.max(0, progress.value))}%` }}
        />
      </div>
    </div>
  );
}
