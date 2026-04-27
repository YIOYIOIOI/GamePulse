import { useDataStore } from '../lib/useDataStore';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, CartesianGrid, Legend, Tooltip as RTooltip } from 'recharts';
import { AlertCircle } from 'lucide-react';
import clsx from 'clsx';
import { normalizeTopicLabel } from '../lib/dataProcessor';

export function CompetitorAnalysis({ onChangeView }: { onChangeView: (v: string) => void }) {
  const { data, status } = useDataStore();

  if (status.gamesCount < 2) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-8">
        <div className="w-16 h-16 bg-zinc-100 dark:bg-zinc-800 text-zinc-400 dark:text-zinc-300 rounded-2xl flex items-center justify-center mb-6">
          <AlertCircle className="w-8 h-8" />
        </div>
        <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mb-2">需要更多数据</h2>
        <p className="text-zinc-500 dark:text-zinc-300 max-w-md mx-auto mb-8">
          竞品分析至少需要两个不同游戏的数据集。请继续追加另一个游戏的数据。
        </p>
        <button
          onClick={() => onChangeView('data-center')}
          className="bg-black dark:bg-white text-white dark:text-zinc-900 px-6 py-2.5 rounded-full font-medium hover:bg-zinc-800 transition-colors"
        >
          追加数据
        </button>
      </div>
    );
  }

  const games = Array.from(new Set(data.map(d => d.game_name)));

  const gameStats = games.map(game => {
    const gameData = data.filter(d => d.game_name === game);
    const total = gameData.length;
    const pos = gameData.filter(d => d.sentiment === 'positive').length;
    const neg = gameData.filter(d => d.sentiment === 'negative').length;

    const topicCounts = gameData.reduce((acc, curr) => {
      const t = normalizeTopicLabel(curr.topic_description) || '综合体验反馈';
      acc[t] = (acc[t] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    const topTopic = Object.entries(topicCounts).sort((a: [string, number], b: [string, number]) => b[1] - a[1])[0]?.[0] || '-';

    return {
      game,
      total,
      posRate: total > 0 ? (pos / total) * 100 : 0,
      negRate: total > 0 ? (neg / total) * 100 : 0,
      topTopic,
    };
  }).sort((a, b) => b.total - a.total); // Sort by volume

  // Prepare chart data
  const chartData = gameStats.map(s => ({
    name: s.game,
    正向: Number(s.posRate.toFixed(1)),
    负向: Number(s.negRate.toFixed(1)),
  }));

  return (
    <div className="py-12 px-8">
      <div className="mb-10 flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 mb-2">竞品分析</h1>
          <p className="text-zinc-500 dark:text-zinc-300">跨游戏比较玩家情绪结构与主要痛点。</p>
        </div>
        <div className="bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700/50 px-3 py-1.5 rounded-lg text-xs font-mono font-medium">
          {games.length} 款游戏对比
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">

        {/* Chart */}
        <div className="bg-white dark:bg-zinc-800 rounded-2xl p-6 shadow-sm border border-zinc-200 dark:border-zinc-700/50 lg:col-span-2">
          <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-300 mb-6">情绪结构对比</h2>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f4f4f5" />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: '#71717a', fontSize: 12}} />
                <YAxis axisLine={false} tickLine={false} tick={{fill: '#71717a', fontSize: 12}} domain={[0, 100]} tickFormatter={val => `${val}%`} />
                <RTooltip cursor={{fill: '#f4f4f5'}} contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
                <Bar dataKey="正向" stackId="a" fill="#10b981" radius={[0, 0, 4, 4]} barSize={40} />
                <Bar dataKey="负向" stackId="a" fill="#ef4444" radius={[4, 4, 0, 0]} barSize={40} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 关键观察 */}
        <div className="bg-white dark:bg-zinc-800 rounded-2xl p-6 shadow-sm border border-zinc-200 dark:border-zinc-700/50 flex flex-col justify-center">
            <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-300 mb-6">关键观察</h2>

            <div className="space-y-6">
               <div>
                  <div className="text-xs text-zinc-400 dark:text-zinc-300 mb-1">正向口碑最高</div>
                  <div className="font-semibold text-lg text-zinc-900 dark:text-zinc-100 border-l-2 border-emerald-500 pl-3">
                     {[...gameStats].sort((a,b)=>b.posRate-a.posRate)[0].game}
                     <span className="text-emerald-500 font-mono text-sm ml-2">
                       {Math.max(...gameStats.map(g => g.posRate)).toFixed(1)}%
                     </span>
                  </div>
               </div>

               <div>
                  <div className="text-xs text-zinc-400 dark:text-zinc-300 mb-1">负向风险最高</div>
                  <div className="font-semibold text-lg text-zinc-900 dark:text-zinc-100 border-l-2 border-red-500 pl-3">
                     {[...gameStats].sort((a,b)=>b.negRate-a.negRate)[0].game}
                     <span className="text-red-500 font-mono text-sm ml-2">
                       {Math.max(...gameStats.map(g => g.negRate)).toFixed(1)}%
                     </span>
                  </div>
               </div>
            </div>
        </div>

      </div>

      {/* 汇总表 */}
      <div className="bg-white dark:bg-zinc-800 rounded-2xl border border-zinc-200 dark:border-zinc-700/50 shadow-sm overflow-hidden">
        <table className="w-full text-left text-sm whitespace-nowrap">
          <thead className="bg-zinc-50 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-300 border-b border-zinc-100 dark:border-zinc-700/50/50">
            <tr>
              <th className="px-6 py-4 font-semibold">游戏名称</th>
              <th className="px-6 py-4 font-semibold text-right">样本量</th>
              <th className="px-6 py-4 font-semibold text-right">好评占比</th>
              <th className="px-6 py-4 font-semibold text-right">差评占比</th>
              <th className="px-6 py-4 font-semibold text-right">主要主题</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {gameStats.map((s, i) => (
              <tr key={i} className="hover:bg-zinc-50 dark:bg-zinc-800 transition-colors">
                <td className="px-6 py-4 font-medium text-zinc-900 dark:text-zinc-100">{s.game}</td>
                <td className="px-6 py-4 text-right font-mono text-zinc-600 dark:text-zinc-300">{s.total}</td>
                <td className="px-6 py-4 text-right">
                   <span className="text-emerald-600 font-mono bg-emerald-50 px-2 py-1 rounded inline-block min-w-[60px] text-center">
                     {s.posRate.toFixed(1)}%
                   </span>
                </td>
                <td className="px-6 py-4 text-right">
                   <span className="text-red-600 font-mono bg-red-50 px-2 py-1 rounded inline-block min-w-[60px] text-center">
                     {s.negRate.toFixed(1)}%
                   </span>
                </td>
                <td className="px-6 py-4 text-right text-zinc-600 dark:text-zinc-300">{s.topTopic}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

    </div>
  );
}
