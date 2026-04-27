import { useDataStore } from '../lib/useDataStore';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, CartesianGrid, Tooltip as RTooltip, ScatterChart, Scatter, ZAxis } from 'recharts';
import clsx from 'clsx';
import { AlertCircle } from 'lucide-react';

export function PlayerSegmentation() {
  const { data } = useDataStore();

  const validData = data.filter(d => d.playtime_forever !== undefined && d.sentiment);

  if (validData.length === 0) {
    return (
      <div className="p-12 text-center">
        <AlertCircle className="w-8 h-8 text-zinc-400 dark:text-zinc-300 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-2">Insufficient Data</h2>
        <p className="text-zinc-500 dark:text-zinc-300 max-w-md mx-auto">Player segmentation requires "playtime_forever" and "sentiment" fields. Please connect a dataset that includes these fields.</p>
      </div>
    );
  }

  // Segment logic
  const segments = {
    'New Player': validData.filter(d => d.player_type === 'New Player'),
    'Regular Player': validData.filter(d => d.player_type === 'Regular Player'),
    'Core Player': validData.filter(d => d.player_type === 'Core Player'),
  };

  const segmentStats = Object.entries(segments).map(([name, groupData]) => {
    const total = groupData.length;
    const neg = groupData.filter(d => d.sentiment === 'negative').length;
    const avgPlaytime = groupData.reduce((acc, curr) => acc + (curr.playtime_forever || 0), 0) / (total || 1);

    // Calculate medians for proxies
    const avgRisk = groupData.reduce((acc, curr) => acc + (curr.churn_risk_proxy || 50), 0) / (total || 1);
    const avgVal = groupData.reduce((acc, curr) => acc + (curr.value_potential_score || 50), 0) / (total || 1);

    return {
      name,
      total,
      negRatio: total > 0 ? (neg / total) * 100 : 0,
      avgPlaytime: Math.floor(avgPlaytime),
      avgRisk: Math.floor(avgRisk),
      avgVal: Math.floor(avgVal),
    };
  }).filter(s => s.total > 0);

  // Scatter data (Proxy map) - sample up to 100 points
  const scatterData = [...validData].sort(() => 0.5 - Math.random()).slice(0, 100).map(d => ({
    x: d.value_potential_score || 50,
    y: d.churn_risk_proxy || 50,
    z: 1,
    sentiment: d.sentiment,
  }));

  return (
    <div className="py-12 px-8">
      <div className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 mb-2">Player Segmentation</h1>
        <p className="text-zinc-500 dark:text-zinc-300">Categorize players based on engagement and behavioral proxies.</p>

        <div className="mt-4 inline-block bg-blue-50 border border-blue-100 rounded-lg px-4 py-2">
          <p className="text-xs text-blue-800">
             <span className="font-bold">Important Context:</span> This module uses public reviews and playtime as proxies. Metrics below are <span className="underline">not</span> true internal LTV or exact retention models.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">

        {/* Value vs Risk Matrix */}
        <div className="bg-white dark:bg-zinc-800 rounded-2xl p-6 shadow-sm border border-zinc-200 dark:border-zinc-700/50">
           <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-300 mb-2">Value & Risk Matrix (Proxy)</h2>
           <p className="text-xs text-zinc-400 dark:text-zinc-300 mb-6">X: Active Value | Y: Churn Risk Proxy | Color: Sentiment</p>

           <div className="h-[300px]">
             <ResponsiveContainer width="100%" height="100%">
               <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                 <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f4f4f5" />
                 <XAxis type="number" dataKey="x" name="Value Proxy" domain={[0, 100]} tick={{fontSize: 12, fill: '#a1a1aa'}} axisLine={false} tickLine={false} />
                 <YAxis type="number" dataKey="y" name="Risk Proxy" domain={[0, 100]} tick={{fontSize: 12, fill: '#a1a1aa'}} axisLine={false} tickLine={false} />
                 <ZAxis type="number" dataKey="z" range={[40, 40]} />
                 <RTooltip cursor={{strokeDasharray: '3 3'}} contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
                 <Scatter
                   name="Positive"
                   data={scatterData.filter(d => d.sentiment === 'positive')}
                   fill="#10b981"
                   fillOpacity={0.6}
                 />
                 <Scatter
                   name="Negative"
                   data={scatterData.filter(d => d.sentiment === 'negative')}
                   fill="#ef4444"
                   fillOpacity={0.6}
                 />
               </ScatterChart>
             </ResponsiveContainer>
           </div>
        </div>

        {/* Segment Breakdown */}
        <div className="bg-white dark:bg-zinc-800 rounded-2xl p-6 shadow-sm border border-zinc-200 dark:border-zinc-700/50">
           <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-300 mb-6">Segment Analysis</h2>

           <div className="space-y-6">
              {segmentStats.map(s => (
                <div key={s.name} className="flex flex-col">
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-semibold text-zinc-900 dark:text-zinc-100">{s.name}</span>
                    <span className="text-xs font-mono text-zinc-500 dark:text-zinc-300">{s.total} users</span>
                  </div>

                  <div className="flex gap-4">
                    <div className="flex-1 bg-zinc-50 dark:bg-zinc-800 p-2 rounded-lg border border-zinc-100 dark:border-zinc-700/50/50">
                       <div className="text-[10px] uppercase text-zinc-400 dark:text-zinc-300 font-bold mb-1">Avg Playtime</div>
                       <div className="font-mono text-zinc-700 dark:text-zinc-300">{s.avgPlaytime}h</div>
                    </div>
                    <div className="flex-1 bg-zinc-50 dark:bg-zinc-800 p-2 rounded-lg border border-zinc-100 dark:border-zinc-700/50/50">
                       <div className="text-[10px] uppercase text-zinc-400 dark:text-zinc-300 font-bold mb-1">Negative Ratio</div>
                       <div className={clsx("font-mono", s.negRatio > 40 ? "text-red-500" : "text-emerald-500")}>
                         {s.negRatio.toFixed(1)}%
                       </div>
                    </div>
                    <div className="flex-1 bg-zinc-50 dark:bg-zinc-800 p-2 rounded-lg border border-zinc-100 dark:border-zinc-700/50/50">
                       <div className="text-[10px] uppercase text-zinc-400 dark:text-zinc-300 font-bold mb-1">CRM Priority</div>
                       <div className="font-mono text-blue-600">
                         {s.avgRisk > 60 || s.avgVal > 70 ? 'High' : 'Normal'}
                       </div>
                    </div>
                  </div>
                </div>
              ))}
           </div>
        </div>

      </div>
    </div>
  );
}
