import { useState } from 'react';
import { clearLlmMemory, DEFAULT_LLM_SETTINGS, loadLlmMemory, loadLlmSettings, maskApiKey, saveLlmSettings, type LlmSettings } from '../lib/llmClient';
import { KeyRound, Trash2, Database } from 'lucide-react';

export function ModelSettings() {
  const [settings, setSettings] = useState<LlmSettings>(() => loadLlmSettings());
  const [savedHint, setSavedHint] = useState('');
  const [memoryCount, setMemoryCount] = useState(() => loadLlmMemory().length);

  const persist = () => {
    saveLlmSettings(settings);
    setSavedHint(`已保存到本机浏览器 localStorage：${maskApiKey(settings.apiKey)}`);
    window.setTimeout(() => setSavedHint(''), 2600);
  };

  const reset = () => {
    setSettings(DEFAULT_LLM_SETTINGS);
    saveLlmSettings(DEFAULT_LLM_SETTINGS);
  };

  const clearMemory = () => {
    clearLlmMemory();
    setMemoryCount(0);
  };

  return (
    <div className="py-12 px-8">
      <div className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 mb-2">模型设置</h1>
        <p className="text-zinc-500 dark:text-zinc-300">配置真实大模型接口，用于主题重分类和触达策略生成。</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white dark:bg-zinc-800 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-700/50 shadow-sm">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-amber-50 text-amber-700"><KeyRound className="w-5 h-5" /></div>
            <div>
              <h2 className="font-semibold text-zinc-900 dark:text-zinc-100">OpenAI 兼容接口</h2>
              <p className="text-xs text-zinc-500 dark:text-zinc-300 mt-0.5">Key 只保存在当前浏览器本地，不上传到 GamePulse Python 服务端。</p>
            </div>
          </div>

          <div className="space-y-5">
            <label className="flex items-center gap-3 text-sm text-zinc-700 dark:text-zinc-300 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.enabled}
                onChange={e => setSettings(prev => ({ ...prev, enabled: e.target.checked }))}
                className="w-4 h-4 accent-zinc-900 cursor-pointer"
              />
              启用真实大模型增强
            </label>

            <div>
              <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-300 mb-1.5">Base URL</label>
              <input
                className="w-full rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 px-3 py-2 text-sm outline-none focus:border-amber-500"
                value={settings.baseUrl}
                onChange={e => setSettings(prev => ({ ...prev, baseUrl: e.target.value }))}
                placeholder="https://api.openai.com/v1"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-300 mb-1.5">API Key</label>
              <input
                type="password"
                className="w-full rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 px-3 py-2 text-sm outline-none focus:border-amber-500"
                value={settings.apiKey}
                onChange={e => setSettings(prev => ({ ...prev, apiKey: e.target.value }))}
                placeholder="sk-..."
                autoComplete="off"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-300 mb-1.5">模型名称</label>
              <input
                className="w-full rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 px-3 py-2 text-sm outline-none focus:border-amber-500"
                value={settings.model}
                onChange={e => setSettings(prev => ({ ...prev, model: e.target.value }))}
                placeholder="gpt-4o-mini / deepseek-chat / qwen-plus"
              />
            </div>
          </div>

          <div className="mt-6 flex items-center gap-3">
            <button onClick={persist} className="px-5 py-2.5 rounded-xl bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 text-sm font-semibold hover:opacity-90 cursor-pointer">保存本地配置</button>
            <button onClick={reset} className="px-4 py-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 text-sm text-zinc-600 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-700 cursor-pointer">恢复默认</button>
            {savedHint && <span className="text-xs text-emerald-600">{savedHint}</span>}
          </div>
        </div>

        <div className="bg-white dark:bg-zinc-800 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-700/50 shadow-sm h-fit">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 rounded-lg bg-zinc-100 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-200"><Database className="w-5 h-5" /></div>
            <h2 className="font-semibold text-zinc-900 dark:text-zinc-100">本地记忆缓存</h2>
          </div>
          <p className="text-sm text-zinc-500 dark:text-zinc-300 leading-relaxed mb-4">
            大模型返回的主题重分类和策略结果会缓存在本机 localStorage，用于相同数据重复分析时复用，减少请求和等待。
          </p>
          <div className="text-2xl font-mono text-zinc-900 dark:text-zinc-100 mb-4">{memoryCount}</div>
          <button onClick={clearMemory} className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 cursor-pointer">
            <Trash2 className="w-3.5 h-3.5" /> 清空本地缓存
          </button>
        </div>
      </div>
    </div>
  );
}
