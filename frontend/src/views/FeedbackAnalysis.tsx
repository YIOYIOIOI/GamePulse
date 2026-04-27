import { useDataStore } from '../lib/useDataStore';
import { PieChart, Pie, Cell, Tooltip as RTooltip, BarChart, Bar, XAxis, YAxis, ResponsiveContainer, CartesianGrid } from 'recharts';
import { useState } from 'react';
import clsx from 'clsx';
import { differenceInDays, format } from 'date-fns';

export function FeedbackAnalysis() {
  const { data } = useDataStore();
  const [filterMode, setFilterMode] = useState<'all' | 'negative' | 'positive'>('all');

  const filteredData = data.filter(d => filterMode === 'all' ? true : d.sentiment === filterMode);

  // Sentiment data
  const posCount = data.filter(d => d.sentiment === 'positive').length;
  const negCount = data.filter(d => d.sentiment === 'negative').length;
  const sentimentData = [
    { name: 'Positive', value: posCount, color: '#10b981' },
    { name: 'Negative', value: negCount, color: '#ef4444' },
  ].filter(d => d.value > 0);

  // Topic data
  const topicCounts = filteredData.reduce((acc, curr) => {
    const t = curr.topic_description || 'Uncategorized';
    acc[t] = (acc[t] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const topicChartData = Object.entries(topicCounts)
    .sort((a: [string, number], b: [string, number]) => b[1] - a[1])
    .slice(0, 6)
    .map(([name, count]) => ({
      name: name.length > 15 ? name.substring(0, 15) + '...' : name,
      fullName: name,
      count
    }));

  // Top recent reviews for table
  const recentReviews = [...filteredData]
    .sort((a, b) => (b.timestamp_created?.getTime() || 0) - (a.timestamp_created?.getTime() || 0))
    .slice(0, 10);

  if (data.length === 0 || (!posCount && !negCount)) {
    return <div className="p-8 text-zinc-500 dark:text-zinc-300">Not enough data for feedback analysis.</div>;
  }

  return (
    <div className="py-12 px-8">
      <div className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 mb-2">Feedback Analysis</h1>
        <p className="text-zinc-500 dark:text-zinc-300">Understand what players are saying and locate primary pain points.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">

        {/* Sentiment Structure */}
        <div className="bg-white dark:bg-zinc-800 rounded-2xl p-6 shadow-sm border border-zinc-200 dark:border-zinc-700/50">
           <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-300 mb-6">Word of Mouth</h2>
           <div className="h-64 relative">
             <ResponsiveContainer width="100%" height="100%">
               <PieChart>
                 <Pie
                   data={sentimentData}
                   innerRadius={60}
                   outerRadius={80}
                   paddingAngle={5}
                   dataKey="value"
                 >
                   {sentimentData.map((entry, index) => (
                     <Cell key={`cell-${index}`} fill={entry.color} />
                   ))}
                 </Pie>
                 <RTooltip
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                 />
               </PieChart>
             </ResponsiveContainer>
             <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-3xl font-light font-mono">{((posCount / (posCount+negCount)) * 100).toFixed(0)}%</span>
                <span className="text-[10px] uppercase text-zinc-400 dark:text-zinc-300 font-bold tracking-widest mt-1">Positive</span>
             </div>
           </div>
        </div>

        {/* High Frequency Topics */}
        <div className="bg-white dark:bg-zinc-800 rounded-2xl p-6 shadow-sm border border-zinc-200 dark:border-zinc-700/50 md:col-span-2">
           <div className="flex justify-between items-center mb-6">
             <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-300">High Frequency Topics</h2>
             <div className="flex gap-2">
               {(['all', 'negative', 'positive'] as const).map(mode => (
                 <button
                   key={mode}
                   onClick={() => setFilterMode(mode)}
                   className={clsx(
                     "px-3 py-1 pb-1.5 text-xs font-semibold uppercase tracking-wider rounded-md transition-colors",
                     filterMode === mode ? "bg-zinc-900 text-white dark:text-zinc-900" : "bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-300 hover:bg-zinc-200"
                   )}
                 >
                   {mode}
                 </button>
               ))}
             </div>
           </div>

           <div className="h-64">
             {topicChartData.length > 0 ? (
               <ResponsiveContainer width="100%" height="100%">
                 <BarChart data={topicChartData} layout="vertical" margin={{ left: 20 }}>
                   <CartesianGrid strokeDasharray="3 3" horizontal={false} vertical={true} stroke="#f4f4f5" />
                   <XAxis type="number" hide />
                   <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fill: '#71717a', fontSize: 12 }} />
                   <RTooltip
                      cursor={{fill: '#f4f4f5'}}
                      contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                   />
                   <Bar dataKey="count" fill={filterMode === 'negative' ? '#ef4444' : filterMode === 'positive' ? '#10b981' : '#3f3f46'} radius={[0, 4, 4, 0]} barSize={24} />
                 </BarChart>
               </ResponsiveContainer>
             ) : (
                <div className="h-full flex items-center justify-center text-zinc-400 dark:text-zinc-300 text-sm">No topics extracted.</div>
             )}
           </div>
        </div>
      </div>

      {/* Verbatims */}
      <div className="bg-white dark:bg-zinc-800 rounded-2xl border border-zinc-200 dark:border-zinc-700/50 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-zinc-100 dark:border-zinc-700/50/50">
          <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-300">Latest Review Samples</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead className="bg-zinc-50 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-300 border-b border-zinc-100 dark:border-zinc-700/50/50">
              <tr>
                <th className="px-6 py-3 font-semibold w-32">Config</th>
                <th className="px-6 py-3 font-semibold w-48">Topic</th>
                <th className="px-6 py-3 font-semibold min-w-[300px]">Review Verbatim</th>
                <th className="px-6 py-3 font-semibold w-32">Playtime</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {recentReviews.map((r, i) => (
                <tr key={i} className="hover:bg-zinc-50 dark:bg-zinc-800 transition-colors">
                  <td className="px-6 py-4">
                    <span className={clsx(
                      "inline-flex px-2 py-0.5 rounded-full text-xs font-medium",
                      r.sentiment === 'positive' ? "bg-emerald-100 text-emerald-700" :
                      r.sentiment === 'negative' ? "bg-red-100 text-red-700" : "bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300"
                    )}>
                      {r.sentiment || 'Unknown'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-zinc-600 dark:text-zinc-300 truncate max-w-[200px]">
                    {r.topic_description || '-'}
                  </td>
                  <td className="px-6 py-4 text-zinc-900 dark:text-zinc-100 whitespace-normal min-w-[300px]">
                    <div className="line-clamp-2">{r.review_text}</div>
                  </td>
                  <td className="px-6 py-4 text-zinc-500 dark:text-zinc-300 font-mono text-xs">
                    {r.playtime_forever ? `${r.playtime_forever}h` : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
