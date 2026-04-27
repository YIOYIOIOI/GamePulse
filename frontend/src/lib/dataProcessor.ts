import { Review } from './useDataStore';

export function standardizeData(rawData: any[], defaultGameName: string = '未知游戏'): Review[] {
  return rawData.map((row) => {
    // 1. Time Field Standardization
    let timestamp_created: Date | undefined;
    const timeFields = ['timestamp_created', 'created_at', 'year_month', 'date'];
    for (const field of timeFields) {
      if (row[field]) {
        const parsed = new Date(row[field]);
        if (!isNaN(parsed.getTime())) {
          timestamp_created = parsed;
          break;
        }
      }
    }

    // 2. Game Name
    const game_name = row.game_name || defaultGameName;

    // 3. Sentiment field
    let sentiment: 'positive' | 'negative' | 'neutral' = 'neutral';
    if (row.sentiment) {
      const s = String(row.sentiment).toLowerCase();
      if (s.includes('pos') || s.includes('正') || s.includes('好评') || s === '1' || s === 'true') sentiment = 'positive';
      else if (s.includes('neg') || s.includes('负') || s.includes('差评') || s === '0' || s === 'false') sentiment = 'negative';
    } else if (row.vote_up !== undefined) {
      sentiment = String(row.vote_up) === 'true' || String(row.vote_up) === '1' ? 'positive' : 'negative';
    }

    // 4. Topic extraction
    let topic_description = normalizeTopicLabel(row.topic_description || row.topic || row.theme);
    let topic_source = row.topic_source || '数据集字段';

    // If topic is missing, too generic, or looks like raw word bags, classify from text.
    if (!topic_description || isWeakTopic(topic_description)) {
      const text = String(row.review_text || row.review || row.text || row.content || '').toLowerCase();
      topic_description = extractTopic(text, sentiment);
      topic_source = '关键词归类';
    }

    // 5. Playtime extraction
    let playtime_forever: number | undefined;
    if (row.playtime_forever !== undefined && !isNaN(Number(row.playtime_forever))) {
      playtime_forever = Number(row.playtime_forever);
    } else if (row.playtime_at_review !== undefined && !isNaN(Number(row.playtime_at_review))) {
      playtime_forever = Number(row.playtime_at_review);
    } else if (row.playtime !== undefined && !isNaN(Number(row.playtime))) {
      playtime_forever = Number(row.playtime);
    }

    // 6. Player Type and derived metrics
    const player_type = normalizePlayerType(row.player_type) || classifyPlayer(playtime_forever);

    const value_potential_score = calculateValuePotential(playtime_forever, sentiment);
    const churn_risk_proxy = calculateChurnRisk(playtime_forever, sentiment);
    const crm_priority = prioritizeCRM(churn_risk_proxy, value_potential_score);

    return {
      review_text: String(row.review_text || row.review || row.text || row.content || ''),
      sentiment,
      game_name,
      topic_description,
      player_type,
      playtime_forever,
      timestamp_created,
      topic_source,
      value_potential_score,
      churn_risk_proxy,
      crm_priority,
    };
  });
}

type TopicRule = { label: string; keywords: string[] };

const TOPIC_RULES: TopicRule[] = [
  { label: '匹配与排位体验', keywords: ['matchmaking', 'match making', 'rank', 'ranked', 'mmr', 'elo', 'teammate', '队友', '匹配', '排位', '段位', '上分', '掉分'] },
  { label: '外挂与公平性', keywords: ['cheat', 'cheater', 'hack', 'hacker', 'aimbot', 'wallhack', 'smurf', 'script', '外挂', '开挂', '脚本', '小号', '炸鱼', '不公平'] },
  { label: '平衡性与数值', keywords: ['balance', 'nerf', 'buff', 'overpowered', 'op ', 'meta', 'broken hero', 'weapon', 'damage', 'skill', '平衡', '削弱', '加强', '超模', '强度', '数值', '英雄', '武器', '技能'] },
  { label: '服务器与网络', keywords: ['server', 'ping', 'latency', 'lag', 'disconnect', 'connection', 'rubberband', 'desync', 'packet', '服务器', '延迟', '掉线', '断连', '网络', '卡顿', '丢包'] },
  { label: '性能与稳定性', keywords: ['fps', 'frame', 'stutter', 'crash', 'freeze', 'bug', 'glitch', 'performance', 'optimization', '性能', '帧率', '掉帧', '闪退', '崩溃', '卡死', '优化', 'bug', '漏洞'] },
  { label: '操作与手感', keywords: ['control', 'camera', 'input', 'hitbox', 'combat', 'movement', 'clunky', 'feel', '操作', '手感', '镜头', '打击感', '判定', '按键', '连招', '动作'] },
  { label: '新手引导与学习成本', keywords: ['tutorial', 'beginner', 'new player', 'learn', 'learning curve', 'confusing', 'hard to understand', '新手', '教程', '引导', '入门', '学习成本', '看不懂', '不会玩'] },
  { label: '内容更新与活动', keywords: ['update', 'patch', 'event', 'season', 'content', 'map', 'mode', 'dlc', 'expansion', '更新', '补丁', '活动', '赛季', '内容', '地图', '模式', '联动'] },
  { label: '商业化与价格', keywords: ['price', 'expensive', 'pay', 'paid', 'money', 'skin', 'battle pass', 'microtransaction', 'mtx', 'gacha', 'p2w', '价格', '太贵', '付费', '氪金', '皮肤', '通行证', '抽卡', '骗氪'] },
  { label: '社区氛围与沟通', keywords: ['toxic', 'toxicity', 'community', 'chat', 'voice', 'report', 'grief', 'flame', 'abuse', '社区', '喷子', '嘴臭', '辱骂', '举报', '语音', '聊天', '恶意'] },
  { label: '美术、音效与沉浸感', keywords: ['graphics', 'visual', 'art', 'music', 'sound', 'audio', 'animation', 'beautiful', '画面', '美术', '建模', '音效', '音乐', '动画', '沉浸'] },
  { label: '剧情与世界观', keywords: ['story', 'plot', 'character', 'lore', 'dialogue', 'quest', '剧情', '故事', '角色', '世界观', '任务', '文本'] },
  { label: '账号、登录与安装', keywords: ['login', 'account', 'launcher', 'download', 'install', 'verify', 'ban', '登录', '账号', '启动器', '下载', '安装', '验证', '封号'] },
  { label: '本地化与语言', keywords: ['translation', 'localization', 'language', 'subtitle', '中文', '翻译', '本地化', '语言', '字幕'] },
  { label: '客服与运营响应', keywords: ['support', 'customer service', 'devs', 'developer', 'feedback', 'roadmap', '客服', '工单', '官方', '开发者', '运营', '反馈', '路线图'] },
];

