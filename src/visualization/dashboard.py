"""GamePulse 运营洞察台 — rebuilt Streamlit product UI."""

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

# Warm, editorial operations palette. No tech blue.
INK = "#24211D"
MUTED = "#716B61"
PAPER = "#F7F1E7"
CARD = "#FFFDF8"
LINE = "#E4D8C7"
OLIVE = "#5F6F52"
MOSS = "#7C8A5D"
CLAY = "#B46A45"
OCHRE = "#C89232"
WINE = "#8E3B46"
SAND = "#EFE3D0"

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
    "home": "工作台",
    "quality": "数据质量",
    "voice": "玩家反馈",
    "segments": "玩家分层",
    "campaigns": "触达策略",
    "competitors": "竞品对比",
    "method": "说明",
}


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;700&family=Inter:wght@400;500;600;700;800&display=swap');

        :root {{
          --ink: {INK};
          --muted: {MUTED};
          --paper: {PAPER};
          --card: {CARD};
          --line: {LINE};
          --olive: {OLIVE};
          --clay: {CLAY};
          --ochre: {OCHRE};
          --wine: {WINE};
        }}

        html, body, [class*="css"] {{
          font-family: Inter, "Microsoft YaHei", sans-serif;
          color: var(--ink);
        }}
        .stApp {{
          background:
            radial-gradient(circle at 12% 8%, rgba(180,106,69,.10), transparent 26%),
            linear-gradient(180deg, #F8F0E3 0%, #F6EFE5 38%, #EFE3D0 100%);
          color: var(--ink);
        }}
        .block-container {{ max-width: 1440px; padding: 28px 42px 72px; }}
        section[data-testid="stSidebar"] {{
          background: #F4E8D7;
          border-right: 1px solid var(--line);
        }}
        section[data-testid="stSidebar"] * {{ color: var(--ink); }}
        div[data-testid="stSidebarUserContent"] {{ padding-top: 20px; }}

        h1, h2, h3 {{ color: var(--ink); letter-spacing: -.03em; }}
        .brand {{
          display: grid;
          grid-template-columns: 1fr auto;
          gap: 24px;
          align-items: end;
          border-bottom: 1px solid var(--line);
          padding-bottom: 22px;
          margin-bottom: 24px;
        }}
        .brand-kicker {{
          font-size: 12px;
          letter-spacing: .16em;
          text-transform: uppercase;
          color: var(--clay);
          font-weight: 800;
          margin-bottom: 8px;
        }}
        .brand-title {{
          font-family: "Noto Serif SC", serif;
          font-size: 48px;
          line-height: 1.05;
          font-weight: 700;
          margin: 0;
        }}
        .brand-copy {{
          max-width: 760px;
          color: var(--muted);
          font-size: 15px;
          line-height: 1.75;
          margin-top: 12px;
        }}
        .brand-meta {{
          background: #2C2924;
          color: #FFF8EC;
          border-radius: 22px;
          padding: 18px 20px;
          min-width: 260px;
          box-shadow: 0 18px 50px rgba(36,33,29,.14);
        }}
        .brand-meta b {{ color: #FFF8EC; }}
        .brand-meta div {{ color: rgba(255,248,236,.76); font-size: 13px; margin-top: 6px; }}

        .layout-grid {{
          display: grid;
          grid-template-columns: 280px 1fr;
          gap: 22px;
          align-items: start;
        }}
        .left-rail, .panel, .metric-card, .note-card {{
          background: rgba(255,253,248,.92);
          border: 1px solid var(--line);
          border-radius: 22px;
          box-shadow: 0 14px 36px rgba(68,55,42,.08);
        }}
        .left-rail {{ padding: 18px; position: sticky; top: 18px; }}
        .panel {{ padding: 24px; margin-bottom: 18px; }}
        .section-head {{ margin-bottom: 18px; }}
        .section-eyebrow {{
          color: var(--clay);
          text-transform: uppercase;
          letter-spacing: .12em;
          font-size: 11px;
          font-weight: 800;
          margin-bottom: 6px;
        }}
        .section-title {{
          font-family: "Noto Serif SC", serif;
          font-size: 28px;
          font-weight: 700;
          margin: 0;
        }}
        .section-copy {{
          color: var(--muted);
          line-height: 1.7;
          margin-top: 8px;
          max-width: 780px;
        }}
        .metric-row {{ display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; margin-bottom: 18px; }}
        .metric-card {{ padding: 18px; min-height: 126px; }}
        .metric-label {{ color: var(--muted); font-size: 12px; font-weight: 700; }}
        .metric-value {{ color: var(--ink); font-size: 30px; line-height: 1; font-weight: 800; margin-top: 12px; }}
        .metric-note {{ color: var(--muted); font-size: 12px; line-height: 1.55; margin-top: 10px; }}
        .note-card {{ padding: 18px; margin-bottom: 14px; }}
        .note-card h3 {{ margin: 0 0 10px; font-size: 18px; }}
        .note-card p {{ color: var(--muted); margin: 7px 0; line-height: 1.65; }}
        .label {{ display:inline-block; border-radius: 999px; padding: 5px 10px; font-size: 12px; font-weight: 700; margin: 0 6px 6px 0; }}
        .label.good {{ background:#E6E8D6; color:#43523D; }}
        .label.warn {{ background:#F4DFC9; color:#914F2F; }}
        .label.bad {{ background:#F2D7D8; color:#7C2E3A; }}
        .divider-title {{ color: var(--muted); font-size: 12px; font-weight: 800; letter-spacing: .10em; text-transform: uppercase; margin: 8px 0 12px; }}
        .source-line {{ font-size: 12px; color: var(--muted); line-height: 1.6; }}
        .stButton > button {{
          border: 1px solid #6E563F !important;
          background: #2C2924 !important;
          color: #FFF8EC !important;
          border-radius: 13px !important;
          font-weight: 800 !important;
        }}
        .stButton > button:hover {{ background: #443729 !important; border-color:#443729 !important; }}
        div[data-baseweb="select"] > div, input, textarea {{ background: #FFFDF8 !important; border-color: var(--line) !important; }}
        .stTabs [data-baseweb="tab-list"] {{ gap: 10px; border-bottom: 1px solid var(--line); }}
        .stTabs [data-baseweb="tab"] {{
          background: #FFFDF8;
          border: 1px solid var(--line);
          border-bottom: 0;
          border-radius: 14px 14px 0 0;
          padding: 10px 18px;
          color: var(--muted);
          font-weight: 700;
        }}
        .stTabs [aria-selected="true"] {{ background: #2C2924 !important; color: #FFF8EC !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    st.session_state.setdefault("datasets", [])
    st.session_state.setdefault("active_df", None)
    st.session_state.setdefault("active_source", None)
    st.session_state.setdefault("current_page", "home")


def plot_layout(fig):
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": INK, "family": "Inter, Microsoft YaHei"},
        margin={"l": 10, "r": 10, "t": 56, "b": 24},
        colorway=[OLIVE, CLAY, OCHRE, WINE, MOSS, "#9E7B57", "#6B5B4A"],
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
            needs_fallback = out["topic_description"].isin(["待归类主题", "泛体验反馈/未分类"])
            out.loc[needs_fallback, "topic_description"] = out.loc[needs_fallback, "review_text"].map(classify_review_topic)
            out.loc[needs_fallback, "topic_source"] = "review_keyword_fallback"
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
    st.session_state.active_source = f"{len(frames)} 个数据集，{len(st.session_state.active_df):,} 条记录"


def load_data(path_or_file) -> pd.DataFrame:
    return normalize_loaded_df(pd.read_csv(path_or_file))


def find_default_files() -> list[Path]:
    results = Path(__file__).resolve().parents[2] / "data" / "results"
    if not results.exists():
        return []
    return sorted(results.glob("*.csv"), key=lambda p: p.stat().st_size, reverse=True)[:12]


def metric_card(label: str, value: str, note: str = "") -> None:
    st.markdown(
        f"""
        <div class="metric-card">
          <div class="metric-label">{label}</div>
          <div class="metric-value">{value}</div>
          <div class="metric-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(kicker: str, title: str, copy: str = "") -> None:
    st.markdown(
        f"""
        <div class="section-head">
          <div class="section-eyebrow">{kicker}</div>
          <h2 class="section-title">{title}</h2>
          {f'<div class="section-copy">{copy}</div>' if copy else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def app_header(df: pd.DataFrame | None) -> None:
    loaded = df is not None and len(df) > 0
    game_count = df["game_name"].nunique() if loaded and "game_name" in df.columns else 0
    rows = len(df) if loaded else 0
    st.markdown(
        f"""
        <div class="brand">
          <div>
            <div class="brand-kicker">Game Operations Dashboard</div>
            <h1 class="brand-title">GamePulse 运营洞察台</h1>
            <div class="brand-copy">把 Steam 真实评论整理成运营团队能用的判断：玩家在抱怨什么、哪类玩家需要优先处理、触达应该怎么说、竞品最近有什么变化。</div>
          </div>
          <div class="brand-meta">
            <b>{'数据已加载' if loaded else '等待数据'}</b>
            <div>{rows:,} 条记录 · {game_count} 款游戏</div>
            <div>公开评论分析，不替代内部经营数据。</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    st.sidebar.markdown("### GamePulse")
    st.sidebar.caption("运营分析工作台")
    page = st.sidebar.radio("功能", list(PAGE_LABELS.keys()), format_func=lambda k: PAGE_LABELS[k], label_visibility="collapsed")
    st.session_state.current_page = page

    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 数据")
    source = st.sidebar.radio("来源", ["Steam 采集", "本地文件", "上传 CSV"], label_visibility="collapsed")
    append = st.sidebar.checkbox("追加到当前数据集", value=True, help="做竞品对比时保持开启，连续采集多款游戏。")

    if source == "Steam 采集":
        presets = {"DOTA 2": 570, "Elden Ring": 1245620, "Baldur's Gate 3": 1086940, "Cyberpunk 2077": 1091500, "自定义": 0}
        preset = st.sidebar.selectbox("游戏", list(presets.keys()))
        app_id = presets[preset]
        game_name = preset
        if preset == "自定义":
            app_id = st.sidebar.number_input("Steam App ID", min_value=1, value=570, step=1)
            game_name = st.sidebar.text_input("游戏名称", value="Custom Steam Game")
        max_reviews = st.sidebar.slider("评论数", 100, 5000, 1000, 100)
        language = st.sidebar.selectbox("语言", ["all", "english", "schinese"], index=0)
        review_type = st.sidebar.selectbox("评论类型", ["all", "positive", "negative"], index=0)
        if st.sidebar.button("采集数据", type="primary"):
            with st.spinner(f"正在采集 {game_name} 的 Steam 评论..."):
                df_new = fetch_steam_reviews(int(app_id), game_name, int(max_reviews), language, review_type)
                if df_new.empty:
                    st.sidebar.error("没有采集到有效评论。")
                else:
                    out = save_collected_reviews(df_new, game_name)
                    set_active(df_new, f"Steam：{game_name} · {out.name}", append=append)
                    st.sidebar.success(f"已采集 {len(df_new):,} 条")
    elif source == "本地文件":
        files = find_default_files()
        if files:
            selected = st.sidebar.selectbox("选择文件", [str(p) for p in files], format_func=lambda x: Path(x).name)
            if st.sidebar.button("加载文件", type="primary"):
                set_active(load_data(selected), f"本地：{Path(selected).name}", append=append)
        else:
            st.sidebar.info("没有找到本地 CSV。")
    else:
        uploaded = st.sidebar.file_uploader("上传 CSV", type=["csv"])
        if uploaded is not None and st.sidebar.button("加载上传文件", type="primary"):
            set_active(load_data(uploaded), f"上传：{uploaded.name}", append=append)

    if st.session_state.active_df is not None:
        st.sidebar.markdown("---")
        st.sidebar.success(st.session_state.active_source)
        sources = [x["source"].split(" · ")[0] for x in st.session_state.datasets]
        st.sidebar.caption(" / ".join(sources))
        if st.sidebar.button("清空数据"):
            st.session_state.datasets = []
            st.session_state.active_df = None
            st.session_state.active_source = None
            st.rerun()


def render_empty_state() -> None:
    section_header("Start", "先加载一份真实数据", "可以直接采集 Steam 评论，也可以加载项目里已有的 CSV。做竞品对比时，左侧“追加到当前数据集”保持开启，再采集第二款游戏。")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("<div class='note-card'><h3>1. 采集评论</h3><p>适合现场演示：选择游戏，采集 Steam 公开评论。</p></div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='note-card'><h3>2. 看数据质量</h3><p>先判断样本量、时间跨度、字段是否足够，避免过度解读。</p></div>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div class='note-card'><h3>3. 输出动作</h3><p>从玩家反馈、分层、触达和竞品对比里提炼运营建议。</p></div>", unsafe_allow_html=True)


def render_home(df: pd.DataFrame) -> None:
    summary = executive_summary(df)
    section_header("Overview", "今天先看这四件事", "总览只放负责人真正会关心的指标：口碑、风险、数据范围和是否能做竞品比较。")
    st.markdown("<div class='metric-row'>", unsafe_allow_html=True)
    cols = st.columns(4)
    with cols[0]: metric_card("健康分", "N/A" if summary["health_score"] is None else f"{summary['health_score']}/100", "基于公开评论，不等同收入表现")
    with cols[1]: metric_card("正向口碑", "N/A" if summary["positive_rate"] is None else f"{summary['positive_rate']:.1%}", "好评占比")
    with cols[2]: metric_card("负向风险", "N/A" if summary["negative_rate"] is None else f"{summary['negative_rate']:.1%}", "差评占比")
    with cols[3]: metric_card("覆盖游戏", str(df["game_name"].nunique()) if "game_name" in df.columns else "1", "两款以上才做竞品对比")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    section_header("Priority", "可执行建议", "这里不写空泛结论，只展示能追溯到数据的动作。")
    actions = evidence_backed_actions(df)
    if not actions:
        st.info("当前数据还不足以给出明确建议。先增加样本量或补充主题/分层字段。")
    for item in actions:
        st.markdown(
            f"<div class='note-card'><h3>{item['title']}</h3><p><b>依据：</b>{item['evidence']}</p><p><b>建议：</b>{item['action']}</p><p><b>注意：</b>{item['risk']}</p></div>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def render_quality(df: pd.DataFrame) -> None:
    q = evaluate_data_quality(df)
    section_header("Data Quality", "数据质量", "先判断数据能支撑什么，再决定展示哪些分析。")
    cols = st.columns(4)
    with cols[0]: metric_card("样本量", f"{q.sample_size:,}", q.grade)
    with cols[1]: metric_card("时间跨度", "N/A" if q.date_span_days is None else f"{q.date_span_days} 天", "不到 14 天不看趋势")
    with cols[2]: metric_card("游戏数量", str(q.games_count), "两款以上可做竞品对比")
    with cols[3]: metric_card("字段完整度", f"{sum([q.has_sentiment, q.has_topics, q.has_player_type, q.has_playtime])}/4", "口碑 / 主题 / 分层 / 时长")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='panel'><div class='divider-title'>可以看</div>" + "".join([f"<span class='label good'>{x}</span>" for x in q.supported_modules]) + "</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='panel'><div class='divider-title'>暂时不能看</div>" + "".join([f"<span class='label warn'>{x}</span>" for x in q.limitations]) + "</div>", unsafe_allow_html=True)


def render_voice(df: pd.DataFrame) -> None:
    section_header("Player Voice", "玩家反馈", "把评论拆成口碑结构和主要话题。没有主题模型时，先用关键词归类做快速预览。")
    c1, c2 = st.columns([1, 1.2])
    with c1:
        if "sentiment" in df.columns:
            counts = df["sentiment"].value_counts()
            fig = px.pie(values=counts.values, names=counts.index, hole=.58, title="好评 / 差评", color_discrete_sequence=[OLIVE, WINE, OCHRE])
            st.plotly_chart(plot_layout(fig), width="stretch")
        else:
            st.warning("缺少口碑字段。")
    with c2:
        if "topic_description" in df.columns:
            topics = df["topic_description"].value_counts().head(10).sort_values()
            fig = px.bar(x=topics.values, y=topics.index, orientation="h", title="玩家主要在说什么", color=topics.values, color_continuous_scale=["#EAD9BE", CLAY])
            fig.update_layout(showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(plot_layout(fig), width="stretch")
            if "topic_source" in df.columns:
                st.caption("部分主题来自关键词归类，正式对外前建议抽样复核。")
        else:
            st.warning("缺少评论文本，无法做主题预览。")


def render_segments(df: pd.DataFrame) -> None:
    section_header("Segments", "玩家分层", "用公开评论和游玩时长做粗分层。它能帮运营排优先级，但不是内部 LTV 模型。")
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
        topic_counts = part["topic_description"].value_counts()
        useful = topic_counts.drop(labels=["泛体验反馈/未分类", "待归类主题"], errors="ignore")
        topic = useful.idxmax() if len(useful) else topic_counts.idxmax()
    avg_play = part["playtime_forever"].mean() if "playtime_forever" in part.columns and len(part) else 0
    return {"n": len(part), "neg": neg, "topic": topic, "avg_play": avg_play}


def render_campaigns(df: pd.DataFrame) -> None:
    section_header("Campaign", "触达策略", "不同玩家说不同的话。这里给的是运营参考，不是直接发布稿。")
    segments = df["player_type"].dropna().astype(str).value_counts().index.tolist()[:4] if "player_type" in df.columns else ["新手玩家", "普通玩家", "核心玩家"]
    for seg in segments:
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
            <div class="note-card">
              <h3>{seg}</h3>
              <p><b>数据概况：</b>{stat['n']:,} 条评论；负向占比 {stat['neg']:.1%}；主要话题「{stat['topic']}」；平均时长 {stat['avg_play']:.1f}h</p>
              <p><b>目标：</b>{copy['goal']}</p>
              <p><b>触达内容：</b>{copy['content']}</p>
              <p><b>调性：</b>{copy['tone']}</p>
              <p><b>运营建议：</b>{action}</p>
              <p><b>参考文案：</b>“{sample}”</p>
              <p class="source-line">发布前请运营确认是否和当前版本内容一致。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_competitors(df: pd.DataFrame) -> None:
    section_header("Competitors", "竞品对比", "连续采集两款以上游戏，并保持左侧“追加到当前数据集”开启。")
    if "game_name" not in df.columns or df["game_name"].nunique() < 2:
        st.warning("目前只有一款游戏。请在左边再采集或加载另一款游戏。")
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


def render_method() -> None:
    section_header("Notes", "说明", "这页讲清楚产品边界，避免面试时被追问数据口径。")
    st.markdown(
        """
        <div class="panel">
          <p><b>能支持：</b>公开评论可以支持口碑结构、痛点排序、主题变化、时长分层和竞品口碑对比。</p>
          <p><b>不能伪造：</b>真实 LTV、付费转化、留存和流失需要公司内部日志、充值、活动曝光和触达回流数据。</p>
          <p><b>主题口径：</b>当前轻量主题来自关键词归类；正式版本可以接 LDA、BERTopic 或人工标注体系。</p>
          <p><b>产品原则：</b>数据不够的模块降级展示，不给没有依据的经营结论。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="GamePulse 运营洞察台", page_icon="🎮", layout="wide", initial_sidebar_state="expanded")
    init_state()
    inject_css()
    render_sidebar()

    df = normalize_loaded_df(st.session_state.active_df) if st.session_state.active_df is not None else None
    app_header(df)

    if df is None:
        render_empty_state()
        return

    page = st.session_state.current_page
    if page == "home":
        render_home(df)
    elif page == "quality":
        render_quality(df)
    elif page == "voice":
        render_voice(df)
    elif page == "segments":
        render_segments(df)
    elif page == "campaigns":
        render_campaigns(df)
    elif page == "competitors":
        render_competitors(df)
    elif page == "method":
        render_method()


if __name__ == "__main__":
    main()
