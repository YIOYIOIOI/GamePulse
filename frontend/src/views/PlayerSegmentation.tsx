import { useEffect, useState } from 'react';
import { useDataStore } from '../lib/useDataStore';
import { XAxis, YAxis, ResponsiveContainer, CartesianGrid, Tooltip as RTooltip, ScatterChart, Scatter, ZAxis } from 'recharts';
import clsx from 'clsx';
import { AlertCircle, Cpu } from 'lucide-react';
import { fetchSegments, isEngineAvailable, SegmentMeta, SegmentProfile } from '../lib/analysisApi';

export function PlayerSegmentation() {
  const { data } = useDataStore();

  const validData = data.filter(d => d.playtime_forever !== undefined && d.sentiment);

  // 后端 Python 引擎分层（KMeans 多特征）：可用时页面主体消费引擎的行级标签
  // （与批处理报告同一口径），不可用时降级为本地时长阈值视图
  const [engineMeta, setEngineMeta] = useState<SegmentMeta | null>(null);
  const [engineLabels, setEngineLabels] = useState<string[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (validData.length < 100) return;
      if (!(await isEngineAvailable())) return;
      try {
        const { meta, labels } = await fetchSegments(validData, true);
        if (!cancelled) {
          setEngineMeta(meta);
          if (labels && labels.length === validData.length) {
            setEngineLabels(labels.map(l => l.segment_label));
          }
        }
      } catch {
        /* 引擎不可用时保持本地视图，不打扰用户 */
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.length]);

  if (validData.length === 0) {
    return (
      <div className="p-12 text-center">
        <AlertCircle className="w-8 h-8 text-zinc-400 dark:text-zinc-300 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-2">数据不足</h2>
        <p className="text-zinc-500 dark:text-zinc-300 max-w-md mx-auto">玩家分层需要游玩时长和情绪字段。请接入包含这些字段的数据集。</p>
      </div>
    );
  }

  // 分组口径：引擎行级标签可用时用引擎口径（消除页面内双口径），否则退回本地时长阈值
  const engineActive = engineLabels !== null && engineLabels.length === validData.length;
  const segments: Record<string, typeof validData> = {};
  if (engineActive) {
    validData.forEach((d, i) => {
      const key = engineLabels![i] || '未知';
      (segments[key] ??= []).push(d);
    });
  } else {
    segments['新手玩家'] = validData.filter(d => d.player_type === '新手玩家');
    segments['普通玩家'] = validData.filter(d => d.player_type === '普通玩家');
    segments['核心玩家'] = validData.filter(d => d.player_type === '核心玩家');
  }

  const segmentStats = Object.entries(segments).map(([name, groupData]) => {
    const total = groupData.length;
    const neg = groupData.filter(d => d.sentiment === 'negative').length;
    const avgPlaytime = groupData.reduce((acc, curr) => acc + (curr.playtime_forever || 0), 0) / (total || 1);
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
  }).filter(s => s.total > 0).sort((a, b) => a.avgPlaytime - b.avgPlaytime);

  const scatterData = [...validData].sort(() => 0.5 - Math.random()).slice(0, 100).map(d => ({
    x: d.value_potential_score || 50,
    y: d.churn_risk_proxy || 50,
    z: 1,
    sentiment: d.sentiment,
  }));

  return (
    <div className="py-12 px-8">
      <div className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 mb-2">玩家分层</h1>
        <p className="text-zinc-500 dark:text-zinc-300">基于活跃度、游玩时长和口碑倾向，对玩家进行运营分层。</p>

        <div className="mt-4 inline-block bg-blue-50 border border-blue-100 rounded-lg px-4 py-2">
          <p className="text-xs text-blue-800">
             <span className="font-bold">说明：</span> 本模块使用公开评论和游玩时长作为代理指标，不代表真实内部 LTV、付费转化或精确留存模型。
          </p>
        </div>
      </div>

      {engineMeta && engineMeta.method === 'kmeans_multifeature' && (
        <div className="mb-8 bg-white dark:bg-zinc-800 rounded-2xl p-6 shadow-sm border border-zinc-200 dark:border-zinc-700/50">
          <div className="flex items-center gap-2 mb-1">
            <Cpu className="w-4 h-4 text-indigo-500" />
            <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-300">后端引擎分层 · KMeans 多特征</h2>
          </div>
          <p className="text-xs text-zinc-400 dark:text-zinc-300 mb-4">
            由 Python 分析引擎计算（与批处理报告同一口径）：k={engineMeta.k}（轮廓系数 {engineMeta.silhouette} 自动选取），
            特征：{(engineMeta.features || []).join(' / ')}，log1p + 标准化。
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {(Object.entries(engineMeta.cluster_profiles ?? {}) as [string, SegmentProfile][]).map(([name, p]) => (
              <div key={name} className="bg-zinc-50 dark:bg-zinc-900/40 rounded-lg p-3 border border-zinc-100 dark:border-zinc-700/50">
                <div className="flex justify-between items-baseline mb-1">
                  <span className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm">{name}</span>
                  <span className="text-[10px] font-mono text-zinc-400">{(p.share * 100).toFixed(1)}%</span>
                </div>
                <div className="text-[11px] text-zinc-500 dark:text-zinc-300 font-mono leading-relaxed">
                  n={p.n} · 均时长 {p.avg_playtime_hours}h
                  {p.avg_votes_up !== null && <> · 均获赞 {p.avg_votes_up}</>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className="bg-white dark:bg-zinc-800 rounded-2xl p-6 shadow-sm border border-zinc-200 dark:border-zinc-700/50">
           <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-300 mb-2">价值 × 风险矩阵（代理指标）</h2>
           <p className="text-xs text-zinc-400 dark:text-zinc-300 mb-6">横轴：活跃价值代理；纵轴：流失风险代理；颜色：评论情绪。</p>

           <div className="h-[300px]">
             <ResponsiveContainer width="100%" height="100%">
               <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                 <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f4f4f5" />
                 <XAxis type="number" dataKey="x" name="活跃价值代理" domain={[0, 100]} tick={{fontSize: 12, fill: '#a1a1aa'}} axisLine={false} tickLine={false} />
                 <YAxis type="number" dataKey="y" name="流失风险代理" domain={[0, 100]} tick={{fontSize: 12, fill: '#a1a1aa'}} axisLine={false} tickLine={false} />
                 <ZAxis type="number" dataKey="z" range={[40, 40]} />
                 <RTooltip cursor={{strokeDasharray: '3 3'}} contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
                 <Scatter name="正向" data={scatterData.filter(d => d.sentiment === 'positive')} fill="#10b981" fillOpacity={0.6} />
                 <Scatter name="负向" data={scatterData.filter(d => d.sentiment === 'negative')} fill="#ef4444" fillOpacity={0.6} />
               </ScatterChart>
             </ResponsiveContainer>
           </div>
        </div>

        <div className="bg-white dark:bg-zinc-800 rounded-2xl p-6 shadow-sm border border-zinc-200 dark:border-zinc-700/50">
           <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-300 mb-1">分层概览</h2>
           <p className="text-xs text-zinc-400 dark:text-zinc-300 mb-5">
             {engineActive
               ? '口径：Python 引擎 KMeans 行级标签（与批处理报告一致）'
               : '口径：本地时长阈值（<10h 新手 / 10–100h 普通 / >100h 核心）'}
           </p>

           <div className="space-y-6">
              {segmentStats.map(s => (
                <div key={s.name} className="flex flex-col">
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-semibold text-zinc-900 dark:text-zinc-100">{s.name}</span>
                    <span className="text-xs font-mono text-zinc-500 dark:text-zinc-300">{s.total} 人</span>
                  </div>

                  <div className="flex gap-4">
                    <div className="flex-1 bg-zinc-50 dark:bg-zinc-800 p-2 rounded-lg border border-zinc-100 dark:border-zinc-700/50/50">
                       <div className="text-[10px] uppercase text-zinc-400 dark:text-zinc-300 font-bold mb-1">平均游玩</div>
                       <div className="font-mono text-zinc-700 dark:text-zinc-300">{s.avgPlaytime}h</div>
                    </div>
                    <div className="flex-1 bg-zinc-50 dark:bg-zinc-800 p-2 rounded-lg border border-zinc-100 dark:border-zinc-700/50/50">
                       <div className="text-[10px] uppercase text-zinc-400 dark:text-zinc-300 font-bold mb-1">负向占比</div>
                       <div className={clsx("font-mono", s.negRatio > 40 ? "text-red-500" : "text-emerald-500")}>{s.negRatio.toFixed(1)}%</div>
                    </div>
                    <div className="flex-1 bg-zinc-50 dark:bg-zinc-800 p-2 rounded-lg border border-zinc-100 dark:border-zinc-700/50/50">
                       <div className="text-[10px] uppercase text-zinc-400 dark:text-zinc-300 font-bold mb-1">触达优先级</div>
                       <div className="font-mono text-blue-600">{s.avgRisk > 60 || s.avgVal > 70 ? '高' : '常规'}</div>
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
