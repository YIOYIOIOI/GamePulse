import { useDataStore } from '../lib/useDataStore';
import { differenceInDays } from 'date-fns';
import { CheckCircle2, AlertCircle, XCircle } from 'lucide-react';
import clsx from 'clsx';
import * as Progress from '@radix-ui/react-progress';

export function HealthCheck() {
  const { data, status, enginePackage } = useDataStore();

  // 口径：引擎分析包（/api/analyze，与 CLI 批处理同一事实源）优先；引擎不可用时本地估算降级
  const eq = enginePackage?.quality;
  const gates = enginePackage?.gates;
  const engineActive = !!eq;

  const localDates = data.map(d => d.timestamp_created?.getTime() || 0).filter(d => d > 0);
  const localMin = localDates.length ? new Date(Math.min(...localDates)) : new Date();
  const localMax = localDates.length ? new Date(Math.max(...localDates)) : new Date();
  const localTimeSpan = differenceInDays(localMax, localMin) || 1;

  const sampleSize = eq?.sample_size ?? status.totalRecords;
  const timeSpanDays = eq?.date_span_days ?? localTimeSpan;

  const fields = {
    sentiment: data.filter(d => d.sentiment).length / (status.totalRecords || 1),
    topic: data.filter(d => d.topic_description).length / (status.totalRecords || 1),
    playtime: data.filter(d => d.playtime_forever !== undefined).length / (status.totalRecords || 1),
  };

  const capabilities = gates
    ? [
        { name: '口碑结构分析', reason: gates.voice?.reason ?? '', supported: !!gates.voice?.enabled },
        { name: '玩家分层', reason: gates.segments?.reason ?? '', supported: !!gates.segments?.enabled },
        { name: 'CRM 策略生成', reason: gates.campaigns?.reason ?? '', supported: !!gates.campaigns?.enabled },
        { name: '竞品对比', reason: gates.competitors?.reason ?? '', supported: !!gates.competitors?.enabled },
        { name: '趋势判断', reason: gates.trend?.reason ?? '', supported: !!gates.trend?.enabled },
      ]
    : [
        { name: '口碑结构分析', reason: '需要 sentiment 字段', supported: fields.sentiment > 0.5 },
        { name: '主题洞察', reason: '需要 topic 字段', supported: fields.topic > 0.5 },
        { name: '玩家分层', reason: '需要 playtime + sentiment', supported: fields.playtime > 0.5 && fields.sentiment > 0.5 },
        { name: 'CRM 策略生成', reason: '需要 playtime + sentiment + topic', supported: fields.playtime > 0.5 && fields.sentiment > 0 && fields.topic > 0 },
        { name: '竞品对比', reason: '需要至少两款游戏数据', supported: status.gamesCount > 1 },
      ];

  let downgradeReason = '';
  if (engineActive) {
    downgradeReason = (eq!.limitations || []).join('；');
  } else {
    if (sampleSize < 300) downgradeReason = '样本量 < 300：波动较大，仅建议做描述性观察。';
    else if (sampleSize < 1000) downgradeReason = '样本量 < 1000：置信度中等，结论需保守。';
    if (timeSpanDays < 14) downgradeReason += `${downgradeReason ? '；' : ''}时间跨度 < 14 天：仅做截面分析，不输出趋势判断。`;
  }

  const FieldStatus = ({ ratio, name }: { ratio: number, name: string }) => {
    const isGood = ratio > 0.8;
    const isOk = ratio > 0.3;
    return (
      <div className="flex items-center justify-between p-3 bg-zinc-50 dark:bg-zinc-800 rounded-lg">
        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{name}</span>
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-zinc-500 dark:text-zinc-300">{(ratio * 100).toFixed(1)}% 填充率</span>
          {isGood ? <CheckCircle2 className="w-4 h-4 text-emerald-500" /> :
           isOk ? <AlertCircle className="w-4 h-4 text-amber-500" /> :
           <XCircle className="w-4 h-4 text-red-500" />}
        </div>
      </div>
    );
  };

  return (
    <div className="py-12 px-8">
      <div className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 mb-2">数据健康检查</h1>
        <p className="text-zinc-500 dark:text-zinc-300">评估当前数据是否足以支撑深入分析。</p>
        <p className="text-xs text-zinc-400 dark:text-zinc-300 mt-2">
          {engineActive
            ? '口径：Python 引擎 /api/analyze（与 CLI 批处理报告同一事实源）'
            : '口径：本地估算（分析引擎不可用时的降级路径）'}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

        {/* Core Metrics */}
        <div className="space-y-6">
          <div className="bg-white dark:bg-zinc-800 rounded-2xl p-6 shadow-sm border border-zinc-200 dark:border-zinc-700/50">
             <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-300 mb-6">样本量与时间跨度</h2>
             <div className="space-y-6">
                <div>
                   <div className="flex justify-between text-sm mb-2">
                     <span className="font-medium text-zinc-900 dark:text-zinc-100">样本量</span>
                     <span className="font-mono text-zinc-500 dark:text-zinc-300">{sampleSize} 条记录</span>
                   </div>
                   <Progress.Root className="h-2 w-full bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden" value={Math.min(100, (sampleSize/2000)*100)}>
                     <Progress.Indicator
                       className={clsx("h-full transition-all duration-500", sampleSize > 1000 ? "bg-emerald-500" : sampleSize > 300 ? "bg-amber-500" : "bg-red-500")}
                       style={{ width: `${Math.min(100, (sampleSize/2000)*100)}%` }}
                      />
                   </Progress.Root>
                   <div className="text-xs text-zinc-400 dark:text-zinc-300 mt-2">建议：&gt; 1,000</div>
                </div>

                <div>
                   <div className="flex justify-between text-sm mb-2">
                     <span className="font-medium text-zinc-900 dark:text-zinc-100">时间跨度</span>
                     <span className="font-mono text-zinc-500 dark:text-zinc-300">{timeSpanDays} 天</span>
                   </div>
                   <Progress.Root className="h-2 w-full bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden" value={Math.min(100, (timeSpanDays/30)*100)}>
                     <Progress.Indicator
                       className={clsx("h-full transition-all duration-500 bg-blue-500")}
                       style={{ width: `${Math.min(100, (timeSpanDays/30)*100)}%` }}
                      />
                   </Progress.Root>
                   <div className="text-xs text-zinc-400 dark:text-zinc-300 mt-2">建议：&gt; 14 天后再输出趋势判断</div>
                </div>
             </div>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-2xl p-6 shadow-sm border border-zinc-200 dark:border-zinc-700/50">
             <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-300 mb-4">字段完整度</h2>
             <div className="space-y-3">
                <FieldStatus name="情绪字段" ratio={fields.sentiment} />
                <FieldStatus name="游玩时长字段" ratio={fields.playtime} />
                <FieldStatus name="主题/分类字段" ratio={fields.topic} />
             </div>
          </div>
        </div>

        {/* Capability Matrix */}
        <div className="bg-white dark:bg-zinc-800 rounded-2xl p-6 shadow-sm border border-zinc-200 dark:border-zinc-700/50 relative overflow-hidden">
          {downgradeReason && (
            <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl flex gap-3">
              <AlertCircle className="w-5 h-5 text-amber-600 shrink-0" />
              <div>
                <h4 className="text-sm font-semibold text-amber-900">
                  {engineActive ? '限制与边界（引擎口径）' : '分析能力降级'}
                </h4>
                <p className="text-xs text-amber-700 mt-1">{downgradeReason}</p>
              </div>
            </div>
          )}

          <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-300 mb-6">当前可支持的分析能力</h2>

          <div className="space-y-4">
            {capabilities.map(cap => (
              <div key={cap.name} className={clsx(
                "p-4 rounded-xl border flex gap-4",
                cap.supported ? "bg-emerald-50/50 border-emerald-100" : "bg-zinc-50 dark:bg-zinc-800 border-zinc-200 dark:border-zinc-700/50 opacity-60"
              )}>
                <div className="shrink-0 mt-0.5">
                  {cap.supported ?
                    <CheckCircle2 className="w-5 h-5 text-emerald-500" /> :
                    <XCircle className="w-5 h-5 text-zinc-400 dark:text-zinc-300" />
                  }
                </div>
                <div>
                  <h4 className={clsx("font-semibold text-sm", cap.supported ? "text-emerald-900" : "text-zinc-500 dark:text-zinc-300")}>
                    {cap.name}
                  </h4>
                  <p className="text-xs text-zinc-500 dark:text-zinc-300 mt-1">
                    {!cap.supported ? `暂不可用：${cap.reason}` : `当前数据质量可支持。`}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {engineActive && (enginePackage!.next_steps || []).length > 0 && (
            <div className="mt-6 pt-4 border-t border-zinc-100 dark:border-zinc-700/50">
              <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 dark:text-zinc-300 mb-2">引擎建议的下一步</h3>
              <ul className="space-y-1">
                {enginePackage!.next_steps.map((step, i) => (
                  <li key={i} className="text-xs text-zinc-500 dark:text-zinc-300">· {step}</li>
                ))}
              </ul>
            </div>
          )}

        </div>

      </div>
    </div>
  );
}
