import { useDataStore } from '../lib/useDataStore';
import { useTheme } from '../lib/useTheme';
import {
  Database,
  LayoutDashboard,
  Stethoscope,
  MessageSquareText,
  Users,
  Megaphone,
  Swords,
  Info,
  Moon,
  Sun
} from 'lucide-react';
import clsx from 'clsx';
import { ReactNode } from 'react';

interface SidebarProps {
  currentView: string;
  onViewChange: (view: string) => void;
}

export function Sidebar({ currentView, onViewChange }: SidebarProps) {
  const { status } = useDataStore();
  const { theme, setTheme } = useTheme();
  const hasData = status.totalRecords > 0;

  const navItems = [
    { id: 'data-center', label: 'Data Center', icon: Database, requiresData: false },
    { id: 'workbench', label: 'Workbench', icon: LayoutDashboard, requiresData: true },
    { id: 'health', label: 'Data Health', icon: Stethoscope, requiresData: true },
    { id: 'feedback', label: 'Feedback Analysis', icon: MessageSquareText, requiresData: true },
    { id: 'segmentation', label: 'Player Segmentation', icon: Users, requiresData: true },
    { id: 'strategy', label: 'Touch Strategy', icon: Megaphone, requiresData: true },
    { id: 'competitor', label: 'Competitor Analysis', icon: Swords, requiresData: true },
    { id: 'info', label: 'Analysis Boundaries', icon: Info, requiresData: false },
  ];

  return (
    <div className="w-64 bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-300 h-screen flex flex-col border-r border-zinc-200 dark:border-zinc-700/50 shrink-0 relative overflow-y-auto transition-colors">
      <div className="p-6">
        <div className="flex items-center gap-3 font-semibold text-xl text-zinc-900 dark:text-white mb-8 tracking-tight transition-colors">
          <div className="w-8 h-8 rounded-lg bg-orange-500 flex items-center justify-center shadow-[0_0_15px_rgba(249,115,22,0.3)]">
            <span className="text-white dark:text-zinc-950 text-lg">G</span>
          </div>
          GamePulse
        </div>

        <nav className="flex flex-col gap-1">
          <div className="text-xs uppercase tracking-widest text-zinc-500 font-semibold mb-3 px-3">Analytics Workflow</div>
          {navItems.map((item) => {
            const disabled = item.requiresData && !hasData;
            return (
              <button
                key={item.id}
                onClick={() => !disabled && onViewChange(item.id)}
                disabled={disabled}
                className={clsx(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-200 w-full text-left font-medium",
                  {
                    "bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-white": currentView === item.id,
                    "hover:bg-zinc-100/50 dark:hover:bg-zinc-800/50 hover:text-zinc-900 dark:hover:text-white": currentView !== item.id && !disabled,
                    "opacity-40 cursor-not-allowed": disabled
                  }
                )}
              >
                <item.icon className={clsx("w-4 h-4", currentView === item.id ? "text-orange-500" : "text-zinc-400")} />
                {item.label}
              </button>
            )
          })}
        </nav>
      </div>

      <div className="mt-auto p-6 border-t border-zinc-200 dark:border-zinc-700/50 transition-colors">
        <button
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          className="flex items-center gap-3 px-3 py-2.5 mb-4 rounded-lg text-sm transition-all duration-200 w-full text-left font-medium hover:bg-zinc-100 dark:hover:bg-zinc-800/50"
        >
          {theme === 'dark' ? (
            <>
              <Sun className="w-4 h-4 text-orange-500" />
              <span>Light Mode</span>
            </>
          ) : (
            <>
              <Moon className="w-4 h-4 text-zinc-500" />
              <span>Dark Mode</span>
            </>
          )}
        </button>

        <div className="bg-zinc-50 dark:bg-zinc-800 rounded-lg p-4 border border-zinc-200 dark:border-zinc-700/50/50 transition-colors">
          <div className="text-xs uppercase tracking-widest text-zinc-500 font-semibold mb-2">Active Dataset</div>
          {hasData ? (
             <div>
               <div className="text-2xl font-light text-zinc-900 dark:text-white mb-1 transition-colors">{status.totalRecords.toLocaleString()} <span className="text-xs text-zinc-400">Rows</span></div>
               <div className="flex items-center gap-2 mt-2">
                 <span className="inline-flex items-center text-xs px-2 py-0.5 rounded-full bg-zinc-200 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 font-mono transition-colors">
                    {status.gamesCount} Games
                 </span>
                 {status.isMerged && (
                   <span className="inline-flex items-center text-xs px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 font-mono transition-colors">
                      Merged
                   </span>
                 )}
               </div>
             </div>
          ) : (
             <div className="text-sm text-zinc-500">No data loaded.</div>
          )}
        </div>
      </div>
    </div>
  );
}

export function AppLayout({ children, currentView, onViewChange }: { children: ReactNode, currentView: string, onViewChange: (v: string) => void }) {
  return (
    <div className="flex h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 font-sans overflow-hidden transition-colors">
      <Sidebar currentView={currentView} onViewChange={onViewChange} />
      <main className="flex-1 overflow-y-auto w-full bg-zinc-50 dark:bg-zinc-950 transition-colors">
        <div className="max-w-6xl mx-auto min-h-screen">
          {children}
        </div>
      </main>
    </div>
  );
}
