import { useState, type CSSProperties } from 'react';
import { clearLlmMemory, DEFAULT_LLM_SETTINGS, fetchModelList, loadLlmMemory, loadLlmSettings, maskApiKey, saveLlmSettings, type LlmSettings, type ModelOption } from '../lib/llmClient';
import { KeyRound, Trash2, Database, RefreshCw, Eye, EyeOff } from 'lucide-react';
import { ProgressBar, type ProgressState } from '../components/ProgressBar';

export function ModelSettings() {
  const [settings, setSettings] = useState<LlmSettings>(() => loadLlmSettings());
  const [savedHint, setSavedHint] = useState('');
  const [modelStatus, setModelStatus] = useState('');
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [modelListProgress, setModelListProgress] = useState<ProgressState>(null);
  const [memoryCount, setMemoryCount] = useState(() => loadLlmMemory().length);
  const [showSecret, setShowSecret] = useState(false);

  const persist = () => {
    saveLlmSettings(settings);
    setSavedHint(`已保存到本机浏览器：${maskApiKey(settings.apiKey)}`);
    window.setTimeout(() => setSavedHint(''), 2600);
  };

  const reset = () => {
    setSettings(DEFAULT_LLM_SETTINGS);
    saveLlmSettings(DEFAULT_LLM_SETTINGS);
    setModels([]);
    setModelStatus('已恢复默认配置。');
  };

  const clearMemory = () => {
    clearLlmMemory();
    setMemoryCount(0);
  };

  const loadModels = async () => {
    setIsLoadingModels(true);
    setModelStatus('');
    setModelListProgress({ label: '正在连接模型服务...', value: 20 });
    try {
      setModelListProgress({ label: '正在获取可用模型列表...', value: 55 });
      const rows = await fetchModelList(settings);
      setModelListProgress({ label: '正在整理模型列表...', value: 85 });
      setModels(rows);
      const message = rows.length ? `已获取 ${rows.length} 个模型。` : '服务返回为空，可手动填写模型名。';
      setModelStatus(message);
      setModelListProgress({ label: message, value: 100 });
      window.setTimeout(() => setModelListProgress(null), 1500);
    } catch (err) {
      setModelStatus(err instanceof Error ? err.message : '模型列表获取失败。');
      setModelListProgress({ label: '模型列表获取失败，请检查服务地址和访问密钥。', value: 100 });
      window.setTimeout(() => setModelListProgress(null), 2200);
    } finally {
      setIsLoadingModels(false);
    }
  };

  return (
    <div className="py-12 px-8">
      <div className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 mb-2">模型设置</h1>
        <p className="text-zinc-500 dark:text-zinc-300">配置模型辅助分析：调用你填写的模型服务来辅助主题细分和触达策略生成，不是推理模式开关。</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white dark:bg-zinc-800 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-700/50 shadow-sm">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-amber-50 text-amber-700"><KeyRound className="w-5 h-5" /></div>
            <div>
              <h2 className="font-semibold text-zinc-900 dark:text-zinc-100">模型服务连接</h2>
              <p className="text-xs text-zinc-500 dark:text-zinc-300 mt-0.5">用于连接你自己的模型接口；密钥只保存在当前浏览器本地，不写入项目后端。</p>
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
              启用模型辅助分析
            </label>

            <div>
              <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-300 mb-1.5">服务地址</label>
              <input
                className="w-full rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 px-3 py-2 text-sm outline-none focus:border-amber-500"
                value={settings.baseUrl}
                onChange={e => setSettings(prev => ({ ...prev, baseUrl: e.target.value }))}
                placeholder="https://api.openai.com/v1"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-300 mb-1.5">访问密钥</label>
              <div className="relative">
                <input
                  type="text"
                  inputMode="text"
                  name="gamepulse-model-access-token"
                  autoComplete="new-password"
                  spellCheck={false}
                  className="w-full rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 px-3 py-2 pr-11 text-sm outline-none focus:border-amber-500"
                  value={settings.apiKey}
                  onChange={e => setSettings(prev => ({ ...prev, apiKey: e.target.value }))}
                  placeholder="粘贴模型服务访问密钥"
                  style={{ WebkitTextSecurity: showSecret ? 'none' : 'disc' } as CSSProperties}
                />
                <button
                  type="button"
                  onClick={() => setShowSecret(prev => !prev)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-lg text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-700 cursor-pointer"
                  aria-label={showSecret ? '隐藏密钥' : '显示密钥'}
                >
                  {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <p className="mt-1.5 text-[11px] text-zinc-400">这里不是登录表单；密钥仅用于浏览器直接请求模型服务。</p>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-300">模型名称</label>
                <button
                  onClick={loadModels}
                  disabled={isLoadingModels}
                  className="inline-flex items-center gap-1.5 text-xs text-amber-700 hover:text-amber-800 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isLoadingModels ? 'animate-spin' : ''}`} />
                  {isLoadingModels ? '获取中' : '获取模型列表'}
                </button>
              </div>
              <input
                className="w-full rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 px-3 py-2 text-sm outline-none focus:border-amber-500"
                value={settings.model}
                onChange={e => setSettings(prev => ({ ...prev, model: e.target.value }))}
                placeholder="gpt-4o-mini / deepseek-chat / qwen-plus"
                list="gamepulse-model-options"
              />
              <datalist id="gamepulse-model-options">
                {models.map(model => <option key={model.id} value={model.id} />)}
              </datalist>
              {models.length > 0 && (
                <div className="mt-3 max-h-44 overflow-auto rounded-xl border border-zinc-200 dark:border-zinc-700 divide-y divide-zinc-100 dark:divide-zinc-700/60">
                  {models.slice(0, 50).map(model => (
                    <button
                      key={model.id}
                      onClick={() => setSettings(prev => ({ ...prev, model: model.id }))}
                      className="w-full px-3 py-2 text-left text-xs hover:bg-amber-50 dark:hover:bg-zinc-700 cursor-pointer flex items-center justify-between gap-3"
                    >
                      <span className="truncate text-zinc-800 dark:text-zinc-100">{model.id}</span>
                      {model.owned_by && <span className="text-zinc-400 shrink-0">{model.owned_by}</span>}
                    </button>
                  ))}
                </div>
              )}
              <ProgressBar progress={modelListProgress} />
              {modelStatus && <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-300">{modelStatus}</p>}
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
            模型辅助分析返回的主题细分和策略结果会缓存在本机浏览器，用于相同数据重复分析时复用，减少等待。
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
