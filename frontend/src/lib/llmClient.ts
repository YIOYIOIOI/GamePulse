import { Review } from './useDataStore';

export type LlmSettings = {
  enabled: boolean;
  baseUrl: string;
  apiKey: string;
  model: string;
};

const SETTINGS_KEY = 'gamepulse.localLlm.settings.v1';
const MEMORY_KEY = 'gamepulse.localLlm.memory.v1';

export const DEFAULT_LLM_SETTINGS: LlmSettings = {
  enabled: false,
  baseUrl: 'https://api.openai.com/v1',
  apiKey: '',
  model: 'gpt-4o-mini',
};

export function loadLlmSettings(): LlmSettings {
  try {
    const raw = window.localStorage.getItem(SETTINGS_KEY);
    if (!raw) return DEFAULT_LLM_SETTINGS;
    return { ...DEFAULT_LLM_SETTINGS, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_LLM_SETTINGS;
  }
}

export function saveLlmSettings(settings: LlmSettings) {
  window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
}

export type LlmMemoryEntry = {
  id: string;
  type: 'topic-classification' | 'strategy';
  createdAt: string;
  model: string;
  inputHash: string;
  summary: string;
  result: unknown;
};

export function loadLlmMemory(): LlmMemoryEntry[] {
  try {
    const raw = window.localStorage.getItem(MEMORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function rememberLlmResult(entry: Omit<LlmMemoryEntry, 'id' | 'createdAt'>) {
  const next: LlmMemoryEntry = {
    ...entry,
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    createdAt: new Date().toISOString(),
  };
  const memory = [next, ...loadLlmMemory()].slice(0, 20);
  window.localStorage.setItem(MEMORY_KEY, JSON.stringify(memory));
  return next;
}

export function clearLlmMemory() {
  window.localStorage.removeItem(MEMORY_KEY);
}

export function maskApiKey(key: string) {
  if (!key) return '未配置';
  if (key.length <= 8) return '已配置';
  return `${key.slice(0, 4)}••••${key.slice(-4)}`;
}

export async function hashText(text: string): Promise<string> {
  const bytes = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function callOpenAICompatible(settings: LlmSettings, messages: Array<{ role: 'system' | 'user' | 'assistant'; content: string }>) {
  if (!settings.enabled || !settings.baseUrl || !settings.apiKey || !settings.model) {
    throw new Error('请先在本地配置大模型 API。');
  }
  const base = settings.baseUrl.replace(/\/$/, '');
  const res = await fetch(`${base}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${settings.apiKey}`,
    },
    body: JSON.stringify({
      model: settings.model,
      temperature: 0.2,
      response_format: { type: 'json_object' },
      messages,
    }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`大模型调用失败：HTTP ${res.status}${text ? ` - ${text.slice(0, 200)}` : ''}`);
  }
  const payload = await res.json();
  const content = payload.choices?.[0]?.message?.content;
  if (!content) throw new Error('大模型没有返回内容。');
  return JSON.parse(content);
}

const TAXONOMY = [
  '匹配与排位体验', '外挂与公平性', '平衡性与数值', '服务器与网络', '性能与稳定性', '操作与手感',
  '新手引导与学习成本', '内容更新与活动', '商业化与价格', '社区氛围与沟通', '美术、音效与沉浸感',
  '剧情与世界观', '账号、登录与安装', '本地化与语言', '客服与运营响应', '正向综合反馈', '负向综合反馈', '综合体验反馈'
];

export async function classifyTopicsWithLlm(reviews: Review[]) {
  const settings = loadLlmSettings();
  const samples = reviews.slice(0, 120).map((r, index) => ({
    index,
    sentiment: r.sentiment,
    current_topic: r.topic_description || '',
    text: r.review_text.slice(0, 600),
  }));
  const inputHash = await hashText(JSON.stringify(samples));
  const cached = loadLlmMemory().find(m => m.type === 'topic-classification' && m.inputHash === inputHash && m.model === settings.model);
  if (cached) return { fromCache: true, result: cached.result as { topics: Array<{ index: number; topic: string; confidence?: number; reason?: string }> } };

  const result = await callOpenAICompatible(settings, [
    {
      role: 'system',
      content: '你是游戏用户反馈分析专家。只返回 JSON。不要编造评论不存在的信息。主题必须从给定 taxonomy 中选择。',
    },
    {
      role: 'user',
      content: JSON.stringify({
        task: '为每条 Steam 评论选择最合适的中文主题。避免把大量评论都归为综合反馈；只有确实无法判断时才使用综合类。',
        taxonomy: TAXONOMY,
        output_schema: { topics: [{ index: 0, topic: '主题名', confidence: 0.0, reason: '不超过20字' }] },
        reviews: samples,
      }),
    },
  ]);
  rememberLlmResult({ type: 'topic-classification', model: settings.model, inputHash, summary: `主题重分类 ${samples.length} 条评论`, result });
  return { fromCache: false, result: result as { topics: Array<{ index: number; topic: string; confidence?: number; reason?: string }> } };
}

export async function generateStrategyWithLlm(payload: unknown) {
  const settings = loadLlmSettings();
  const inputHash = await hashText(JSON.stringify(payload));
  const cached = loadLlmMemory().find(m => m.type === 'strategy' && m.inputHash === inputHash && m.model === settings.model);
  if (cached) return { fromCache: true, result: cached.result as { strategies: unknown[] } };

  const result = await callOpenAICompatible(settings, [
    {
      role: 'system',
      content: '你是资深游戏运营策略专家。只返回 JSON。基于证据输出可执行触达策略，不要声称拥有真实付费、留存或LTV数据。',
    },
    {
      role: 'user',
      content: JSON.stringify({
        task: '根据玩家分层、负向占比、主要主题和评论样本，生成中文 CRM 触达策略。',
        output_schema: {
          strategies: [{ group: '新手玩家', goal: '策略目标', tone: '建议语气', advice: '运营建议', draft: '参考文案' }]
        },
        data: payload,
      }),
    },
  ]);
  rememberLlmResult({ type: 'strategy', model: settings.model, inputHash, summary: '触达策略生成', result });
  return { fromCache: false, result: result as { strategies: unknown[] } };
}
