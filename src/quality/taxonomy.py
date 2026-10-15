"""Versioned lexical evidence filters. Matches are mentions, never verified defects."""

from __future__ import annotations

import re

TAXONOMY_VERSION = "quality-mentions-20261014-v2"
CATEGORIES = {
    "stability": "崩溃与稳定性",
    "performance": "性能与卡顿",
    "connectivity": "联机与连接",
    "usability": "操作与界面",
    "progression": "成长与引导",
    "balance": "平衡与机制",
}
RULES = {
    "stability": [
        r"\bcrash(?:es|ed|ing)?\b",
        r"\bfreez(?:e|es|ing)\b",
        r"\bsoftlock\b",
        r"\bcorrupt(?:ed|ion)?\b",
        "崩溃",
        "崩潰",
        "闪退",
        "閃退",
        "死机",
        "死機",
        "坏档",
        "壞檔",
        "вылет",
        "краш",
        "зависает",
    ],
    "performance": [
        r"\bfps\b",
        r"\bstutter(?:s|ing)?\b",
        r"\bperformance\b",
        r"\blag(?:gy|ging|s)?\b",
        "卡顿",
        "卡頓",
        "掉帧",
        "掉幀",
        "性能",
        "优化",
        "優化",
        "тормозит",
        "лаги",
    ],
    "connectivity": [
        r"\bdisconnect(?:s|ed|ing)?\b",
        r"\bmultiplayer\b",
        r"\bdesync\b",
        r"\bconnection\b",
        "联机",
        "聯機",
        "连接",
        "連線",
        "掉线",
        "掉線",
        "сервер",
        "соединение",
    ],
    "usability": [
        r"\bcontrols?\b",
        r"\binterface\b",
        r"\bkeybind(?:s|ing)?\b",
        r"\bui\b",
        r"\bkeyboard\b",
        "操作",
        "界面",
        "键位",
        "鍵位",
        "按键",
        "按鍵",
        "интерфейс",
        "управление",
    ],
    "progression": [
        r"\btutorial\b",
        r"\blearning curve\b",
        r"\bprogression\b",
        r"\bgrind(?:y|ing)?\b",
        "引导",
        "引導",
        "教程",
        "上手",
        "肝",
        "обучение",
    ],
    "balance": [
        r"\bbalanc(?:e|ed|ing)\b",
        r"\boverpowered\b",
        r"\bnerf(?:ed|s)?\b",
        r"\bdifficulty\b",
        "平衡",
        "难度",
        "難度",
        "削弱",
        "баланс",
        "сложность",
    ],
}
SUPPORTED_LANGUAGES = {"english", "schinese", "tchinese", "russian", "en", "zh-cn", "zh-tw", "ru"}
COMPILED = {k: [re.compile(p, re.IGNORECASE) for p in rules] for k, rules in RULES.items()}
# Issue forms repeat the same section headings and checklists in every issue ("### (Crash) logs",
# "- [x] I have searched..."). They describe the form, not the reported problem.
ISSUE_TEMPLATE = re.compile(
    r"^[ \t]{0,3}#{1,6}[ \t][^\n]*$"  # section headings
    r"|^[ \t]*[-*][ \t]+\[[ xX]\][^\n]*$"  # checklist lines
    r"|<!--.*?-->",  # hidden instructions
    re.MULTILINE | re.DOTALL,
)


def mask_issue_template(text: str) -> str:
    """Blank template boilerplate with spaces so cue offsets still point into the original text."""
    return ISSUE_TEMPLATE.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), text)


def find_mentions(text: str, language: str, source: str) -> list[dict]:
    if source == "steam" and language not in SUPPORTED_LANGUAGES:
        return []
    if source == "github_issues":
        text = mask_issue_template(text)
    matches = []
    for category, patterns in COMPILED.items():
        cues = []
        for pattern in patterns:
            for match in pattern.finditer(text):
                cue = {"text": match.group(), "start": match.start(), "end": match.end()}
                if cue not in cues:
                    cues.append(cue)
                if len(cues) >= 12:
                    break
            if len(cues) >= 12:
                break
        if cues:
            matches.append({"category": category, "cues": cues})
    return matches
