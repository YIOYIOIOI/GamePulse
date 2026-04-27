import { useDataStore } from '../lib/useDataStore';
import { PieChart, Pie, Cell, Tooltip as RTooltip, BarChart, Bar, XAxis, YAxis, ResponsiveContainer, CartesianGrid } from 'recharts';
import { useState } from 'react';
import clsx from 'clsx';
import { normalizeTopicLabel } from '../lib/dataProcessor';
import { classifyTopicsWithLlm, loadLlmSettings } from '../lib/llmClient';

const FILTER_LABELS = {
  all: '全部',
  negative: '负向',
  positive: '正向',
} as const;

export function FeedbackAnalysis() {
  const { data, replaceData } = useDataStore();
  const [filterMode, setFilterMode] = useState<'all' | 'negative' | 'positive'>('all');
  const [llmStatus, setLlmStatus] = useState('');
  const [isClassifying, setIsClassifying] = useState(false);

  const filteredData = data.filter(d => filterMode === 'all' ? true : d.sentiment === filterMode);

  const posCount = data.filter(d => d.sentiment === 'positive').length;
  const negCount = data.filter(d => d.sentiment === 'negative').length;
  const sentimentData = [
    { name: '正向', value: posCount, color: '#10b981' },
    { name: '负向', value: negCount, color: '#ef4444' },
  ].filter(d => d.value > 0);

  const topicCounts = filteredData.reduce((acc, curr) => {
    const t = normalizeTopicLabel(curr.topic_description) || '未分类反馈';
    acc[t] = (acc[t] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const topicChartData = Object.entries(topicCounts)
    .sort((a: [string, number], b: [string, number]) => b[1] - a[1])
    .slice(0, 10)
    .map(([name, count]) => ({
      name: name.length > 14 ? name.substring(0, 14) + '…' : name,
      fullName: name,
      count
    }));

  const recentReviews = [...filteredData]
    .sort((a, b) => (b.timestamp_created?.getTime() || 0) - (a.timestamp_created?.getTime() || 0))
    .slice(0, 10);

  const runLlmTopicClassification = async () => {
    const settings = loadLlmSettings();
    if (!settings.enabled || !settings.apiKey) {
      setLlmStatus('请先在「模型设置」里启用并保存访问密钥。');
      return;
    }
    setIsClassifying(true);
    setLlmStatus('正在使用 AI 增强进行主题细分...');
    try {
      const { result, fromCache } = await classifyTopicsWithLlm(data);
      const updates = new Map((result.topics || []).map(item => [item.index, item.topic]));
      const next = data.map((row, index) => updates.has(index) ? { ...row, topic_description: updates.get(index), topic_source: fromCache ? '本地 AI 缓存' : 'AI 增强' } : row);
      replaceData(next, fromCache ? 'AI 主题缓存' : 'AI 主题细分');
      setLlmStatus(fromCache ? '已使用本地缓存完成主题细分。' : '已通过 AI 增强完成主题细分。');
    } catch (err) {
      setLlmStatus(err instanceof Error ? err.message : 'AI 主题细分失败。');
    } finally {
      setIsClassifying(false);
    }
  };

  if (data.length === 0 || (!posCount && !negCount)) {
    return <div className="p-8 text-zinc-500 dark:text-zinc-300">数据不足，无法进行反馈分析。</div>;
  }

  return (
    <div className="py-12 px-8">
      <div className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 mb-2">反馈分析</h1>
        <p className="text-zinc-500 dark:text-zinc-300">理解玩家在说什么，并定位主要痛点。</p>
        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={runLlmTopicClassification}
            disabled={isClassifying}
            className="px-4 py-2 rounded-xl bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 text-sm font-semibold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-all"
          >
            {isClassifying ? '细分中...' : '用 AI 增强细分主题'}
          </button>
          {llmStatus && <span className="text-xs text-zinc-500 dark:text-zinc-300">{llmStatus}</span>}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white dark:bg-zinc-800 rounded-2xl p-6 shadow-sm border border-zinc-200 dark:border-zinc-700/50">
           <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-300 mb-6">口碑结构</h2>
           <div className="h-64 relative">
             <ResponsiveContainer width="100%" height="100%">
               <PieChart>
                 <Pie data={sentimentData} innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value">
                   {sentimentData.map((entry, index) => (
                     <Cell key={`cell-${index}`} fill={entry.color} />
                   ))}
                 </Pie>
                 <RTooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
               </PieChart>
             </ResponsiveContainer>
             <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-3xl font-light font-mono">{((posCount / (posCount + negCount)) * 100).toFixed(0)}%</span>
                <span className="text-[10px] uppercase text-zinc-400 dark:text-zinc-300 font-bold tracking-widest mt-1">正向</span>
             </div>
           </div>
        </div>

        <div className="bg-white dark:bg-zinc-800 rounded-2xl p-6 shadow-sm border border-zinc-200 dark:border-zinc-700/50 md:col-span-2">
           <div className="flex justify-between items-center mb-6">
             <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-300">高频主题</h2>
             <div className="flex gap-2">
               {(['all', 'negative', 'positive'] as const).map(mode => (
                 <button
                   key={mode}
                   onClick={() => setFilterMode(mode)}
                   className={clsx(
                     "px-3 py-1 pb-1.5 text-xs font-semibold rounded-md transition-colors",
                     filterMode === mode ? "bg-zinc-900 text-white dark:text-zinc-900" : "bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-300 hover:bg-zinc-200"
                   )}
                 >
                   {FILTER_LABELS[mode]}
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
                   <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fill: '#71717a', fontSize: 12 }} width={110} />
                   <RTooltip cursor={{fill: '#f4f4f5'}} contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
                   <Bar dataKey="count" fill={filterMode === 'negative' ? '#ef4444' : filterMode === 'positive' ? '#10b981' : '#3f3f46'} radius={[0, 4, 4, 0]} barSize={20} />
                 </BarChart>
               </ResponsiveContainer>
             ) : (
                <div className="h-full flex items-center justify-center text-zinc-400 dark:text-zinc-300 text-sm">未提取到主题。</div>
             )}
           </div>
        </div>
      </div>

      <div className="bg-white dark:bg-zinc-800 rounded-2xl border border-zinc-200 dark:border-zinc-700/50 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-zinc-100 dark:border-zinc-700/50/50">
          <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-300">最新评论样本</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead className="bg-zinc-50 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-300 border-b border-zinc-100 dark:border-zinc-700/50/50">
              <tr>
                <th className="px-6 py-3 font-semibold w-32">情绪</th>
                <th className="px-6 py-3 font-semibold w-48">主题</th>
                <th className="px-6 py-3 font-semibold min-w-[300px]">评论原文</th>
                <th className="px-6 py-3 font-semibold w-32">游玩时长</th>
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
                      {r.sentiment === 'positive' ? '正向' : r.sentiment === 'negative' ? '负向' : '未知'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-zinc-600 dark:text-zinc-300 truncate max-w-[200px]">
                    {normalizeTopicLabel(r.topic_description) || '-'}
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
