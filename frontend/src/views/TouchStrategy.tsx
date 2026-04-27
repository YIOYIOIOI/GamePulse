import { useDataStore } from '../lib/useDataStore';
import { useState } from 'react';
import { Megaphone, AlertCircle, RefreshCw } from 'lucide-react';
import clsx from 'clsx';
import { normalizeTopicLabel } from '../lib/dataProcessor';
import { generateStrategyWithLlm, loadLlmSettings } from '../lib/llmClient';
import { ProgressBar, type ProgressState } from '../components/ProgressBar';

export function TouchStrategy() {
  const { data } = useDataStore();
  const [llmStrategies, setLlmStrategies] = useState<Record<string, any>>({});
  const [llmStatus, setLlmStatus] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [modelProgress, setModelProgress] = useState<ProgressState>(null);

  const validData = data.filter(d => d.player_type);

  if (validData.length === 0) {
    return (
      <div className="p-12 text-center">
        <AlertCircle className="w-8 h-8 text-zinc-400 dark:text-zinc-300 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-2">数据不足</h2>
        <p className="text-zinc-500 dark:text-zinc-300 max-w-md mx-auto">触达策略需要玩家分层输入。请确保数据里有情绪和游玩时长字段。</p>
      </div>
    );
  }

  const segmentNames = ['新手玩家', '普通玩家', '核心玩家'];

  const strategies = segmentNames.map(name => {
    const group = validData.filter(d => d.player_type === name);
    if (group.length === 0) return null;

    const total = group.length;
    const negCount = group.filter(d => d.sentiment === 'negative').length;
    const negRatio = (negCount / total) * 100;
    const avgPlaytime = group.reduce((acc, curr) => acc + (curr.playtime_forever || 0), 0) / total;

    const topicCounts = group.reduce((acc, curr) => {
      const t = normalizeTopicLabel(curr.topic_description) || '综合体验反馈';
      acc[t] = (acc[t] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    const topTopic = Object.entries(topicCounts).sort((a: [string, unknown], b: [string, unknown]) => (b[1] as number) - (a[1] as number))[0]?.[0] || '综合体验反馈';

    let goal = '';
    let content = '';
    let tone = '';
    let draft = '';
    let advice = '';

    if (negRatio > 40) {
      goal = '止损与召回';
      tone = '共情、透明、及时';
      content = `解释「${topTopic}」相关问题，给出补偿或修复节奏，并明确后续路径。`;
      advice = `该群体负向占比达到 ${negRatio.toFixed(0)}%。优先处理「${topTopic}」，不要先做泛营销。`;
      draft = `我们看到了大家集中反馈的「${topTopic}」问题。这个体验确实没有达到预期，团队已经在排查，并会在后续公告里同步明确的处理进度。感谢你们继续反馈具体场景。`;
    } else if (name === '核心玩家') {
      goal = '核心用户维护与共创';
      tone = '感谢、专业、邀请式';
      content = '提前透露版本方向、邀请参与测试、收集高质量反馈。';
      advice = '核心玩家会影响社区舆论，应把他们纳入版本沟通和内容共创。';
      draft = `感谢你长期投入这款游戏。我们正在围绕「${topTopic}」做下一阶段优化，希望邀请你参与一轮反馈收集，帮助我们把改动做得更稳。`;
    } else if (name === '新手玩家') {
      goal = '降低入门阻力';
      tone = '友好、清晰、鼓励';
      content = '提供新手指引、低门槛目标、欢迎奖励和帮助入口。';
      advice = '新手期要减少挫败感。如果高频主题是新手引导或操作手感，应优先优化前几局体验。';
      draft = `欢迎加入游戏！如果你在「${topTopic}」上遇到阻碍，可以先看这份 5 分钟入门指南。本周也会开放新手奖励，帮助你更快进入状态。`;
    } else {
      goal = '保持活跃与内容回流';
      tone = '直接、轻量、有信息量';
      content = '版本亮点、活动提醒、常规补丁说明和回流奖励。';
      advice = `普通玩家容易受「${topTopic}」影响而流失，需要持续监控并用轻量内容维持参与。`;
      draft = `本次更新已经覆盖「${topTopic}」相关调整。欢迎回来体验新的平衡与活动奖励，也欢迎继续反馈实际对局感受。`;
    }

    return {
      group: name,
      sampleSize: total,
      negRatio,
      avgPlaytime: Math.floor(avgPlaytime),
      topTopic,
      goal,
      content,
      tone,
      draft,
      advice
    };
  }).filter(Boolean);

  const runLlmStrategy = async () => {
    const settings = loadLlmSettings();
    if (!settings.enabled || !settings.apiKey) {
      setLlmStatus('请先在「模型设置」里启用并保存访问密钥。');
      return;
    }
    setIsGenerating(true);
    setLlmStatus('正在使用 模型辅助分析生成触达策略...');
    try {
      const payload = (strategies as any[]).map(s => ({
        group: s.group,
        sampleSize: s.sampleSize,
        negRatio: s.negRatio,
        avgPlaytime: s.avgPlaytime,
        topTopic: s.topTopic,
        samples: data.filter(d => d.player_type === s.group).slice(0, 12).map(d => ({ sentiment: d.sentiment, topic: d.topic_description, text: d.review_text.slice(0, 300) }))
      }));
      setModelProgress({ label: '正在请求模型服务生成策略...', value: 42 });
      const { result, fromCache } = await generateStrategyWithLlm(payload);
      setModelProgress({ label: fromCache ? '已命中本地缓存，正在应用策略...' : '模型已返回，正在整理策略卡...', value: 82 });
      const mapped: Record<string, any> = {};
      (result.strategies || []).forEach((item: any) => { if (item.group) mapped[item.group] = item; });
      setLlmStrategies(mapped);
      setModelProgress({ label: fromCache ? '已使用本地缓存生成策略。' : '已通过模型辅助分析生成策略。', value: 100 });
      setLlmStatus(fromCache ? '已使用本地缓存生成策略。' : '已通过模型辅助分析生成策略。');
      window.setTimeout(() => setModelProgress(null), 1600);
    } catch (err) {
      setModelProgress({ label: '策略生成失败，请检查模型服务配置。', value: 100 });
      setLlmStatus(err instanceof Error ? err.message : '模型策略生成失败。');
      window.setTimeout(() => setModelProgress(null), 2200);
    } finally {
      setIsGenerating(false);
    }
  };

  const resolvedStrategies = (strategies as any[]).map(s => ({ ...s, ...(llmStrategies[s.group] || {}) }));

  return (
    <div className="py-12 px-8">
      <div className="mb-10 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 mb-2">触达策略</h1>
          <p className="text-zinc-500 dark:text-zinc-300">基于玩家分层和主题痛点，生成可复核的 CRM 沟通方案。</p>
          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={runLlmStrategy}
              disabled={isGenerating}
              className="px-4 py-2 rounded-xl bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 text-sm font-semibold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-all"
            >
              {isGenerating ? '生成中...' : '用 模型辅助分析生成策略'}
            </button>
            {llmStatus && <span className="text-xs text-zinc-500 dark:text-zinc-300">{llmStatus}</span>}
          </div>
          <div className="max-w-xl"><ProgressBar progress={modelProgress} /></div>
        </div>

        <div className="flex bg-amber-50 border border-amber-200 text-amber-800 text-xs px-4 py-2 rounded-lg items-center gap-2 max-w-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <p>
             <span className="font-bold">需要人工复核：</span> 下方草案由关键词主题自动生成，对外发布前必须由运营人员确认。
          </p>
        </div>
      </div>

      <div className="space-y-8">
        {resolvedStrategies.map((strategy: any) => (
          <div key={strategy.group} className="bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700/50 rounded-2xl overflow-hidden shadow-sm">
            <div className="border-b border-zinc-100 dark:border-zinc-700/50/50 bg-zinc-50 dark:bg-zinc-800/50 p-6 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{strategy.group}</h2>
                <div className="flex items-center gap-4 mt-2">
                   <div className="flex items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-300 font-mono">
                     <span className="w-2 h-2 rounded-full bg-zinc-300"></span>
                     {strategy.sampleSize} 人
                   </div>
                   <div className="flex items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-300 font-mono">
                     <span className={clsx("w-2 h-2 rounded-full", strategy.negRatio > 40 ? "bg-red-500" : "bg-emerald-500")}></span>
                     负向 {strategy.negRatio.toFixed(1)}%
                   </div>
                   <div className="flex items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-300 font-mono">
                     <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                     平均 {strategy.avgPlaytime}h
                   </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-xs uppercase font-bold tracking-wider text-zinc-400 dark:text-zinc-300 mb-1">主要主题</div>
                <div className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{strategy.topTopic}</div>
              </div>
            </div>

            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="space-y-6">
                <div>
                  <div className="text-xs uppercase font-bold tracking-wider text-zinc-400 dark:text-zinc-300 mb-2">策略目标</div>
                  <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100 bg-zinc-50 dark:bg-zinc-800 p-3 rounded-lg border border-zinc-100 dark:border-zinc-700/50/50">
                    {strategy.goal}
                  </div>
                </div>
                <div>
                  <div className="text-xs uppercase font-bold tracking-wider text-zinc-400 dark:text-zinc-300 mb-2">建议语气</div>
                  <div className="text-sm text-zinc-700 dark:text-zinc-300">{strategy.tone}</div>
                </div>
                <div>
                  <div className="text-xs uppercase font-bold tracking-wider text-zinc-400 dark:text-zinc-300 mb-2">运营建议</div>
                  <div className="text-sm text-purple-700 bg-purple-50 p-3 rounded-lg border border-purple-100 leading-relaxed">
                    {strategy.advice}
                  </div>
                </div>
                <div>
                  <div className="text-xs uppercase font-bold tracking-wider text-zinc-400 dark:text-zinc-300 mb-2">触达内容</div>
                  <div className="text-sm text-zinc-700 dark:text-zinc-300">{strategy.content}</div>
                </div>
              </div>

              <div className="border-l border-zinc-100 dark:border-zinc-700/50/50 pl-8">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-xs uppercase font-bold tracking-wider text-zinc-400 dark:text-zinc-300">参考文案</div>
                  <button className="text-xs text-blue-600 hover:underline flex items-center gap-1">
                    <RefreshCw className="w-3 h-3" /> 重新生成
                  </button>
                </div>
                <div className="bg-zinc-900 text-zinc-300 p-5 rounded-xl font-mono text-sm leading-relaxed whitespace-pre-wrap relative shadow-inner">
                  <div className="absolute top-0 right-0 p-2 opacity-20">
                     <Megaphone className="w-12 h-12" />
                  </div>
                  <span className="relative z-10">{strategy.draft}</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
