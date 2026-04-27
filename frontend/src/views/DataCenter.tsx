import React, { useState, useRef } from 'react';
import { useDataStore } from '../lib/useDataStore';
import { standardizeData } from '../lib/dataProcessor';
import { fetchSteamReviews, searchSteamApps, type SteamAppSearchResult } from '../lib/steamApi';
import Papa from 'papaparse';
import { Upload, Download, Trash2, CheckCircle2, PlusCircle, FileSpreadsheet } from 'lucide-react';
import clsx from 'clsx';

type OperationProgress = { label: string; value: number } | null;

function ProgressBar({ progress }: { progress: OperationProgress }) {
  if (!progress) return null;
  return (
    <div className="mt-3 rounded-xl border border-blue-100 dark:border-blue-900/40 bg-blue-50/70 dark:bg-blue-950/20 px-3 py-2">
      <div className="flex items-center justify-between text-xs mb-2">
        <span className="font-medium text-blue-700 dark:text-blue-300">{progress.label}</span>
        <span className="font-mono text-blue-600 dark:text-blue-300">{Math.round(progress.value)}%</span>
      </div>
      <div className="h-2 rounded-full bg-blue-100 dark:bg-blue-900/50 overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-blue-600 to-indigo-500 transition-all duration-300 ease-out"
          style={{ width: `${Math.min(100, Math.max(0, progress.value))}%` }}
        />
      </div>
    </div>
  );
}

