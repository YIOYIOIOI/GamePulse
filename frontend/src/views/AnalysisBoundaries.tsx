import { AlertTriangle, CheckCircle, Crosshair, XCircle, Info } from 'lucide-react';

export function AnalysisBoundaries() {
  return (
    <div className="py-12 px-8 max-w-4xl">
      <div className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 mb-2">分析边界与限制</h1>
        <p className="text-zinc-500 dark:text-zinc-300">说明公开评论数据能支持什么、不能支持什么。</p>
      </div>

      <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-5 mb-8 flex gap-4">
        <AlertTriangle className="w-6 h-6 text-yellow-600 shrink-0 mt-0.5" />
        <div>
          <h3 className="font-semibold text-yellow-900 mb-1">核心原则</h3>
          <p className="text-sm text-yellow-800 leading-relaxed">
            公开评论是运营决策的 <span className="font-bold">输入</span>，但不是完整事实来源。它存在幸存者偏差、极端意见偏差，也缺少真实付费和行为上下文。不要用抓取评论指标替代内部埋点。
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">

        {/* Can do */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle className="w-5 h-5 text-emerald-500" />
            <h2 className="font-bold text-lg text-zinc-900 dark:text-zinc-100">公开数据可支持</h2>
          </div>
          <ul className="space-y-4">
            {[
              { title: '情绪结构', desc: '发声玩家中的正负反馈比例。' },
              { title: '痛点排序', desc: '识别最明显引发摩擦的 bug 或功能问题。' },
              { title: '高层主题归类', desc: '将抱怨归入匹配、公平性、性能等结构化主题。' },
              { title: '游玩时长代理分层', desc: '按平台记录或用户自报游玩时长进行粗分层。' },
              { title: '竞品口碑差距', desc: '比较相似产品的公开口碑表现。' },
              { title: 'CRM 策略草拟', desc: '围绕具体社区痛点生成沟通模板。' }
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
            <h2 className="font-bold text-lg text-zinc-900 dark:text-zinc-100">需要内部数据</h2>
          </div>
          <ul className="space-y-4">
            {[
              { title: '真实 LTV（生命周期价值）', desc: '需要真实交易与支付日志。' },
              { title: '真实留存/流失率', desc: '需要登录日志和会话时长；评论者只占 DAU 的一部分。' },
              { title: '转化指标', desc: '无法从评论推导曝光→安装→付费等漏斗转化。' },
              { title: '活动 ROI', desc: '只能观察活动是否被喜欢，不能判断是否盈利。' },
              { title: '精确生命周期建模', desc: '需要用户级连续行为埋点。' }
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
          产品降级规则
        </h3>
        <p className="text-sm text-zinc-600 dark:text-zinc-300 mb-4">
          当数据质量不足时，GamePulse 会严格降级分析能力：
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div className="bg-white dark:bg-zinc-800 p-3 border border-zinc-100 dark:border-zinc-700/50/50 rounded-lg shadow-sm">
            <span className="font-mono text-xs bg-zinc-100 dark:bg-zinc-800 px-1 py-0.5 rounded mr-2">n &lt; 300</span>
            不做趋势判断，仅做描述性分析。
          </div>
          <div className="bg-white dark:bg-zinc-800 p-3 border border-zinc-100 dark:border-zinc-700/50/50 rounded-lg shadow-sm">
             <span className="font-mono text-xs bg-zinc-100 dark:bg-zinc-800 px-1 py-0.5 rounded mr-2">&lt; 14 Days</span>
            禁用时间序列预测。
          </div>
          <div className="bg-white dark:bg-zinc-800 p-3 border border-zinc-100 dark:border-zinc-700/50/50 rounded-lg shadow-sm">
            <span className="font-mono text-xs bg-zinc-100 dark:bg-zinc-800 px-1 py-0.5 rounded mr-2">Tags Gen</span>
            自动主题需标记为“关键词归类”
          </div>
          <div className="bg-white dark:bg-zinc-800 p-3 border border-zinc-100 dark:border-zinc-700/50/50 rounded-lg shadow-sm">
            <span className="font-mono text-xs bg-zinc-100 dark:bg-zinc-800 px-1 py-0.5 rounded mr-2">无游玩时长</span>
            完全禁用分层模块。
          </div>
        </div>
      </div>
    </div>
  );
}
