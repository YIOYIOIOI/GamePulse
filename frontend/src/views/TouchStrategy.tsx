import { useDataStore } from '../lib/useDataStore';
import { Megaphone, AlertCircle, RefreshCw } from 'lucide-react';
import clsx from 'clsx';

export function TouchStrategy() {
  const { data } = useDataStore();

  const validData = data.filter(d => d.player_type);

  if (validData.length === 0) {
    return (
      <div className="p-12 text-center">
        <AlertCircle className="w-8 h-8 text-zinc-400 dark:text-zinc-300 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-2">Insufficient Data</h2>
        <p className="text-zinc-500 dark:text-zinc-300 max-w-md mx-auto">Touch strategy generation requires player segmentation logic. Please ensure your dataset supports segmentation.</p>
      </div>
    );
  }

  const segmentNames = ['New Player', 'Regular Player', 'Core Player'];

  const strategies = segmentNames.map(name => {
    const group = validData.filter(d => d.player_type === name);
    if (group.length === 0) return null;

    const total = group.length;
    const negCount = group.filter(d => d.sentiment === 'negative').length;
    const negRatio = (negCount / total) * 100;
    const avgPlaytime = group.reduce((acc, curr) => acc + (curr.playtime_forever || 0), 0) / total;

    // Get top topic for this group
    const topicCounts = group.reduce((acc, curr) => {
      const t = curr.topic_description || 'General';
      acc[t] = (acc[t] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    const topTopic = Object.entries(topicCounts).sort((a: [string, unknown], b: [string, unknown]) => (b[1] as number) - (a[1] as number))[0]?.[0] || 'General';

    // Strategy Generation Logic
    let goal = '';
    let content = '';
    let tone = '';
    let draft = '';
    let advice = '';

    if (negRatio > 40) {
      goal = 'Damage Control & Re-engagement';
      tone = 'Empathetic, Transparent, Urgent';
      content = `Explanation of ${topTopic} issues, compensation plan, clear roadmap.`;
      advice = `High negative sentiment (${negRatio.toFixed(0)}%) detected. Prioritize fixing ${topTopic}. Acknowledge user frustration immediately.`;
      draft = `Hey everyone, we've seen your feedback regarding ${topTopic}. We know it's frustrating and falls short of expectations. We are actively working on a hotfix targeted for [Date]. Thank you for bearing with us.`;
    } else if (name === 'Core Player') {
      goal = 'Brand Advocacy & Deep Engagement';
      tone = 'Appreciative, Collaborative, Insider';
      content = 'Advanced sneak peeks, high-tier discussions, exclusive Q&A requests.';
      advice = 'These players drive community sentiment. Involve them in upcoming content decisions.';
      draft = `To our veteran players: We're exploring some major meta shifts for the next update and want your thoughts. Check out this dev diary diving deep into the new mechanics.`;
    } else if (name === 'New Player') {
      goal = 'Onboarding & Retention';
      tone = 'Welcoming, Encouraging, Educational';
      content = 'Beginner guides, easily achievable milestones, welcome rewards.';
      advice = 'Minimize friction. If they are talking about "New Player Experience", streamline the tutorial.';
      draft = `Welcome to the game! To help you get started, we've put together a quick 5-minute video covering the basics. Jump in-game this weekend for a 2x XP boost!`;
    } else {
      goal = 'Routine Engagement & Upsell';
      tone = 'Upbeat, Informative';
      content = 'Content highlights, event announcements, regular patch notes.';
      advice = `Keep them playing. Monitor feedback on ${topTopic} to prevent them slipping into the negative cohort.`;
      draft = `The latest patch brings changes to ${topTopic}. Jump back in to check out the rebalance and earn new rewards this season.`;
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

  return (
    <div className="py-12 px-8">
      <div className="mb-10 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 mb-2">触达策略</h1>
          <p className="text-zinc-500 dark:text-zinc-300">Automated CRM strategies based on behavioral segments.</p>
        </div>

        <div className="flex bg-amber-50 border border-amber-200 text-amber-800 text-xs px-4 py-2 rounded-lg items-center gap-2 max-w-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <p>
             <span className="font-bold">Human Review Required:</span> Reference drafts are auto-generated from keyword themes. Do not publish without operational review.
          </p>
        </div>
      </div>

      <div className="space-y-8">
        {strategies.map((strategy: any) => (
          <div key={strategy.group} className="bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700/50 rounded-2xl overflow-hidden shadow-sm">
            {/* Header */}
            <div className="border-b border-zinc-100 dark:border-zinc-700/50/50 bg-zinc-50 dark:bg-zinc-800/50 p-6 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{strategy.group}</h2>
                <div className="flex items-center gap-4 mt-2">
                   <div className="flex items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-300 font-mono">
                     <span className="w-2 h-2 rounded-full bg-zinc-300"></span>
                     {strategy.sampleSize} Users
                   </div>
                   <div className="flex items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-300 font-mono">
                     <span className={clsx("w-2 h-2 rounded-full", strategy.negRatio > 40 ? "bg-red-500" : "bg-emerald-500")}></span>
                     {strategy.negRatio.toFixed(1)}% Negative
                   </div>
                   <div className="flex items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-300 font-mono">
                     <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                     {strategy.avgPlaytime}h Avg
                   </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-xs uppercase font-bold tracking-wider text-zinc-400 dark:text-zinc-300 mb-1">Top Theme</div>
                <div className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{strategy.topTopic}</div>
              </div>
            </div>

            {/* Content */}
            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="space-y-6">
                <div>
                  <div className="text-xs uppercase font-bold tracking-wider text-zinc-400 dark:text-zinc-300 mb-2">Strategy Goal</div>
                  <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100 bg-zinc-50 dark:bg-zinc-800 p-3 rounded-lg border border-zinc-100 dark:border-zinc-700/50/50">
                    {strategy.goal}
                  </div>
                </div>
                <div>
                  <div className="text-xs uppercase font-bold tracking-wider text-zinc-400 dark:text-zinc-300 mb-2">Recommended Tone</div>
                  <div className="text-sm text-zinc-700 dark:text-zinc-300">{strategy.tone}</div>
                </div>
                <div>
                  <div className="text-xs uppercase font-bold tracking-wider text-zinc-400 dark:text-zinc-300 mb-2">Operational Advice</div>
                  <div className="text-sm text-purple-700 bg-purple-50 p-3 rounded-lg border border-purple-100 leading-relaxed">
                    {strategy.advice}
                  </div>
                </div>
              </div>

              <div className="border-l border-zinc-100 dark:border-zinc-700/50/50 pl-8">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-xs uppercase font-bold tracking-wider text-zinc-400 dark:text-zinc-300">Reference Draft</div>
                  <button className="text-xs text-blue-600 hover:underline flex items-center gap-1">
                    <RefreshCw className="w-3 h-3" /> Regenerate
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