export function DataCenter({ onChangeView }: { onChangeView: (v: string) => void }) {
  const { data, status, appendData, clearData } = useDataStore();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isFetching, setIsFetching] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [searchProgress, setSearchProgress] = useState<OperationProgress>(null);
  const [fetchProgress, setFetchProgress] = useState<OperationProgress>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SteamAppSearchResult[]>([]);
  const [steamConfig, setSteamConfig] = useState({
    gameName: 'DOTA 2',
    customName: '',
    appId: '570',
    count: 300,
    reviewType: 'all'
  });


  const handleGameSearch = async () => {
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    setSearchProgress({ label: '正在连接 Steam 搜索服务...', value: 12 });
    const timer = window.setInterval(() => {
      setSearchProgress(prev => prev ? { ...prev, value: Math.min(prev.value + 14, 86) } : prev);
    }, 350);
    try {
      setSearchProgress({ label: '正在搜索候选游戏...', value: 28 });
      const results = await searchSteamApps(searchQuery);
      setSearchProgress({ label: results.length > 0 ? `找到 ${results.length} 个候选游戏` : '没有找到候选游戏', value: 100 });
      setSearchResults(results);
      if (results.length > 0) {
        const first = results[0];
        setSteamConfig(prev => ({ ...prev, gameName: 'Custom', customName: first.name, appId: String(first.app_id) }));
      }
      window.setTimeout(() => setSearchProgress(null), 1200);
    } catch (e) {
      setSearchProgress({ label: '搜索失败，请稍后重试', value: 100 });
      alert(e instanceof Error ? e.message : 'Steam 游戏搜索失败。');
      window.setTimeout(() => setSearchProgress(null), 1600);
    } finally {
      window.clearInterval(timer);
      setIsSearching(false);
    }
  };

  const selectSearchResult = (app: SteamAppSearchResult) => {
    setSteamConfig(prev => ({ ...prev, gameName: 'Custom', customName: app.name, appId: String(app.app_id) }));
  };

  const handleSteamFetch = async () => {
    setIsFetching(true);
    setFetchProgress({ label: '正在连接 Steam 评论接口...', value: 8 });
    const timer = window.setInterval(() => {
      setFetchProgress(prev => {
        if (!prev) return prev;
        const step = steamConfig.count >= 2000 ? 4 : steamConfig.count >= 1000 ? 6 : 9;
        return { ...prev, value: Math.min(prev.value + step, 88) };
      });
    }, 500);
    try {
      const finalGameName = steamConfig.gameName === 'Custom' ? (steamConfig.customName || 'Custom Game') : steamConfig.gameName;
      setFetchProgress({ label: `正在采集《${finalGameName}》评论...`, value: 18 });
      const rawData = await fetchSteamReviews({ ...steamConfig, gameName: finalGameName });
      setFetchProgress({ label: `已采集 ${rawData.length.toLocaleString()} 条评论，正在标准化字段...`, value: 92 });
      const standardData = standardizeData(rawData, finalGameName);
      appendData(standardData, `Steam: ${finalGameName}`);
      setFetchProgress({ label: '采集完成，正在进入工作台...', value: 100 });
      window.setTimeout(() => {
        setFetchProgress(null);
        onChangeView('workbench');
      }, 500);
    } catch (e) {
      setFetchProgress({ label: '采集失败，请检查 App ID、网络或评论类型', value: 100 });
      alert(e instanceof Error ? e.message : 'Steam 数据采集失败。');
      window.setTimeout(() => setFetchProgress(null), 1800);
    } finally {
      window.clearInterval(timer);
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
        const standardData = standardizeData(results.data, 'Uploaded Custom Game');
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
    try {
      // Simulate loading local file by using our steam mock
      const rawData = await fetchSteamReviews({ gameName: 'Elden Ring', appId: '1245620', count: 500, reviewType: 'all' });
      const standardData = standardizeData(rawData, 'Elden Ring');
      appendData(standardData, 'Local: elden_ring_reviews.csv');
      onChangeView('workbench');
    } catch (e) {
      alert('项目样例加载失败。');
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

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* Steam Source */}
        <div className="bg-white dark:bg-zinc-800 rounded-2xl p-6 shadow-sm border border-zinc-200 dark:border-zinc-700/50 flex flex-col relative overflow-hidden transition-colors">
           <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-600 to-indigo-600"></div>
           <div className="flex items-center gap-3 mb-6">
             <div className="p-2.5 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-lg">
                <Download className="w-5 h-5" />
             </div>
             <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">Steam 评论采集</h2>
           </div>

           <div className="space-y-4 flex-1">
             <div>
               <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-300 uppercase tracking-wider mb-1.5">搜索 Steam 游戏</label>
               <div className="flex gap-2">
                 <input
                   className="flex-1 bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-colors"
                   value={searchQuery}
                   placeholder="输入游戏名称搜索"
                   onChange={e => setSearchQuery(e.target.value)}
                   onKeyDown={e => { if (e.key === 'Enter') handleGameSearch(); }}
                 />
                 <button
                   onClick={handleGameSearch}
                   disabled={isSearching}
                   className="px-4 py-2 bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 rounded-lg text-sm font-semibold disabled:opacity-50"
                 >
                   {isSearching ? '搜索中...' : '搜索'}
                 </button>
               </div>
               <ProgressBar progress={searchProgress} />
               {searchResults.length > 0 && (
                 <div className="mt-3 border border-zinc-200 dark:border-zinc-700 rounded-xl overflow-hidden divide-y divide-zinc-100 dark:divide-zinc-700/60">
                   {searchResults.slice(0, 5).map(app => (
                     <button key={app.app_id} onClick={() => selectSearchResult(app)} className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-zinc-50 dark:hover:bg-zinc-700/40 transition-colors">
                       {app.tiny_image && <img src={app.tiny_image} alt="" className="w-16 h-8 object-cover rounded" />}
                       <span className="flex-1 text-sm text-zinc-800 dark:text-zinc-100">{app.name}</span>
                       <span className="text-xs font-mono text-zinc-500">{app.app_id}</span>
                     </button>
                   ))}
                 </div>
               )}
             </div>

             <div className="flex gap-4">
               <div className="flex-1">
                 <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-300 uppercase tracking-wider mb-1.5">游戏名称</label>
                 <select
                   className="w-full bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-colors"
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
                     className="w-full bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-colors"
                     value={steamConfig.customName || ''}
                     placeholder="输入游戏名称"
                     onChange={e => setSteamConfig({...steamConfig, customName: e.target.value})}
                   />
                 </div>
               )}
             </div>

             <div className="flex gap-4">
               <div className="w-1/3">
                 <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-300 uppercase tracking-wider mb-1.5">App ID</label>
                 <input
                   className="w-full bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-blue-500 transition-colors"
                   value={steamConfig.appId}
                   onChange={e => setSteamConfig({...steamConfig, appId: e.target.value})}
                 />
               </div>
               <div className="flex-1">
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
                     className="w-full h-2 bg-zinc-200 dark:bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-blue-600"
                     value={steamConfig.count}
                     onChange={e => setSteamConfig({...steamConfig, count: Number(e.target.value)})}
                   />
                   <input
                     type="number"
                     className="w-20 bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 rounded-lg px-2 py-1 text-sm font-mono focus:outline-none focus:border-blue-500 transition-colors"
                     value={steamConfig.count}
                     onChange={e => setSteamConfig({...steamConfig, count: Number(e.target.value)})}
                   />
                 </div>
               </div>
             </div>
             <div>
                <label className="block text-xs font-semibold text-zinc-500 dark:text-zinc-300 uppercase tracking-wider mb-1.5">评论类型</label>
                <select
                  className="w-full bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 transition-colors"
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
               isFetching ? "bg-zinc-100 dark:bg-zinc-800 text-zinc-400 dark:text-zinc-300 cursor-not-allowed" : "bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 hover:bg-zinc-800 dark:hover:bg-zinc-100"
             )}
           >
             {isFetching ? '采集中...' : '采集 Steam 数据'}
           </button>
        </div>

        {/* Local / Upload Source */}
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
                  className="px-6 py-2 border border-zinc-300 dark:border-zinc-700 rounded-full text-sm font-medium hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors text-zinc-700 dark:text-zinc-300"
               >
                 Select CSV File
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
                className="ml-auto px-4 py-1.5 bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 text-zinc-700 dark:text-zinc-300 text-xs font-semibold rounded-lg transition-colors border border-zinc-300 dark:border-zinc-700"
              >
                Load
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
              Clear Dataset
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
