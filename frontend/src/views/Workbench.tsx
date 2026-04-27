import { useDataStore } from '../lib/useDataStore';
import { ShieldCheck, Crosshair, AlertTriangle, Lightbulb, Database } from 'lucide-react';
import clsx from 'clsx';

export function Workbench({ onChangeView }: { onChangeView: (v: string) => void }) {
  const { data, status } = useDataStore();

  if (status.totalRecords === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-8">
        <div className="w-16 h-16 bg-zinc-100 dark:bg-zinc-800 text-zinc-400 dark:text-zinc-300 rounded-2xl flex items-center justify-center mb-6 transition-colors">
          <Database className="w-8 h-8" />
        </div>
        <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mb-2">No Data Available</h2>
        <p className="text-zinc-500 dark:text-zinc-300 max-w-md mx-auto mb-8">
          The workbench requires player feedback to generate insights. Please connect to a data source to begin.
        </p>
        <button
          onClick={() => onChangeView('data-center')}
          className="bg-black dark:bg-white text-white dark:text-zinc-900 px-6 py-2.5 rounded-full font-medium hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors"
        >
          Go to Data Center
        </button>
      </div>
    );
  }

  const positiveReviews = data.filter(r => r.sentiment === 'positive').length;
  const negativeReviews = data.filter(r => r.sentiment === 'negative').length;
  const posRatio = data.length > 0 ? (positiveReviews / data.length) * 100 : 0;
  const negRatio = data.length > 0 ? (negativeReviews / data.length) * 100 : 0;

  const healthScore = Math.floor(posRatio * 0.8 + (status.totalRecords > 500 ? 20 : status.totalRecords / 25));

  // Generate actionable suggestions (mock logic based on actual parsed data)
  const suggestions = [];
  if (negRatio > 40) {
    suggestions.push({
      title: 'High Negative Community Sentiment',
      basis: `${negRatio.toFixed(1)}% of recent feedback is negative.`,
      action: 'Prioritize bug fixes or immediate communication regarding top issues.',
      risk: 'High churn if unaddressed.',
      type: 'danger'
    });
  } else if (posRatio > 70) {
    suggestions.push({
      title: 'Strong Positive Word of Mouth',
      basis: `${posRatio.toFixed(1)}% positive sentiment.`,
      action: 'Leverage momentum for community events or expansions.',
      risk: 'Monitor for sudden shifts from update fatigue.',
      type: 'success'
    });
  }

  // Find top negative topic
  const negTopics = data.filter(r => r.sentiment === 'negative').reduce((acc, curr) => {
    const t = curr.topic_description || 'General';
    acc[t] = (acc[t] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const topNegTopic = Object.entries(negTopics).sort((a: [string, unknown], b: [string, unknown]) => (b[1] as number) - (a[1] as number))[0];
  if (topNegTopic && (topNegTopic[1] as number) > (negativeReviews * 0.2)) {
    suggestions.push({
      title: `Critical Pain Point: ${topNegTopic[0]}`,
      basis: `${topNegTopic[1]} complaints directly mention this.`,
      action: `Review 'Touch Strategy' tool for template responses to ${topNegTopic[0]} issues.`,
      risk: 'Focusing on marketing while core issue persists will amplify backlash.',
      type: 'warning'
    });
  }

  if (suggestions.length === 0) {
    suggestions.push({
      title: 'Stable Operations',
      basis: 'No critical anomalies in sentiment structure.',
      action: 'Continue monitoring. Explore Player Segmentation for micro-optimizations.',
      risk: 'None currently.',
      type: 'info'
    });
  }

  return (
    <div className="py-12 px-8">
      <div className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50 mb-2">Workbench</h1>
        <p className="text-zinc-500 dark:text-zinc-300">Operational overview and actionable insights.</p>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-10">
        <div className="bg-white dark:bg-zinc-800 p-6 rounded-2xl border border-zinc-200 dark:border-zinc-700/50 shadow-sm transition-colors">
          <div className="text-xs text-zinc-500 dark:text-zinc-300 uppercase font-bold tracking-wider mb-2">Health Score</div>
          <div className="flex items-end gap-2">
            <span className={clsx("text-4xl font-light font-mono", healthScore > 70 ? "text-emerald-500" : healthScore > 40 ? "text-amber-500" : "text-red-500")}>
              {healthScore}
            </span>
            <span className="text-zinc-400 dark:text-zinc-300 font-mono mb-1">/100</span>
          </div>
        </div>
        <div className="bg-white dark:bg-zinc-800 p-6 rounded-2xl border border-zinc-200 dark:border-zinc-700/50 shadow-sm transition-colors">
          <div className="text-xs text-zinc-500 dark:text-zinc-300 uppercase font-bold tracking-wider mb-2">Positive Sentiment</div>
          <div className="text-4xl font-light font-mono text-zinc-900 dark:text-zinc-100">{posRatio.toFixed(1)}%</div>
          <div className="text-xs text-zinc-400 dark:text-zinc-300 mt-2">Based on {positiveReviews} reviews</div>
        </div>
        <div className="bg-white dark:bg-zinc-800 p-6 rounded-2xl border border-zinc-200 dark:border-zinc-700/50 shadow-sm transition-colors">
          <div className="text-xs text-zinc-500 dark:text-zinc-300 uppercase font-bold tracking-wider mb-2">Risk Factor</div>
          <div className="text-4xl font-light font-mono text-zinc-900 dark:text-zinc-100">{negRatio.toFixed(1)}%</div>
           <div className="text-xs text-zinc-400 dark:text-zinc-300 mt-2">Based on {negativeReviews} reviews</div>
        </div>
        <div className="bg-white dark:bg-zinc-800 p-6 rounded-2xl border border-zinc-200 dark:border-zinc-700/50 shadow-sm transition-colors">
          <div className="text-xs text-zinc-500 dark:text-zinc-300 uppercase font-bold tracking-wider mb-2">Games Tracked</div>
          <div className="flex items-end gap-2">
             <span className="text-4xl font-light font-mono text-zinc-900 dark:text-zinc-100">{status.gamesCount}</span>
          </div>
          {status.gamesCount > 1 && (
            <div className="text-xs text-blue-500 dark:text-blue-400 font-medium mt-2">Supports Competitor Analysis</div>
          )}
        </div>
      </div>

      <h2 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 mb-6">Actionable Suggestions</h2>

      <div className="space-y-4">
        {suggestions.map((s, i) => (
          <div key={i} className="bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700/50 rounded-xl p-5 flex gap-4 shadow-sm transition-colors">
             <div className="shrink-0 mt-1">
               {s.type === 'danger' && <AlertTriangle className="w-5 h-5 text-red-500" />}
               {s.type === 'warning' && <Crosshair className="w-5 h-5 text-amber-500" />}
               {s.type === 'success' && <ShieldCheck className="w-5 h-5 text-emerald-500" />}
               {s.type === 'info' && <Lightbulb className="w-5 h-5 text-blue-500" />}
             </div>
             <div className="flex-1">
               <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">{s.title}</h3>
               <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-3">
                 <div>
                   <div className="text-[10px] uppercase font-bold tracking-widest text-zinc-400 dark:text-zinc-300 mb-1">Data Basis</div>
                   <div className="text-sm text-zinc-700 dark:text-zinc-300">{s.basis}</div>
                 </div>
                 <div>
                   <div className="text-[10px] uppercase font-bold tracking-widest text-zinc-400 dark:text-zinc-300 mb-1">Recommended Action</div>
                   <div className="text-sm text-zinc-700 dark:text-zinc-300">{s.action}</div>
                 </div>
                 <div>
                   <div className="text-[10px] uppercase font-bold tracking-widest text-zinc-400 dark:text-zinc-300 mb-1">Risk / Notice</div>
                   <div className="text-sm text-zinc-700 dark:text-zinc-300">{s.risk}</div>
                 </div>
               </div>
             </div>
          </div>
        ))}
      </div>
    </div>
  );
}