const TOPIC_LABEL_MAP: Record<string, string> = {
  'Matchmaking & Fairness': '匹配与公平性',
  'Performance & Stability': '性能与稳定性',
  'New Player Experience': '新手引导与学习成本',
  'Content & Updates': '内容更新与活动',
  'Monetization': '商业化与价格',
  'Community & Toxicity': '社区氛围与沟通',
  'General Feedback': '综合体验反馈',
  'Uncategorized': '未分类反馈',
  'General': '综合体验反馈',
};

export function normalizeTopicLabel(topic?: string): string {
  const raw = String(topic || '').trim();
  if (!raw) return '';
  return TOPIC_LABEL_MAP[raw] || raw;
}

function isWeakTopic(topic: string): boolean {
  const normalized = normalizeTopicLabel(topic);
  if (!normalized) return true;
  if (['综合体验反馈', '未分类反馈'].includes(normalized)) return true;
  // Raw topic-model word bags often look like "game, good, play, ...".
  const commaCount = (normalized.match(/,/g) || []).length;
  return normalized.length > 50 || commaCount >= 3;
}

function extractTopic(text: string, sentiment: 'positive' | 'negative' | 'neutral'): string {
  if (!text) return sentiment === 'negative' ? '负向综合反馈' : '综合体验反馈';

  const scored = TOPIC_RULES
    .map(rule => ({
      label: rule.label,
      score: rule.keywords.reduce((acc, kw) => acc + (text.includes(kw.toLowerCase()) ? 1 : 0), 0),
    }))
    .filter(item => item.score > 0)
    .sort((a, b) => b.score - a.score);

  if (scored.length > 0) return scored[0].label;
  return sentiment === 'negative' ? '负向综合反馈' : sentiment === 'positive' ? '正向综合反馈' : '综合体验反馈';
}

function normalizePlayerType(value?: string): string {
  const raw = String(value || '').trim();
  if (!raw) return '';
  if (['New Player', '新手玩家'].includes(raw)) return '新手玩家';
  if (['Regular Player', '普通玩家'].includes(raw)) return '普通玩家';
  if (['Core Player', '核心玩家'].includes(raw)) return '核心玩家';
  return raw;
}

function classifyPlayer(playtime?: number): string {
  if (playtime === undefined) return '未知玩家';
  if (playtime < 10) return '新手玩家';
  if (playtime < 100) return '普通玩家';
  return '核心玩家';
}

function calculateValuePotential(playtime?: number, sentiment?: string): number {
  if (playtime === undefined) return 50;
  let score = Math.min(100, Math.floor(Math.sqrt(playtime) * 10));
  if (sentiment === 'positive') score = Math.min(100, score + 10);
  return score;
}

function calculateChurnRisk(playtime?: number, sentiment?: string): number {
  if (playtime === undefined) return 50;
  let risk = 50;
  if (playtime < 10) risk += 30;
  else if (playtime > 100) risk -= 20;

  if (sentiment === 'negative') risk += 30;
  if (sentiment === 'positive') risk -= 30;

  return Math.max(0, Math.min(100, risk));
}

function prioritizeCRM(churn_risk: number, value_potential: number): 'High' | 'Medium' | 'Low' {
  if (churn_risk > 70 && value_potential > 60) return 'High';
  if (value_potential > 80) return 'High';
  if (churn_risk < 30) return 'Low';
  return 'Medium';
}
