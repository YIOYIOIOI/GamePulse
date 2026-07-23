"""
语言归一与过滤模块

Steam 评论 API 自带 `language` 字段（评论者填写/客户端语言），但历史管线
没有使用它，导致主题模型在多语言混合语料上按"语言"而非"主题"聚类。
本模块把语言处理显式纳入管线：

1. `add_language_columns(df)`  -> 归一出 `lang_code`（ISO 风格分桶）
2. `filter_language(df, "en")` -> 建模前按语言分流
3. `verify_language_tags(df)`  -> 可选：用 langdetect 抽验 Steam 标签的可信度

设计原则：Steam 自带标签为主（零成本、覆盖 100%），langdetect 仅作抽验，
不作为主判据（短文本/表情文本上 langdetect 噪声大）。
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# Steam 语言标签 -> ISO 风格语言桶。
# 参考 https://partner.steamgames.com/doc/store/localization/languages
STEAM_LANGUAGE_BUCKETS: dict[str, str] = {
    "english": "en",
    "russian": "ru",
    "spanish": "es",
    "latam": "es",          # 拉美西语，与西语同桶（同一书写系统与词汇基础）
    "brazilian": "pt",
    "portuguese": "pt",
    "schinese": "zh",
    "tchinese": "zh",
    "turkish": "tr",
    "ukrainian": "uk",
    "german": "de",
    "polish": "pl",
    "french": "fr",
    "indonesian": "id",
    "thai": "th",
    "koreana": "ko",
    "japanese": "ja",
    "vietnamese": "vi",
    "italian": "it",
    "czech": "cs",
    "hungarian": "hu",
    "romanian": "ro",
    "bulgarian": "bg",
    "greek": "el",
    "finnish": "fi",
    "danish": "da",
    "dutch": "nl",
    "norwegian": "no",
    "swedish": "sv",
    "arabic": "ar",
}

OTHER_BUCKET = "other"


def normalize_steam_language(tag: object) -> str:
    """把 Steam 的 language 标签归一成语言桶代码；未知/缺失 -> 'other'。"""
    if not isinstance(tag, str) or not tag.strip():
        return OTHER_BUCKET
    return STEAM_LANGUAGE_BUCKETS.get(tag.strip().lower(), OTHER_BUCKET)


def add_language_columns(df: pd.DataFrame, language_column: str = "language") -> pd.DataFrame:
    """添加 `lang_code` 列（不修改原列）。缺 language 列时全部标 'other' 并告警。"""
    out = df.copy()
    if language_column not in out.columns:
        logger.warning("缺少 %s 列，lang_code 全部标记为 %s", language_column, OTHER_BUCKET)
        out["lang_code"] = OTHER_BUCKET
        return out
    out["lang_code"] = out[language_column].map(normalize_steam_language)
    return out


def filter_language(df: pd.DataFrame, lang_code: str = "en") -> pd.DataFrame:
    """按语言桶过滤；若尚无 lang_code 列则先归一。"""
    if "lang_code" not in df.columns:
        df = add_language_columns(df)
    kept = df[df["lang_code"] == lang_code].copy()
    logger.info("语言过滤 %s: %d -> %d 行", lang_code, len(df), len(kept))
    return kept


def language_distribution(df: pd.DataFrame) -> pd.Series:
    """语言桶分布（建模前应先看这个，决定分流策略）。"""
    if "lang_code" not in df.columns:
        df = add_language_columns(df)
    return df["lang_code"].value_counts()


def verify_language_tags(
    df: pd.DataFrame,
    text_column: str = "review_text_clean",
    sample_size: int = 300,
    random_state: int = 42,
) -> dict:
    """
    用 langdetect 抽验 Steam 语言标签的可信度（可选，需要安装 langdetect）。

    返回 {'sampled': n, 'agree_rate': float, 'note': str}。
    仅统计 langdetect 能给出结果、且文本长度 >= 20 的样本，短文本检测不可靠。
    """
    try:
        from langdetect import DetectorFactory, detect

        DetectorFactory.seed = random_state
    except ImportError:
        return {"sampled": 0, "agree_rate": None, "note": "langdetect 未安装，跳过抽验"}

    if "lang_code" not in df.columns:
        df = add_language_columns(df)

    candidates = df[df[text_column].astype(str).str.len() >= 20]
    sample = candidates.sample(min(sample_size, len(candidates)), random_state=random_state)

    checked = 0
    agreed = 0
    for _, row in sample.iterrows():
        try:
            detected = detect(str(row[text_column]))
        except Exception:  # langdetect 对 emoji/数字串会抛 LangDetectException
            continue
        checked += 1
        # zh-cn/zh-tw -> zh
        detected = detected.split("-")[0]
        if detected == row["lang_code"]:
            agreed += 1

    rate = round(agreed / checked, 4) if checked else None
    return {
        "sampled": checked,
        "agree_rate": rate,
        "note": "langdetect 抽验（>=20字符文本）；Steam 标签为主判据，本数字仅用于评估标签可信度",
    }
