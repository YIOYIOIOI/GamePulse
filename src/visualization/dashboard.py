"""GamePulse 运营洞察台 — fully rebuilt no-sidebar product UI."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.analysis.product_metrics import (  # noqa: E402
    build_lifecycle_proxy,
    evaluate_data_quality,
    evidence_backed_actions,
    executive_summary,
)
from src.data_collection.steam_light_collector import (  # noqa: E402
    fetch_steam_reviews,
    save_collected_reviews,
)

INK = "#F2EDE4"
MUTED = "#B8AEA0"
PAPER = "#17130F"
CARD = "#211B16"
LINE = "#3C3229"
OLIVE = "#A7B985"
CLAY = "#D99066"
OCHRE = "#D5A24A"
WINE = "#D06E78"
COCOA = "#F3E9D8"
SAGE = "#2F3A28"
BLUSH = "#3C2428"

TOPIC_RULES = {
    "匹配与公平性": ["match", "rank", "mmr", "teammate", "balance", "fair", "smurf", "cheat", "hack"],
    "性能与稳定性": ["server", "lag", "fps", "crash", "bug", "disconnect", "stutter", "performance"],
    "新手体验": ["tutorial", "new player", "learn", "hard", "beginner", "complex", "confusing"],
    "内容与版本": ["update", "patch", "hero", "map", "mode", "content", "event", "meta"],
    "付费感知": ["pay", "price", "skin", "battle pass", "money", "expensive", "microtransaction"],
    "社区氛围": ["toxic", "community", "friend", "team", "chat", "report", "russian", "china"],
}

SEGMENT_COPY = {
    "新手玩家": {
        "goal": "降低第一次挫败，让用户尽快理解核心乐趣。",
        "content": "上手任务、失败原因解释、低门槛奖励、3分钟入门指南。",
        "tone": "清楚、耐心、少术语。",
    },
    "普通玩家": {
        "goal": "给出下一步目标，把零散活跃变成稳定参与。",
        "content": "阶段目标、限时活动、版本亮点、好友组队奖励。",
        "tone": "直接、明确、强调收益和进度。",
    },
    "核心玩家": {
        "goal": "保留高投入玩家的参与感，减少负面扩散。",
        "content": "版本解读、平衡性说明、高阶挑战、社区共创议题。",
        "tone": "尊重判断，给足背景和解释。",
    },
}

PAGE_LABELS = {
    "board": "决策看板",
    "quality": "数据体检",
    "voice": "玩家反馈",
    "segments": "玩家分层",
    "campaigns": "触达方案",
    "competitors": "竞品对比",
    "method": "口径说明",
}


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;700&family=Inter:wght@400;500;600;700;800&display=swap');
        html, body, [class*="css"] {{ font-family: Inter, "Microsoft YaHei", sans-serif; color: {INK}; }}
        .stApp {{
          background:
            linear-gradient(120deg, rgba(167,185,133,.10), transparent 34%),
            radial-gradient(circle at 92% 10%, rgba(217,144,102,.13), transparent 28%),
            linear-gradient(180deg, #0F0C09 0%, #17110D 48%, #1E1712 100%);
          color: {INK};
        }}
        header[data-testid="stHeader"] {{ display: none !important; }}
        div[data-testid="stToolbar"] {{ display: none !important; }}
        #MainMenu, footer {{ visibility: hidden !important; height: 0 !important; }}
        .block-container {{ max-width: 1500px; padding: 18px 44px 80px; }}
        section[data-testid="stSidebar"] {{ display: none !important; }}
        [data-testid="collapsedControl"] {{ display: none !important; }}
        h1, h2, h3 {{ color: {INK}; letter-spacing: -.03em; }}
        .topbar {{
          display:flex; justify-content:space-between; align-items:center;
          border-bottom:1px solid {LINE}; padding-bottom:18px; margin-bottom:22px;
        }}
        .brandmark {{ font-weight: 900; letter-spacing: -.04em; font-size: 22px; color:{COCOA}; }}
        .brandmark span {{ color:{CLAY}; }}
        .top-meta {{ color:{MUTED}; font-size:13px; }}
        .hero {{
          display:grid; grid-template-columns: 1.3fr .7fr; gap:20px; align-items:stretch; margin-bottom:20px;
        }}
        .hero-main {{
          background:#120F0C; color:#F8EFE1; border-radius:28px; padding:34px 38px;
          box-shadow:0 24px 70px rgba(0,0,0,.42); position:relative; overflow:hidden;
        }}
        .hero-main:after {{
          content:""; position:absolute; right:-90px; top:-90px; width:260px; height:260px; border-radius:999px;
          background:rgba(221,226,201,.18);
        }}
        .eyebrow {{ color:#D99066; text-transform:uppercase; letter-spacing:.14em; font-weight:900; font-size:12px; margin-bottom:10px; }}
        .hero-title {{ font-family:"Noto Serif SC", serif; font-size:48px; line-height:1.08; margin:0 0 14px; color:#F8EFE1; }}
        .hero-copy {{ color:rgba(248,239,225,.72); line-height:1.8; max-width:760px; font-size:15px; }}
        .hero-side {{
          background:{CARD}; border:1px solid {LINE}; border-radius:28px; padding:26px;
          box-shadow:0 18px 50px rgba(0,0,0,.32);
        }}
        .status-big {{ font-size:34px; font-weight:900; line-height:1; margin:12px 0; color:{COCOA}; }}
        .status-note {{ color:{MUTED}; line-height:1.7; font-size:13px; }}
        .command {{
          background:{CARD}; border:1px solid {LINE}; border-radius:24px; padding:18px; margin-bottom:20px;
          box-shadow:0 14px 42px rgba(0,0,0,.28);
        }}
        .command-title {{ font-weight:900; color:{COCOA}; margin-bottom:4px; }}
        .command-help {{ color:{MUTED}; font-size:13px; margin-bottom:10px; }}
        .nav-wrap {{
          background:rgba(33,27,22,.82); border:1px solid {LINE}; border-radius:22px;
          padding:10px 12px; margin:18px 0 22px; box-shadow:0 12px 34px rgba(0,0,0,.24);
        }}
        div[role="radiogroup"] {{ gap:8px; }}
        div[role="radiogroup"] label {{
          background:#211B16; border:1px solid {LINE}; border-radius:999px; padding:8px 14px;
          min-height:38px; color:{MUTED}; font-weight:800;
        }}
        div[role="radiogroup"] label:has(input:checked) {{ background:#120F0C; color:#F8EFE1; border-color:{COCOA}; }}
        .section {{ margin:12px 0 20px; }}
        .section-kicker {{ color:{CLAY}; text-transform:uppercase; letter-spacing:.13em; font-size:11px; font-weight:900; }}
        .section-title {{ font-family:"Noto Serif SC", serif; font-size:30px; margin:4px 0 6px; }}
        .section-copy {{ color:{MUTED}; line-height:1.7; max-width:840px; }}
        .metric-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin:16px 0 22px; }}
        .metric {{ background:{CARD}; border:1px solid {LINE}; border-radius:22px; padding:18px; box-shadow:0 14px 36px rgba(0,0,0,.26); }}
        .metric-label {{ color:{MUTED}; font-size:12px; font-weight:800; }}
        .metric-value {{ font-size:30px; font-weight:900; color:{COCOA}; margin-top:10px; }}
        .metric-note {{ color:{MUTED}; font-size:12px; line-height:1.55; margin-top:8px; }}
        .board-grid {{ display:grid; grid-template-columns:1.1fr .9fr; gap:18px; align-items:start; }}
        .card {{ background:{CARD}; border:1px solid {LINE}; border-radius:24px; padding:22px; box-shadow:0 14px 36px rgba(0,0,0,.26); margin-bottom:16px; }}
        .card h3 {{ margin:0 0 10px; font-size:20px; }}
        .card p {{ color:{MUTED}; line-height:1.7; margin:7px 0; }}
        .action-list {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }}
        .action-card {{ background:{CARD}; border:1px solid {LINE}; border-radius:22px; padding:18px; min-height:210px; box-shadow:0 14px 36px rgba(0,0,0,.26); }}
        .action-card h3 {{ font-size:18px; margin:0 0 10px; }}
        .action-card p {{ color:{MUTED}; font-size:13px; line-height:1.65; }}
        .tag {{ display:inline-block; padding:5px 10px; border-radius:999px; font-size:12px; font-weight:800; margin:0 6px 8px 0; }}
        .tag.good {{ background:{SAGE}; color:#B8C99B; }}
        .tag.warn {{ background:#3A2B18; color:#E8B76A; }}
        .tag.bad {{ background:{BLUSH}; color:#E18A92; }}
        .note {{ color:{MUTED}; font-size:12px; line-height:1.65; }}
        .stButton > button {{ background:#F3E9D8 !important; color:#17110D !important; border:1px solid #F3E9D8 !important; border-radius:14px !important; font-weight:900 !important; }}
        .stButton > button:hover {{ background:#D9CBB8 !important; border-color:#D9CBB8 !important; }}
        div[data-baseweb="select"] > div, input, textarea {{ background:{CARD} !important; border-color:{LINE} !important; }}
        .stFileUploader {{ background:{CARD}; border:1px dashed {LINE}; border-radius:18px; padding:10px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    st.session_state.setdefault("datasets", [])
    st.session_state.setdefault("active_df", None)
    st.session_state.setdefault("active_source", None)
    st.session_state.setdefault("page", "board")


def plot_layout(fig):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": INK, "family": "Inter, Microsoft YaHei"},
        margin={"l": 10, "r": 10, "t": 58, "b": 24},
        colorway=[OLIVE, CLAY, OCHRE, WINE, "#8A7758", "#A98C69"],
    )
    return fig


def humanize_topic(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "泛体验反馈/未分类"
    text_l = text.lower()
    for topic, keywords in TOPIC_RULES.items():
        if any(kw in text_l for kw in keywords):
            return topic
    if "," in text and len(text) < 120:
        return "待归类主题"
    return text


def classify_review_topic(text: object) -> str:
    text_l = str(text or "").lower()
    scores = {topic: sum(1 for kw in kws if kw in text_l) for topic, kws in TOPIC_RULES.items()}
    best, score = max(scores.items(), key=lambda x: x[1])
    return best if score else "泛体验反馈/未分类"


def infer_topics(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "topic_description" in out.columns:
        out["topic_description_raw"] = out["topic_description"]
        out["topic_description"] = out["topic_description"].map(humanize_topic)
        if "review_text" in out.columns:
            needs = out["topic_description"].isin(["待归类主题", "泛体验反馈/未分类"])
            out.loc[needs, "topic_description"] = out.loc[needs, "review_text"].map(classify_review_topic)
            out.loc[needs, "topic_source"] = "review_keyword_fallback"
        return out
    if "review_text" not in out.columns:
        return out
    out["topic_description"] = out["review_text"].map(classify_review_topic)
    out["topic_source"] = "keyword_preview"
    return out


def normalize_loaded_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["timestamp_created", "created_at", "year_month", "date"]:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce")
    if "game_name" not in out.columns:
        out["game_name"] = "Current Game"
    if "sentiment" not in out.columns and "vote_up" in out.columns:
        out["sentiment"] = out["vote_up"].astype(bool).map({True: "positive", False: "negative"})
    return infer_topics(out)


def set_active(df: pd.DataFrame, source: str, append: bool = False) -> None:
    df = normalize_loaded_df(df)
    if append and st.session_state.datasets:
        st.session_state.datasets.append({"source": source, "df": df})
    else:
        st.session_state.datasets = [{"source": source, "df": df}]
    frames = [item["df"] for item in st.session_state.datasets]
    st.session_state.active_df = pd.concat(frames, ignore_index=True, sort=False)
    st.session_state.active_source = f"{len(frames)} 个数据集 · {len(st.session_state.active_df):,} 条记录"


def load_data(path_or_file) -> pd.DataFrame:
    return normalize_loaded_df(pd.read_csv(path_or_file))


def find_default_files() -> list[Path]:
    results = Path(__file__).resolve().parents[2] / "data" / "results"
    if not results.exists():
        return []
    return sorted(results.glob("*.csv"), key=lambda p: p.stat().st_size, reverse=True)[:12]


def topbar() -> None:
    st.markdown(
        """
        <div class="topbar">
          <div class="brandmark">Game<span>Pulse</span></div>
          <div class="top-meta">真实评论 · 运营判断 · 竞品对比</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def hero(df: pd.DataFrame | None) -> None:
    loaded = df is not None and len(df) > 0
    rows = len(df) if loaded else 0
    games = df["game_name"].nunique() if loaded and "game_name" in df.columns else 0
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-main">
            <div class="eyebrow">Operations Brief</div>
            <h1 class="hero-title">把玩家反馈变成运营动作</h1>
            <div class="hero-copy">从 Steam 公开评论出发，整理玩家痛点、分层风险、触达建议和竞品变化。页面只展示数据能支撑的判断，不把公开评论包装成真实收入或留存模型。</div>
          </div>
          <div class="hero-side">
            <div class="eyebrow">Current Dataset</div>
            <div class="status-big">{rows:,}</div>
            <div class="status-note">条记录 · {games} 款游戏<br>{'数据已加载，可以进入分析。' if loaded else '还没有加载数据。先从下方选择采集、文件或上传。'}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def data_command() -> None:
    st.markdown("<div class='command'><div class='command-title'>数据入口</div><div class='command-help'>这里是唯一的数据操作区。采集、加载和上传都在这里完成，不再放左侧栏。</div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([1.1, 1, 1, .8])
    with c1:
        source = st.selectbox("来源", ["Steam 采集", "本地文件", "上传 CSV"])
    with c2:
        append = st.checkbox("追加到当前数据集", value=True, help="做竞品对比时保持开启。")
    if source == "Steam 采集":
        presets = {"DOTA 2": 570, "Elden Ring": 1245620, "Baldur's Gate 3": 1086940, "Cyberpunk 2077": 1091500, "自定义": 0}
        with c3:
            preset = st.selectbox("游戏", list(presets.keys()))
        app_id = presets[preset]
        game_name = preset
        if preset == "自定义":
            cc1, cc2 = st.columns(2)
            with cc1:
                app_id = st.number_input("Steam App ID", min_value=1, value=570, step=1)
            with cc2:
                game_name = st.text_input("游戏名称", value="Custom Steam Game")
        cc1, cc2, cc3, cc4 = st.columns([1, 1, 1, .8])
        with cc1:
            max_reviews = st.slider("评论数", 100, 5000, 1000, 100)
        with cc2:
            language = st.selectbox("语言", ["all", "english", "schinese"], index=0)
        with cc3:
            review_type = st.selectbox("评论类型", ["all", "positive", "negative"], index=0)
        with cc4:
            st.write("")
            if st.button("采集数据", type="primary"):
                with st.spinner(f"正在采集 {game_name} 的 Steam 评论..."):
                    df_new = fetch_steam_reviews(int(app_id), game_name, int(max_reviews), language, review_type)
                    if df_new.empty:
                        st.error("没有采集到有效评论。")
                    else:
                        out = save_collected_reviews(df_new, game_name)
                        set_active(df_new, f"Steam：{game_name} · {out.name}", append=append)
                        st.success(f"已采集 {len(df_new):,} 条评论")
    elif source == "本地文件":
        files = find_default_files()
        if files:
            cc1, cc2 = st.columns([3, .8])
            with cc1:
                selected = st.selectbox("选择文件", [str(p) for p in files], format_func=lambda x: Path(x).name)
            with cc2:
                st.write("")
                if st.button("加载文件", type="primary"):
                    set_active(load_data(selected), f"本地：{Path(selected).name}", append=append)
                    st.success("文件已加载")
        else:
            st.info("没有找到本地 CSV。")
    else:
        cc1, cc2 = st.columns([3, .8])
        with cc1:
            uploaded = st.file_uploader("上传 CSV", type=["csv"])
        with cc2:
            st.write("")
            if uploaded is not None and st.button("加载上传", type="primary"):
                set_active(load_data(uploaded), f"上传：{uploaded.name}", append=append)
                st.success("文件已加载")

    if st.session_state.active_df is not None:
        s1, s2 = st.columns([3, .8])
        with s1:
            sources = " / ".join([item["source"].split(" · ")[0] for item in st.session_state.datasets])
            st.caption(f"当前：{st.session_state.active_source}｜{sources}")
        with s2:
            if st.button("清空数据"):
                st.session_state.datasets = []
                st.session_state.active_df = None
                st.session_state.active_source = None
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def nav() -> str:
    st.markdown("<div class='nav-wrap'>", unsafe_allow_html=True)
    page = st.radio("页面", list(PAGE_LABELS.keys()), format_func=lambda k: PAGE_LABELS[k], horizontal=True, label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)
    st.session_state.page = page
    return page


def section(kicker: str, title: str, copy: str) -> None:
    st.markdown(
        f"""
        <div class="section">
          <div class="section-kicker">{kicker}</div>
          <div class="section-title">{title}</div>
          <div class="section-copy">{copy}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric(label: str, value: str, note: str) -> str:
    return f"<div class='metric'><div class='metric-label'>{label}</div><div class='metric-value'>{value}</div><div class='metric-note'>{note}</div></div>"


def metric_grid(cards: list[tuple[str, str, str]]) -> None:
    st.markdown("<div class='metric-grid'>" + "".join(metric(*c) for c in cards) + "</div>", unsafe_allow_html=True)


def empty_state() -> None:
    section("Start", "先加载数据", "这是一个运营分析产品，不是静态展示页。请先采集 Steam 评论，或加载项目里已有的 CSV。")
    st.markdown(
        """
        <div class="action-list">
          <div class="action-card"><h3>采集真实评论</h3><p>选择游戏和评论数量，从 Steam 公开接口拉取数据。</p></div>
          <div class="action-card"><h3>检查数据质量</h3><p>先看样本量、时间跨度和字段完整度，避免过度分析。</p></div>
          <div class="action-card"><h3>形成运营动作</h3><p>从反馈、分层、触达和竞品对比里提炼可以执行的建议。</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def board(df: pd.DataFrame) -> None:
    s = executive_summary(df)
    section("Board", "决策看板", "负责人先看这里：当前口碑、风险范围，以及能直接推进的动作。")
    metric_grid([
        ("健康分", "N/A" if s["health_score"] is None else f"{s['health_score']}/100", "基于公开评论"),
        ("正向口碑", "N/A" if s["positive_rate"] is None else f"{s['positive_rate']:.1%}", "好评占比"),
        ("负向风险", "N/A" if s["negative_rate"] is None else f"{s['negative_rate']:.1%}", "差评占比"),
        ("覆盖游戏", str(df["game_name"].nunique()) if "game_name" in df.columns else "1", "两款以上可做竞品对比"),
    ])
    actions = evidence_backed_actions(df)
    st.markdown("<div class='action-list'>", unsafe_allow_html=True)
    if not actions:
        st.info("当前数据还不足以给出明确建议。")
    for item in actions[:6]:
        st.markdown(
            f"<div class='action-card'><h3>{item['title']}</h3><p><b>依据：</b>{item['evidence']}</p><p><b>建议：</b>{item['action']}</p><p><b>注意：</b>{item['risk']}</p></div>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def quality(df: pd.DataFrame) -> None:
    q = evaluate_data_quality(df)
    section("Quality", "数据体检", "数据能支撑什么、不能支撑什么，先在这里说清楚。")
    metric_grid([
        ("样本量", f"{q.sample_size:,}", q.grade),
        ("时间跨度", "N/A" if q.date_span_days is None else f"{q.date_span_days} 天", "不到 14 天不看趋势"),
        ("游戏数量", str(q.games_count), "两款以上可做竞品对比"),
        ("字段完整度", f"{sum([q.has_sentiment, q.has_topics, q.has_player_type, q.has_playtime])}/4", "口碑 / 主题 / 分层 / 时长"),
    ])
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='card'><h3>可以看</h3>" + "".join([f"<span class='tag good'>{x}</span>" for x in q.supported_modules]) + "</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='card'><h3>暂时不能看</h3>" + "".join([f"<span class='tag warn'>{x}</span>" for x in q.limitations]) + "</div>", unsafe_allow_html=True)


def voice(df: pd.DataFrame) -> None:
    section("Voice", "玩家反馈", "把评论拆成口碑结构和主要话题。主题不够可靠时会明确标注。")
    c1, c2 = st.columns([.9, 1.1])
    with c1:
        if "sentiment" in df.columns:
            counts = df["sentiment"].value_counts()
            fig = px.pie(values=counts.values, names=counts.index, hole=.56, title="好评 / 差评", color_discrete_sequence=[OLIVE, WINE, OCHRE])
            st.plotly_chart(plot_layout(fig), width="stretch")
        else:
            st.warning("缺少口碑字段。")
    with c2:
        if "topic_description" in df.columns:
            topics = df["topic_description"].value_counts().head(10).sort_values()
            fig = px.bar(x=topics.values, y=topics.index, orientation="h", title="玩家主要在说什么", color=topics.values, color_continuous_scale=["#3C3229", CLAY])
            fig.update_layout(showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(plot_layout(fig), width="stretch")
            if "topic_source" in df.columns:
                st.caption("部分主题来自关键词归类，正式对外前建议抽样复核。")
        else:
            st.warning("缺少评论文本，无法做主题预览。")


def segments(df: pd.DataFrame) -> None:
    section("Segments", "玩家分层", "基于公开评论和游玩时长的粗分层，用来帮助运营排优先级。")
    if not {"playtime_forever", "sentiment"}.issubset(df.columns):
        st.warning("需要游玩时长和口碑字段才能做玩家分层。")
        return
    proxy = build_lifecycle_proxy(df)
    c1, c2 = st.columns(2)
    with c1:
        fig = px.histogram(proxy, x="value_potential_score", color="player_type" if "player_type" in proxy.columns else None, title="活跃价值分")
        st.plotly_chart(plot_layout(fig), width="stretch")
    with c2:
        fig = px.histogram(proxy, x="churn_risk_proxy", color="crm_priority", title="流失风险分")
        st.plotly_chart(plot_layout(fig), width="stretch")
    cols = [c for c in ["game_name", "player_type", "sentiment", "topic_description", "value_potential_score", "churn_risk_proxy", "crm_priority", "review_text"] if c in proxy.columns]
    st.dataframe(proxy[cols].head(200), width="stretch")


def segment_stats(df: pd.DataFrame, segment: str) -> dict:
    part = df[df["player_type"].astype(str) == str(segment)] if "player_type" in df.columns else df
    neg = (part["sentiment"] == "negative").mean() if "sentiment" in part.columns and len(part) else 0
    topic = "泛体验反馈"
    if "topic_description" in part.columns and len(part):
        counts = part["topic_description"].value_counts()
        useful = counts.drop(labels=["泛体验反馈/未分类", "待归类主题"], errors="ignore")
        topic = useful.idxmax() if len(useful) else counts.idxmax()
    avg_play = part["playtime_forever"].mean() if "playtime_forever" in part.columns and len(part) else 0
    return {"n": len(part), "neg": neg, "topic": topic, "avg_play": avg_play}


def campaigns(df: pd.DataFrame) -> None:
    section("Campaign", "触达方案", "不同玩家说不同的话。这里给运营参考，不是直接发布稿。")
    segs = df["player_type"].dropna().astype(str).value_counts().index.tolist()[:4] if "player_type" in df.columns else ["新手玩家", "普通玩家", "核心玩家"]
    st.markdown("<div class='action-list'>", unsafe_allow_html=True)
    for seg in segs:
        stat = segment_stats(df, seg)
        copy = SEGMENT_COPY.get(seg, SEGMENT_COPY["普通玩家"])
        if stat["neg"] >= .45:
            action = f"先解释和安抚「{stat['topic']}」相关问题，再同步修复节奏或补偿安排。"
            sample = f"我们看到最近关于「{stat['topic']}」的反馈比较集中，团队会优先同步处理进展。"
        elif stat["avg_play"] >= 100:
            action = f"把「{stat['topic']}」做成版本解读或社区讨论议题。"
            sample = f"你已经体验了很长时间，我们想邀请你一起讨论「{stat['topic']}」相关的版本调整。"
        else:
            action = f"围绕「{stat['topic']}」设计轻量任务，给玩家一个继续体验的理由。"
            sample = f"围绕「{stat['topic']}」，我们准备了一个轻量挑战，完成后可以解锁下一阶段奖励。"
        st.markdown(
            f"""
            <div class="action-card">
              <h3>{seg}</h3>
              <p><b>数据：</b>{stat['n']:,} 条；负向 {stat['neg']:.1%}；主要话题「{stat['topic']}」</p>
              <p><b>目标：</b>{copy['goal']}</p>
              <p><b>内容：</b>{copy['content']}</p>
              <p><b>建议：</b>{action}</p>
              <p><b>参考：</b>“{sample}”</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def competitors(df: pd.DataFrame) -> None:
    section("Competitors", "竞品对比", "连续采集两款以上游戏，并保持“追加到当前数据集”开启。")
    if "game_name" not in df.columns or df["game_name"].nunique() < 2:
        st.warning("目前只有一款游戏。请在数据入口再采集或加载另一款游戏。")
        return
    c1, c2 = st.columns(2)
    with c1:
        if "sentiment" in df.columns:
            comp = pd.crosstab(df["game_name"], df["sentiment"], normalize="index").reset_index()
            fig = px.bar(comp, x="game_name", y=[c for c in comp.columns if c != "game_name"], barmode="stack", title="口碑结构对比")
            st.plotly_chart(plot_layout(fig), width="stretch")
    with c2:
        if "topic_description" in df.columns:
            topic_game = df.groupby(["game_name", "topic_description"]).size().reset_index(name="count")
            top = topic_game.sort_values("count", ascending=False).groupby("game_name").head(3)
            fig = px.bar(top, x="count", y="topic_description", color="game_name", orientation="h", title="各游戏高频话题")
            st.plotly_chart(plot_layout(fig), width="stretch")
    table = df.groupby("game_name").agg(
        records=("review_text", "count"),
        positive_rate=("sentiment", lambda x: (x == "positive").mean() if len(x) else 0),
        top_topic=("topic_description", lambda x: x.value_counts().idxmax() if len(x) else ""),
    ).reset_index()
    st.dataframe(table, width="stretch")


def method() -> None:
    section("Method", "口径说明", "这里讲清楚产品边界，避免把公开评论分析说成内部经营模型。")
    st.markdown(
        """
        <div class="card">
          <p><b>能支持：</b>公开评论可以支持口碑结构、痛点排序、主题变化、时长分层和竞品口碑对比。</p>
          <p><b>不能伪造：</b>真实 LTV、付费转化、留存和流失需要公司内部日志、充值、活动曝光和触达回流数据。</p>
          <p><b>主题口径：</b>当前轻量主题来自关键词归类；正式版本可以接 LDA、BERTopic 或人工标注体系。</p>
          <p><b>产品原则：</b>数据不够的模块降级展示，不给没有依据的经营结论。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="GamePulse 运营洞察台", page_icon="🎮", layout="wide", initial_sidebar_state="collapsed")
    init_state()
    inject_css()
    topbar()
    df = normalize_loaded_df(st.session_state.active_df) if st.session_state.active_df is not None else None
    hero(df)
    data_command()
    page = nav()
    if df is None:
        empty_state()
        return
    if page == "board":
        board(df)
    elif page == "quality":
        quality(df)
    elif page == "voice":
        voice(df)
    elif page == "segments":
        segments(df)
    elif page == "campaigns":
        campaigns(df)
    elif page == "competitors":
        competitors(df)
    elif page == "method":
        method()


if __name__ == "__main__":
    main()
