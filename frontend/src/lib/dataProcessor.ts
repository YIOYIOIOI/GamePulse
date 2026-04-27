import { Review } from './useDataStore';

export function standardizeData(rawData: any[], defaultGameName: string = 'Unknown Game'): Review[] {
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
      const s = row.sentiment.toLowerCase();
      if (s.includes('pos') || s === '1' || s === 'true') sentiment = 'positive';
      else if (s.includes('neg') || s === '0' || s === 'false') sentiment = 'negative';
    } else if (row.vote_up !== undefined) {
      sentiment = String(row.vote_up) === 'true' || String(row.vote_up) === '1' ? 'positive' : 'negative';
    }

    // 4. Topic extraction
    let topic_description = row.topic_description;
    let topic_source = 'Dataset';

    // Light keyword extraction if missing or looks like a bag of words (just checking if it's very long and lacks spaces or we want to override)
    if (!topic_description || topic_description.length > 50) {
      const text = String(row.review_text || row.text || '').toLowerCase();
      topic_description = extractTopic(text);
      topic_source = 'Keyword Categorization';
    }

    // 5. Playtime extraction
    let playtime_forever: number | undefined;
    if (row.playtime_forever !== undefined && !isNaN(Number(row.playtime_forever))) {
      playtime_forever = Number(row.playtime_forever);
    } else if (row.playtime !== undefined && !isNaN(Number(row.playtime))) {
      playtime_forever = Number(row.playtime);
    }

    // 6. Player Type and derived metrics
    let player_type = row.player_type || classifyPlayer(playtime_forever);

    // Simple proxies
    const value_potential_score = calculateValuePotential(playtime_forever, sentiment);
    const churn_risk_proxy = calculateChurnRisk(playtime_forever, sentiment);
    const crm_priority = prioritizeCRM(churn_risk_proxy, value_potential_score);

    return {
      review_text: String(row.review_text || row.text || ''),
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

// Light NLP topic extraction
const TOPIC_RULES = {
  'Matchmaking & Fairness': ['match', 'rank', 'mmr', 'teammate', 'balance', 'fair', 'smurf', 'cheat', 'hack'],
  'Performance & Stability': ['server', 'lag', 'fps', 'crash', 'bug', 'disconnect', 'performance', 'stutter'],
  'New Player Experience': ['tutorial', 'new player', 'learn', 'hard', 'beginner', 'confuser', 'confusing'],
  'Content & Updates': ['update', 'patch', 'hero', 'map', 'mode', 'content', 'event', 'meta'],
  'Monetization': ['pay', 'price', 'skin', 'battle pass', 'money', 'expensive', 'microtransaction', 'mtx', 'p2w'],
  'Community & Toxicity': ['toxic', 'community', 'friend', 'team', 'chat', 'report', 'grief'],
};

function extractTopic(text: string): string {
  if (!text) return 'Uncategorized';

  for (const [topic, keywords] of Object.entries(TOPIC_RULES)) {
    if (keywords.some(kw => text.includes(kw))) {
      return topic;
    }
  }
  return 'General Feedback';
}

function classifyPlayer(playtime?: number): string {
  if (playtime === undefined) return 'Unknown';
  if (playtime < 10) return 'New Player';
  if (playtime < 100) return 'Regular Player';
  return 'Core Player';
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
  // New players have high risk by default. Core have lower but highly responsive to negative sentiment.
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
