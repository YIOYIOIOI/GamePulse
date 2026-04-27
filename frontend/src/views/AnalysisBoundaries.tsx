import { AlertTriangle, CheckCircle, Crosshair, XCircle, Info } from 'lucide-react';

export function AnalysisBoundaries() {
  return (
    <div className="py-12 px-8 max-w-4xl">
      <div className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 mb-2">Analysis Boundaries & Limitations</h1>
        <p className="text-zinc-500 dark:text-zinc-300">Methodological guidelines on what public review data can and cannot support.</p>
      </div>

      <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-5 mb-8 flex gap-4">
        <AlertTriangle className="w-6 h-6 text-yellow-600 shrink-0 mt-0.5" />
        <div>
          <h3 className="font-semibold text-yellow-900 mb-1">Core Principle</h3>
          <p className="text-sm text-yellow-800 leading-relaxed">
            Public reviews are an <span className="font-bold">input</span> for operational decisions, not a complete source of truth. They suffer from survival bias, extreme-opinion bias, and lack financial context. Never substitute internal telemetry with scraped comment metrics.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">

        {/* Can do */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle className="w-5 h-5 text-emerald-500" />
            <h2 className="font-bold text-lg text-zinc-900 dark:text-zinc-100">Supported by Public Data</h2>
          </div>
          <ul className="space-y-4">
            {[
              { title: 'Sentiment Structure', desc: 'Ratio of positive vs negative feedback among vocal players.' },
              { title: 'Pain Point Ranking', desc: 'Identifying which bugs or features cause the most visible friction.' },
              { title: 'High-Level Topic Clustering', desc: 'Grouping complaints into structural categories (e.g., Matchmaking vs Performance).' },
              { title: 'Playtime Proxy Segmentation', desc: 'Categorizing commenters by their self-reported or platform-recorded hours.' },
              { title: 'Competitor Sentiment Gaps', desc: 'Comparing public reception of similar titles.' },
              { title: 'CRM Strategy Drafting', desc: 'Creating communication templates tailored to specific community grievances.' }
            ].map((item, i) => (
              <li key={i} className="flex gap-3 relative">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-2 shrink-0"></div>
                <div>
                  <div className="font-semibold text-sm text-zinc-800 dark:text-zinc-200">{item.title}</div>
                  <div className="text-xs text-zinc-500 dark:text-zinc-300 mt-0.5">{item.desc}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>

        {/* Cannot do */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <XCircle className="w-5 h-5 text-red-500" />
            <h2 className="font-bold text-lg text-zinc-900 dark:text-zinc-100">Requires Internal Data</h2>
          </div>
          <ul className="space-y-4">
            {[
              { title: 'True LTV (Lifetime Value)', desc: 'Requires actual transaction and payment gateway logs.' },
              { title: 'Real Retention / Churn Rates', desc: 'Requires server login logs and session lengths. Commenters are a fraction of the DAU.' },
              { title: 'Conversion Metrics', desc: 'Cannot track funnel success (e.g., Impressions -> Install -> Purchase) from reviews.' },
              { title: 'Event ROI', desc: 'Cannot determine if an in-game event was profitable, only if it was liked.' },
              { title: 'Precise Lifecycle Modeling', desc: 'Requires deep chronological telemetry tracking per user.' }
            ].map((item, i) => (
              <li key={i} className="flex gap-3 relative">
                <div className="w-1.5 h-1.5 rounded-full bg-red-500 mt-2 shrink-0"></div>
                <div>
                  <div className="font-semibold text-sm text-zinc-800 dark:text-zinc-200">{item.title}</div>
                  <div className="text-xs text-zinc-500 dark:text-zinc-300 mt-0.5">{item.desc}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>

      </div>

      <div className="bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700/50 rounded-xl p-6">
        <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
          <Crosshair className="w-4 h-4 text-zinc-400 dark:text-zinc-300" />
          Product Degradation Rules
        </h3>
        <p className="text-sm text-zinc-600 dark:text-zinc-300 mb-4">
          GamePulse enforces strict analytical downgrades when data quality is insufficient:
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div className="bg-white dark:bg-zinc-800 p-3 border border-zinc-100 dark:border-zinc-700/50/50 rounded-lg shadow-sm">
            <span className="font-mono text-xs bg-zinc-100 dark:bg-zinc-800 px-1 py-0.5 rounded mr-2">n &lt; 300</span>
            No trend mapping. Descriptive only.
          </div>
          <div className="bg-white dark:bg-zinc-800 p-3 border border-zinc-100 dark:border-zinc-700/50/50 rounded-lg shadow-sm">
             <span className="font-mono text-xs bg-zinc-100 dark:bg-zinc-800 px-1 py-0.5 rounded mr-2">&lt; 14 Days</span>
            Time series forecasting disabled.
          </div>
          <div className="bg-white dark:bg-zinc-800 p-3 border border-zinc-100 dark:border-zinc-700/50/50 rounded-lg shadow-sm">
            <span className="font-mono text-xs bg-zinc-100 dark:bg-zinc-800 px-1 py-0.5 rounded mr-2">Tags Gen</span>
            Auto-topics flagged as "Keyword Categorization"
          </div>
          <div className="bg-white dark:bg-zinc-800 p-3 border border-zinc-100 dark:border-zinc-700/50/50 rounded-lg shadow-sm">
            <span className="font-mono text-xs bg-zinc-100 dark:bg-zinc-800 px-1 py-0.5 rounded mr-2">No Playtime</span>
            Segmentation module disabled entirely.
          </div>
        </div>
      </div>
    </div>
  );
}
