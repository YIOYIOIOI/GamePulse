import type { Comparison, FollowUpStatus, Monitor, Role } from "./types";

export const num = (value: number | null | undefined) =>
  value == null ? "—" : value.toLocaleString("zh-CN");

export const pct = (value: number | null | undefined, digits = 1) =>
  value == null ? "—" : (value * 100).toFixed(digits) + "%";

/** A difference of two rates, in percentage points: "+1.2". */
export const points = (value: number | null | undefined) =>
  value == null
    ? "—"
    : (value > 0 ? "+" : value < 0 ? "−" : "") +
      Math.abs(value * 100).toFixed(1);

export const pointsText = (value: number | null | undefined) =>
  value == null ? "—" : points(value) + " 个百分点";

const pad = (n: number) => String(n).padStart(2, "0");

/** Local calendar date, 2026-10-13. */
export function day(iso: string) {
  const d = new Date(iso);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Local date and time, 2026-10-13 18:08. */
export function dateTime(iso: string) {
  const d = new Date(iso);
  return `${day(iso)} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function relative(iso: string, now = Date.now()) {
  const minutes = Math.round((now - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.round(hours / 24);
  if (days < 31) return `${days} 天前`;
  return day(iso);
}

export const errorText = (e: unknown) =>
  e instanceof Error ? e.message : "请求失败，请重试";

export const LANGUAGES: Record<string, string> = {
  english: "英语",
  schinese: "简体中文",
  tchinese: "繁体中文",
  russian: "俄语",
  ukrainian: "乌克兰语",
  spanish: "西班牙语",
  latam: "拉美西班牙语",
  brazilian: "巴西葡萄牙语",
  portuguese: "葡萄牙语",
  german: "德语",
  french: "法语",
  italian: "意大利语",
  polish: "波兰语",
  czech: "捷克语",
  turkish: "土耳其语",
  japanese: "日语",
  koreana: "韩语",
  thai: "泰语",
  vietnamese: "越南语",
  hungarian: "匈牙利语",
  dutch: "荷兰语",
  swedish: "瑞典语",
  finnish: "芬兰语",
  danish: "丹麦语",
  norwegian: "挪威语",
  romanian: "罗马尼亚语",
  bulgarian: "保加利亚语",
  greek: "希腊语",
  indonesian: "印尼语",
  arabic: "阿拉伯语",
  unknown: "未标注",
};
export const language = (code: string) => LANGUAGES[code] || code;

export const PLAYTIME: Record<string, string> = {
  "0–2h": "2 小时以内",
  "2–20h": "2–20 小时",
  "20h+": "20 小时以上",
  unknown: "时长未知",
};
export const PLAYTIME_ORDER = ["0–2h", "2–20h", "20h+", "unknown"];

export const CATEGORIES: Record<string, string> = {
  stability: "崩溃与稳定性",
  performance: "性能与卡顿",
  connectivity: "联机与连接",
  usability: "操作与界面",
  progression: "成长与引导",
  balance: "平衡与机制",
};

export const STATUS: Record<FollowUpStatus, string> = {
  pending: "待处理",
  investigating: "调查中",
  confirmed: "已确认",
  closed: "已关闭",
};
export const STATUS_ORDER: FollowUpStatus[] = [
  "pending",
  "investigating",
  "confirmed",
  "closed",
];
/** Status changes the server accepts from each status. */
export const NEXT_STATUS: Record<FollowUpStatus, FollowUpStatus[]> = {
  pending: ["investigating", "closed"],
  investigating: ["confirmed", "closed", "pending"],
  confirmed: ["closed", "investigating"],
  closed: ["investigating"],
};

export const ROLES: Record<Role, { label: string; description: string }> = {
  owner: {
    label: "管理员",
    description: "全部权限，包括同步数据、管理成员和备份",
  },
  reviewer: {
    label: "复核人",
    description: "可以创建和更新跟进，并确认或关闭问题",
  },
  analyst: {
    label: "分析员",
    description: "可以创建跟进、更新调查进展、使用 AI 助手",
  },
  viewer: { label: "只读", description: "只能查看数据和跟进" },
};

export type Tone = "bad" | "good" | "neutral" | "muted";
export interface Verdict {
  label: string;
  tone: Tone;
  detail: string;
}

/** Plain-language reading of a before/after comparison of the not-recommended rate. */
export function verdict(c: Comparison): Verdict {
  if (c.status === "incomplete_window" || c.status === "incomplete_coverage")
    return {
      label: "数据不完整",
      tone: "muted",
      detail: "对比时间段超出了已采集的评论范围",
    };
  if (c.status === "insufficient_sample")
    return {
      label: "样本不足",
      tone: "muted",
      detail: `两段时间各需要至少 ${c.min_per_period} 条评论才做判断`,
    };
  if (c.ci_low != null && c.ci_low > 0)
    return {
      label: "明显变差",
      tone: "bad",
      detail: "不推荐率上升，且超出了正常波动范围",
    };
  if (c.ci_high != null && c.ci_high < 0)
    return {
      label: "明显好转",
      tone: "good",
      detail: "不推荐率下降，且超出了正常波动范围",
    };
  return {
    label: "无明显变化",
    tone: "neutral",
    detail: "差异在正常波动范围内",
  };
}

/** The 30-day monitor only raises an alert after its stricter robustness checks pass. */
export function monitorVerdict(m: Monitor): Verdict {
  const base = verdict(m);
  if (m.alert)
    return {
      ...base,
      label: "需要排查",
      detail: "不推荐率明显上升，按语言调整后仍然成立",
    };
  if (base.tone === "bad")
    return {
      label: "可能变差",
      tone: "bad",
      detail: "不推荐率上升，但按语言或按周检查后不够稳定",
    };
  return base;
}

const BBCODE =
  /\[\/?(?:h[1-6]|b|u|i|strike|spoiler|noparse|hr|list|olist|quote|code|table|tr|th|td|url(?:=[^\]]*)?|img)\]/gi;

/** Steam review text without BBCode markup. */
export function cleanReview(text: string) {
  return text
    .replace(/\[\*\]/g, "• ")
    .replace(BBCODE, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

const TEMPLATE_LINE =
  /^\s*(?:[-*]\s+\[[ xX]\].*|_no response_|none\.?|n\/a)\s*$/i;
const HEADING = /^\s{0,3}#{1,6}\s+(.*)$/;

export interface Block {
  kind: "heading" | "text" | "code";
  text: string;
}

/** Splits a GitHub issue body into readable blocks, dropping form boilerplate and images. */
export function issueBlocks(text: string): Block[] {
  const source = text
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/<img[^>]*>/gi, "")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\((?:https?:)?[^)\s]+\)/g, "$1");
  const blocks: Block[] = [];
  let code: string[] | null = null;
  let paragraph: string[] = [];
  const flush = () => {
    if (paragraph.join("").trim())
      blocks.push({ kind: "text", text: paragraph.join("\n").trim() });
    paragraph = [];
  };
  for (const line of source.split("\n")) {
    if (line.trim().startsWith("```")) {
      if (code) {
        if (code.join("").trim())
          blocks.push({ kind: "code", text: code.join("\n") });
        code = null;
      } else {
        flush();
        code = [];
      }
      continue;
    }
    if (code) {
      code.push(line);
      continue;
    }
    const heading = line.match(HEADING);
    if (heading) {
      flush();
      blocks.push({ kind: "heading", text: heading[1].trim() });
    } else if (TEMPLATE_LINE.test(line)) {
      continue;
    } else if (!line.trim()) {
      flush();
    } else {
      paragraph.push(line);
    }
  }
  if (code?.join("").trim())
    blocks.push({ kind: "code", text: code.join("\n") });
  flush();
  // A heading whose section was left empty carries no information.
  return blocks.filter(
    (b, i) =>
      b.kind !== "heading" ||
      (blocks[i + 1] && blocks[i + 1].kind !== "heading"),
  );
}

/** One-paragraph preview of an issue body: the reporter's own words only. */
export function issueExcerpt(text: string) {
  return issueBlocks(text)
    .filter((b) => b.kind === "text")
    .map((b) => b.text)
    .join(" · ")
    .replace(/\s+/g, " ")
    .trim();
}
