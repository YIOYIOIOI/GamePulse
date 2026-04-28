import React, { useState, useRef } from 'react';
import { useDataStore } from '../lib/useDataStore';
import { standardizeData } from '../lib/dataProcessor';
import { fetchSteamReviewsWithProgress, searchSteamAppsWithProgress, type SteamAppSearchResult } from '../lib/steamApi';
import Papa from 'papaparse';
import { Upload, Download, Trash2, CheckCircle2, PlusCircle, FileSpreadsheet, Check } from 'lucide-react';
import clsx from 'clsx';
import { ProgressBar, type ProgressState } from '../components/ProgressBar';

type OperationProgress = (ProgressState & { rows?: number }) | null;
type ToastState = { kind: 'success' | 'error' | 'info'; text: string } | null;

export function DataCenter({ onChangeView }: { onChangeView: (v: string) => void }) {
  const { data, status, appendData, clearData } = useDataStore();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isFetching, setIsFetching] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [searchProgress, setSearchProgress] = useState<OperationProgress>(null);
  const [fetchProgress, setFetchProgress] = useState<OperationProgress>(null);
  const [toast, setToast] = useState<ToastState>(null);
  const [selectedAppId, setSelectedAppId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SteamAppSearchResult[]>([]);
  const [steamConfig, setSteamConfig] = useState({
    gameName: 'DOTA 2',
    customName: '',
    appId: '570',
    count: 300,
    collectionMode: 'count' as 'count' | 'recentDays',
    recentDays: 14,
    reviewType: 'all'
  });


  const showToast = (next: ToastState) => {
    setToast(next);
    if (next) window.setTimeout(() => setToast(null), 2200);
  };

  const handleGameSearch = async () => {
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    setSearchProgress({ label: '准备搜索 Steam 商店...', value: 3 });
    try {
      const results = await searchSteamAppsWithProgress(searchQuery, event => {
        setSearchProgress({ label: event.message || '正在搜索 Steam 商店...', value: event.percent ?? 0, rows: event.rows });
      });
      setSearchResults(results);
      if (results.length > 0) {
        const first = results[0];
        setSelectedAppId(first.app_id);
        setSteamConfig(prev => ({ ...prev, gameName: 'Custom', customName: first.name, appId: String(first.app_id) }));
        showToast({ kind: 'success', text: `已自动选中：${first.name}` });
      } else {
        showToast({ kind: 'info', text: '没有找到候选游戏，请换一个关键词。' });
      }
      window.setTimeout(() => setSearchProgress(null), 1200);
    } catch (e) {
      setSearchProgress({ label: '搜索失败，请稍后重试', value: 100 });
      showToast({ kind: 'error', text: e instanceof Error ? e.message : 'Steam 游戏搜索失败。' });
      window.setTimeout(() => setSearchProgress(null), 1800);
    } finally {
      setIsSearching(false);
    }
  };

  const selectSearchResult = (app: SteamAppSearchResult) => {
    setSelectedAppId(app.app_id);
    setSteamConfig(prev => ({ ...prev, gameName: 'Custom', customName: app.name, appId: String(app.app_id) }));
    showToast({ kind: 'success', text: `已选择：${app.name}（AppID ${app.app_id}）` });
  };

  const handleSteamFetch = async () => {
    setIsFetching(true);
    setFetchProgress({ label: '正在连接 Steam 评论接口...', value: 3 });
    try {
      const finalGameName = steamConfig.gameName === 'Custom' ? (steamConfig.customName || '自定义游戏') : steamConfig.gameName;
      const rawData = await fetchSteamReviewsWithProgress({ ...steamConfig, gameName: finalGameName }, event => {
        setFetchProgress({ label: event.message || `正在采集《${finalGameName}》评论...`, value: event.percent ?? 0, rows: event.rows });
      });
      setFetchProgress({ label: `已采集 ${rawData.length.toLocaleString()} 条评论，正在标准化字段...`, value: 92 });
      const standardData = standardizeData(rawData, finalGameName);
      appendData(standardData, `Steam: ${finalGameName}`);
      setFetchProgress({ label: '采集完成，正在进入工作台...', value: 100 });
      showToast({ kind: 'success', text: `已采集 ${rawData.length.toLocaleString()} 条评论。` });
      window.setTimeout(() => {
        setFetchProgress(null);
        onChangeView('workbench');
      }, 500);
    } catch (e) {
      setFetchProgress({ label: '采集失败，请检查 App ID、网络或评论类型', value: 100 });
      showToast({ kind: 'error', text: e instanceof Error ? e.message : 'Steam 数据采集失败。' });
      window.setTimeout(() => setFetchProgress(null), 1800);
    } finally {
      setIsFetching(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        if (results.data.length === 0) {
          alert('CSV 为空或格式无效。');
          return;
        }
        const standardData = standardizeData(results.data, '上传数据集');
        appendData(standardData, `CSV: ${file.name}`);
        onChangeView('workbench');
      },
      error: (err) => {
        alert(`Error parsing CSV: ${err.message}`);
      }
    });

    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const loadLocalDemo = async () => {
    setIsFetching(true);
    setFetchProgress({ label: '正在加载项目样例...', value: 3 });
    try {
      const rawData = await fetchSteamReviewsWithProgress({ gameName: 'Elden Ring', appId: '1245620', count: 500, reviewType: 'all' }, event => {
        setFetchProgress({ label: event.message || '正在加载项目样例...', value: event.percent ?? 0, rows: event.rows });
      });
      const standardData = standardizeData(rawData, 'Elden Ring');
      appendData(standardData, '本地样例：elden_ring_reviews.csv');
      showToast({ kind: 'success', text: '项目样例已加载。' });
      window.setTimeout(() => {
        setFetchProgress(null);
        onChangeView('workbench');
      }, 500);
    } catch (e) {
      showToast({ kind: 'error', text: '项目样例加载失败。' });
      setFetchProgress(null);
    } finally {
      setIsFetching(false);
    }
  };

  return (
    <div className="py-12 px-8">
      <div className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50 mb-2">数据中心</h1>
        <p className="text-zinc-500 dark:text-zinc-300">采集或导入玩家评论，开始分析。</p>
      </div>

      {toast && (
        <div className={clsx(
          "fixed top-5 right-6 z-50 rounded-2xl px-4 py-3 text-sm shadow-xl border backdrop-blur cursor-default",
          toast.kind === 'success' && "bg-emerald-50/95 border-emerald-200 text-emerald-800",
          toast.kind === 'error' && "bg-red-50/95 border-red-200 text-red-800",
          toast.kind === 'info' && "bg-zinc-50/95 border-zinc-200 text-zinc-700"
        )}>
          {toast.text}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* Steam Source */}
        <div className="bg-white dark:bg-zinc-800 rounded-2xl p-6 shadow-sm border border-zinc-200 dark:border-zinc-700/50 flex flex-col relative overflow-hidden transition-colors">
           <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-orange-500 via-amber-500 to-stone-700"></div>
           <div className="flex items-center gap-3 mb-6">
             <div className="p-2.5 bg-orange-50 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400 rounded-lg">
                <Download className="w-5 h-5" />
             </div>
             <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">Steam 评论采集</h2>
           </div>

           <div className="space-y-4 flex-1">
             <div>
               <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-300 uppercase tracking-wider mb-1.5">搜索 Steam 游戏</label>
               <div className="flex gap-2">
                 <input
                   className="flex-1 bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-colors"
                   value={searchQuery}
                   placeholder="输入游戏名称搜索"
                   onChange={e => setSearchQuery(e.target.value)}
                   onKeyDown={e => { if (e.key === 'Enter') handleGameSearch(); }}
                 />
                 <button
                   onClick={handleGameSearch}
                   disabled={isSearching}
                   className="px-4 py-2 bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 rounded-lg text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90 cursor-pointer transition-all"
                 >
                   {isSearching ? '搜索中...' : '搜索'}
                 </button>
               </div>
               <ProgressBar progress={searchProgress} />
               {searchResults.length > 0 && (
                 <div className="mt-3 border border-zinc-200 dark:border-zinc-700 rounded-xl overflow-hidden divide-y divide-zinc-100 dark:divide-zinc-700/60">
                   {searchResults.slice(0, 5).map(app => (
                     <button key={app.app_id} onClick={() => selectSearchResult(app)} className={clsx("w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-orange-50 dark:hover:bg-zinc-700/40 transition-colors cursor-pointer", selectedAppId === app.app_id && "bg-orange-50 dark:bg-orange-900/20")}>
                       {app.tiny_image && <img src={app.tiny_image} alt="" className="w-16 h-8 object-cover rounded" />}
                       <span className="flex-1 text-sm text-zinc-800 dark:text-zinc-100">{app.name}</span>
                       <span className="text-xs font-mono text-zinc-500">{app.app_id}</span>{selectedAppId === app.app_id && <Check className="w-4 h-4 text-orange-500" />}
                     </button>
                   ))}
                 </div>
               )}
             </div>

             <div className="flex gap-4">
               <div className="flex-1">
                 <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-300 uppercase tracking-wider mb-1.5">游戏名称</label>
                 <select
                   className="w-full bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-colors"
                   value={steamConfig.gameName}
                   onChange={e => {
                     const val = e.target.value;
                     const newConfig = { ...steamConfig, gameName: val };
                     if (val === 'DOTA 2') newConfig.appId = '570';
                     else if (val === 'Elden Ring') newConfig.appId = '1245620';
                     else if (val === "Baldur's Gate 3") newConfig.appId = '1086940';
                     else if (val === 'Cyberpunk 2077') newConfig.appId = '1091500';
                     else newConfig.appId = ''; // Custom
                     setSteamConfig(newConfig);
                   }}
                 >
                   <option value="DOTA 2">DOTA 2</option>
                   <option value="Elden Ring">Elden Ring</option>
                   <option value="Baldur's Gate 3">Baldur's Gate 3</option>
                   <option value="Cyberpunk 2077">Cyberpunk 2077</option>
                   <option value="Custom">自定义游戏</option>
                 </select>
               </div>

               {steamConfig.gameName === 'Custom' && (
                 <div className="flex-1">
                   <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-300 uppercase tracking-wider mb-1.5">自定义名称</label>
                   <input
                     className="w-full bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-colors"
                     value={steamConfig.customName || ''}
                     placeholder="输入游戏名称"
                     onChange={e => setSteamConfig({...steamConfig, customName: e.target.value})}
                   />
                 </div>
               )}
             </div>

             <div>
               <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-300 uppercase tracking-wider mb-1.5">采集模式</label>
               <div className="grid grid-cols-2 gap-3">
                 <button
                   type="button"
                   onClick={() => setSteamConfig({ ...steamConfig, collectionMode: 'count' })}
                   className={clsx("rounded-xl border px-3 py-2 text-sm text-left cursor-pointer transition-colors", steamConfig.collectionMode === 'count' ? "border-orange-500 bg-orange-50 text-orange-800 dark:bg-orange-900/20 dark:text-orange-200" : "border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-700/40")}
                 >
                   <div className="font-semibold">按数量采集</div>
                   <div className="text-xs opacity-70 mt-0.5">抓最近排序的前 N 条</div>
                 </button>
                 <button
                   type="button"
                   onClick={() => setSteamConfig({ ...steamConfig, collectionMode: 'recentDays' })}
                   className={clsx("rounded-xl border px-3 py-2 text-sm text-left cursor-pointer transition-colors", steamConfig.collectionMode === 'recentDays' ? "border-orange-500 bg-orange-50 text-orange-800 dark:bg-orange-900/20 dark:text-orange-200" : "border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-700/40")}
                 >
                   <div className="font-semibold">采集最近 N 天</div>
                   <div className="text-xs opacity-70 mt-0.5">持续翻页直到覆盖时间窗口</div>
                 </button>
               </div>
             </div>

             <div className="flex gap-4">
               <div className="w-1/3">
                 <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-300 uppercase tracking-wider mb-1.5">App ID</label>
                 <input
                   className="w-full bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-orange-500 transition-colors"
                   value={steamConfig.appId}
                   onChange={e => setSteamConfig({...steamConfig, appId: e.target.value})}
                 />
               </div>
               <div className="flex-1">
                 {steamConfig.collectionMode === 'recentDays' ? (
                   <>
                     <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-300 uppercase tracking-wider mb-1.5 flex justify-between">
                       <span>最近天数</span>
                       <span className="font-mono">{steamConfig.recentDays} 天</span>
                     </label>
                     <div className="flex items-center gap-3">
                       <input
                         type="range"
                         min="1"
                         max="90"
                         step="1"
                         className="w-full h-2 bg-zinc-200 dark:bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-orange-600"
                         value={steamConfig.recentDays}
                         onChange={e => setSteamConfig({...steamConfig, recentDays: Number(e.target.value)})}
                       />
                       <input
                         type="number"
                         min="1"
                         className="w-20 bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 rounded-lg px-2 py-1 text-sm font-mono focus:outline-none focus:border-orange-500 transition-colors"
                         value={steamConfig.recentDays}
                         onChange={e => setSteamConfig({...steamConfig, recentDays: Number(e.target.value)})}
                       />
                     </div>
                     <p className="mt-1.5 text-xs text-zinc-400">会从最新评论开始持续翻页，直到遇到早于该时间窗口的评论。</p>
                   </>
                 ) : (
                   <>
                     <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-300 uppercase tracking-wider mb-1.5 flex justify-between">
                       <span>采集数量</span>
                       <span className="font-mono">{steamConfig.count}</span>
                     </label>
                     <div className="flex items-center gap-3">
                       <input
                         type="range"
                         min="100"
                         max="5000"
                         step="100"
                         className="w-full h-2 bg-zinc-200 dark:bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-orange-600"
                         value={steamConfig.count}
                         onChange={e => setSteamConfig({...steamConfig, count: Number(e.target.value)})}
                       />
                       <input
                         type="number"
                         className="w-20 bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 rounded-lg px-2 py-1 text-sm font-mono focus:outline-none focus:border-orange-500 transition-colors"
                         value={steamConfig.count}
                         onChange={e => setSteamConfig({...steamConfig, count: Number(e.target.value)})}
                       />
                     </div>
                   </>
                 )}
               </div>
             </div>
             <div>
                <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-300 uppercase tracking-wider mb-1.5">评论类型</label>
                <select
                  className="w-full bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-orange-500 transition-colors"
                  value={steamConfig.reviewType}
                  onChange={e => setSteamConfig({...steamConfig, reviewType: e.target.value})}
                >
                  <option value="all">全部评论</option>
                  <option value="positive">仅好评</option>
                  <option value="negative">仅差评</option>
                </select>
             </div>
           </div>

           <ProgressBar progress={fetchProgress} />

           <button
             onClick={handleSteamFetch}
             disabled={isFetching}
             className={clsx(
               "mt-6 w-full py-2.5 rounded-lg text-sm font-semibold transition-colors flex items-center justify-center gap-2",
               isFetching ? "bg-zinc-100 dark:bg-zinc-800 text-zinc-400 dark:text-zinc-300 cursor-not-allowed" : "bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 hover:bg-zinc-800 dark:hover:bg-zinc-100 cursor-pointer"
             )}
           >
             {isFetching ? '采集中...' : '采集 Steam 数据'}
           </button>
        </div>

        {/* 本地上传 */}
        <div className="flex flex-col gap-6">

          <div className="bg-white dark:bg-zinc-800 rounded-2xl p-6 shadow-sm border border-zinc-200 dark:border-zinc-700/50 relative overflow-hidden flex-1 flex flex-col justify-center transition-colors">
             <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-emerald-500 to-teal-500"></div>
             <div className="flex flex-col items-center justify-center text-center">
               <div className="p-3 bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 rounded-full mb-4">
                  <Upload className="w-6 h-6" />
               </div>
               <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-1">上传 CSV</h3>
               <p className="text-sm text-zinc-500 dark:text-zinc-300 mb-6 w-3/4 mx-auto">上传自己的评论数据集，至少需要评论文本和情绪/评分字段。</p>

               <input
                 type="file"
                 accept=".csv"
                 ref={fileInputRef}
                 className="hidden"
                 onChange={handleFileUpload}
               />
               <button
                  onClick={() => fileInputRef.current?.click()}
                  className="px-6 py-2 border border-zinc-300 dark:border-zinc-700 rounded-full text-sm font-medium hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors cursor-pointer text-zinc-700 dark:text-zinc-300"
               >
                 选择 CSV 文件
               </button>
             </div>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-2xl p-6 shadow-sm border border-zinc-200 dark:border-zinc-700/50 relative overflow-hidden flex items-center gap-4 transition-colors">
             <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-amber-500 to-orange-500"></div>
             <div className="p-3 bg-amber-50 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400 rounded-full shrink-0">
                <FileSpreadsheet className="w-5 h-5" />
             </div>
             <div>
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm">加载项目样例</h3>
                <p className="text-xs text-zinc-500 dark:text-zinc-300 mt-0.5">加载项目内置样例数据</p>
             </div>
             <button
                onClick={loadLocalDemo}
                disabled={isFetching}
                className="ml-auto px-4 py-1.5 bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 cursor-pointer text-zinc-700 dark:text-zinc-300 text-xs font-semibold rounded-lg transition-colors border border-zinc-300 dark:border-zinc-700"
              >
                加载
             </button>
          </div>

        </div>

      </div>

      {status.totalRecords > 0 && (
        <div className="mt-12">
          <div className="flex items-center justify-between mb-4 border-b border-zinc-200 dark:border-zinc-700/50 pb-4">
            <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">当前工作数据集</h3>
            <button
              onClick={clearData}
              className="px-3 py-1.5 text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-colors flex items-center gap-1.5"
            >
              <Trash2 className="w-3.5 h-3.5" />
              清空数据集
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
             <div className="bg-zinc-50 dark:bg-zinc-800 rounded-xl p-4 border border-zinc-100 dark:border-zinc-700/50/50">
               <div className="text-xs text-zinc-500 dark:text-zinc-300 font-semibold mb-1">总记录数</div>
               <div className="text-2xl font-light font-mono text-zinc-800 dark:text-zinc-200">{status.totalRecords.toLocaleString()}</div>
             </div>
             <div className="bg-zinc-50 dark:bg-zinc-800 rounded-xl p-4 border border-zinc-100 dark:border-zinc-700/50/50">
               <div className="text-xs text-zinc-500 dark:text-zinc-300 font-semibold mb-1">游戏数</div>
               <div className="text-2xl font-light font-mono text-zinc-800 dark:text-zinc-200">{status.gamesCount}</div>
             </div>
             <div className="bg-zinc-50 dark:bg-zinc-800 rounded-xl p-4 border border-zinc-100 dark:border-zinc-700/50/50 md:col-span-2">
               <div className="text-xs text-zinc-500 dark:text-zinc-300 font-semibold mb-1.5">数据来源</div>
               <div className="flex flex-wrap gap-2">
                 {status.dataSources.map(s => (
                   <span key={s} className="px-2 py-1 bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-xs text-zinc-600 dark:text-zinc-300 rounded-md truncate max-w-full">
                     {s}
                   </span>
                 ))}
               </div>
             </div>
          </div>
        </div>
      )}
    </div>
  );
}
