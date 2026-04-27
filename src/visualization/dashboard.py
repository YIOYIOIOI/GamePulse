"""GamePulse 运营洞察台 — product UI."""

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

HERO_IMAGE = "https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=2200&q=80"
ACCENT = "#55F3D0"
BLUE = "#58A6FF"
PURPLE = "#A78BFA"
PINK = "#F472B6"
AMBER = "#FBBF24"
RED = "#FB7185"
PANEL = "rgba(8, 13, 30, .78)"
BORDER = "rgba(148, 163, 184, .22)"

TOPIC_RULES = {
    "匹配/排位/公平性": ["match", "rank", "mmr", "teammate", "balance", "fair", "smurf", "cheat", "hack"],
    "性能/服务器/稳定性": ["server", "lag", "fps", "crash", "bug", "disconnect", "stutter", "performance"],
    "新手体验/学习成本": ["tutorial", "new player", "learn", "hard", "beginner", "complex", "confusing"],
    "内容/版本/玩法": ["update", "patch", "hero", "map", "mode", "content", "event", "meta"],
    "商业化/付费感知": ["pay", "price", "skin", "battle pass", "money", "expensive", "microtransaction"],
    "社区/社交体验": ["toxic", "community", "friend", "team", "chat", "report", "russian", "china"],
}

SEGMENT_COPY = {
    "新手玩家": {
        "goal": "降低首日挫败感，帮助用户理解核心乐趣。",
        "content": "新手任务、低门槛奖励、3分钟上手指南、失败原因解释。",
        "tone": "陪伴式、解释型，避免硬卖活动。",
    },
    "普通玩家": {
        "goal": "提升中期目标感，把活跃转化为稳定参与。",
        "content": "阶段目标、限时活动、版本亮点、好友组队奖励。",
        "tone": "效率型、目标型，强调收益和进度。",
    },
    "核心玩家": {
        "goal": "维护高价值用户的认同感，降低负面扩散。",
        "content": "深度版本解读、平衡性说明、高阶挑战、社区共创征集。",
        "tone": "尊重专业判断，给出透明信息和参与感。",
    },
}


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        html, body, [class*="css"] {{ font-family: Inter, "Microsoft YaHei", sans-serif; }}
        .stApp {{
          background:
            radial-gradient(circle at 12% 0%, rgba(85,243,208,.16), transparent 28%),
            radial-gradient(circle at 80% 8%, rgba(167,139,250,.20), transparent 32%),
            linear-gradient(180deg, #050814 0%, #090D1C 45%, #0B1020 100%);
          color: #EAF2FF;
        }}
        section[data-testid="stSidebar"] {{
          background: rgba(5,8,20,.94);
          border-right: 1px solid {BORDER};
          backdrop-filter: blur(18px);
        }}
        .block-container {{ padding-top: 24px; max-width: 1480px; }}
        div[data-testid="stMetric"] {{ background: {PANEL}; border:1px solid {BORDER}; border-radius:18px; padding:16px; }}
        .hero {{
          min-height: 360px;
          border-radius: 34px;
          padding: 38px;
          position: relative;
          overflow: hidden;
          border: 1px solid rgba(255,255,255,.18);
          background:
            linear-gradient(100deg, rgba(3,7,18,.92) 0%, rgba(3,7,18,.72) 42%, rgba(3,7,18,.20) 100%),
            url('{HERO_IMAGE}') center/cover no-repeat;
          box-shadow: 0 30px 90px rgba(0,0,0,.38);
        }}
        .hero:after {{ content:""; position:absolute; inset:0; background:linear-gradient(180deg, transparent 45%, rgba(5,8,20,.72)); pointer-events:none; }}
        .hero-content {{ position: relative; z-index: 1; max-width: 780px; }}
        .eyebrow {{ color:{ACCENT}; font-weight:700; letter-spacing:.16em; font-size:12px; text-transform:uppercase; }}
        .hero h1 {{ font-size: 52px; line-height: .98; margin: 14px 0; letter-spacing: -.055em; }}
        .hero p {{ color:#C8D4E8; font-size:16px; line-height:1.75; max-width:720px; }}
        .pill {{ display:inline-flex; gap:8px; align-items:center; padding:7px 12px; border-radius:999px; background:rgba(85,243,208,.10); color:#CCFBF1; border:1px solid rgba(85,243,208,.28); font-size:12px; margin-right:8px; }}
        .glass {{ background:{PANEL}; border:1px solid {BORDER}; border-radius:24px; padding:22px; box-shadow: 0 16px 50px rgba(0,0,0,.22); }}
        .section-title {{ font-size:24px; font-weight:800; letter-spacing:-.03em; margin: 8px 0 4px; }}
        .section-subtitle {{ color:#94A3B8; margin-bottom:18px; }}
        .metric-card {{ background:{PANEL}; border:1px solid {BORDER}; border-radius:22px; padding:20px; min-height:128px; }}
        .metric-label {{ color:#94A3B8; font-size:13px; }}
        .metric-value {{ color:#FFFFFF; font-size:32px; font-weight:800; margin-top:8px; }}
        .metric-note {{ color:#8EA2C6; font-size:12px; margin-top:8px; }}
        .strategy-card {{ background:linear-gradient(145deg, rgba(15,23,42,.94), rgba(13,20,42,.76)); border:1px solid {BORDER}; border-radius:24px; padding:22px; margin-bottom:16px; }}
        .strategy-card h3 {{ margin:0 0 10px; font-size:20px; }}
        .card-grid {{ display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:16px; }}
        .warning {{ background:rgba(251,191,36,.10); border:1px solid rgba(251,191,36,.36); border-radius:18px; padding:16px; color:#FDE68A; }}
        .ok {{ background:rgba(85,243,208,.09); border:1px solid rgba(85,243,208,.28); border-radius:18px; padding:16px; color:#CCFBF1; }}
        .small {{ color:#94A3B8; font-size:12px; }}
        .stButton>button {{ border-radius: 14px; border:1px solid rgba(85,243,208,.38); background:linear-gradient(135deg,#0EA5E9,#14B8A6); color:white; font-weight:700; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    st.session_state.setdefault("datasets", [])
    st.session_state.setdefault("active_df", None)
    st.session_state.setdefault("active_source", None)


def humanize_topic(value: object) -> str:
    """Convert raw model word-bags into business-readable topic labels."""
    text = str(value or "").strip()
    if not text:
        return "泛体验反馈/未分类"
    text_l = text.lower()
    for topic, keywords in TOPIC_RULES.items():
        if any(kw in text_l for kw in keywords):
            return topic
    # Existing LDA outputs may look like comma-separated word bags. Do not expose
    # raw tokens such as "muy, si, moba" as product-facing labels.
    if "," in text and len(text) < 120:
        return "待归类主题"
    return text


def classify_review_topic(text: object) -> str:
    text_l = str(text or "").lower()
    scores = {topic: sum(1 for kw in kws if kw in text_l) for topic, kws in TOPIC_RULES.items()}
    best, score = max(scores.items(), key=lambda x: x[1])
    if score == 0:
        return "泛体验反馈/未分类"
    return best


def infer_topics(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "topic_description" in out.columns:
        out["topic_description_raw"] = out["topic_description"]
        out["topic_description"] = out["topic_description"].map(humanize_topic)
        if "review_text" in out.columns:
            needs_fallback = out["topic_description"].eq("待归类主题") | out["topic_description"].eq("泛体验反馈/未分类")
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
    out = infer_topics(out)
    return out


def set_active(df: pd.DataFrame, source: str, append: bool = False) -> None:
    df = normalize_loaded_df(df)
    if append:
        st.session_state.datasets.append({"source": source, "df": df})
        frames = [item["df"] for item in st.session_state.datasets]
        st.session_state.active_df = pd.concat(frames, ignore_index=True, sort=False)
        st.session_state.active_source = f"已合并 {len(frames)} 个数据集 · {len(st.session_state.active_df):,} 条"
    else:
        st.session_state.datasets = [{"source": source, "df": df}]
        st.session_state.active_df = df
        st.session_state.active_source = source


def load_data(path_or_file) -> pd.DataFrame:
    return normalize_loaded_df(pd.read_csv(path_or_file))


def find_default_files() -> list[Path]:
    root = Path(__file__).resolve().parents[2]
    results = root / "data" / "results"
    if not results.exists():
        return []
    files = sorted(results.glob("*.csv"), key=lambda p: p.stat().st_size, reverse=True)
    return files[:12]


def metric_card(label: str, value: str, note: str = "") -> None:
    st.markdown(
        f"<div class='metric-card'><div class='metric-label'>{label}</div><div class='metric-value'>{value}</div><div class='metric-note'>{note}</div></div>",
        unsafe_allow_html=True,
    )


def page_header() -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="hero-content">
            <div class="eyebrow">GAME OPERATIONS DASHBOARD</div>
            <h1>GamePulse<br/>游戏运营洞察平台</h1>
            <p>从 Steam 真实评论出发，帮运营团队快速看清：玩家在抱怨什么、该优先处理谁、怎么触达、竞品在发生什么变化。</p>
            <span class="pill">真实评论</span><span class="pill">可解释指标</span><span class="pill">运营动作</span><span class="pill">竞品对比</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_collection_panel() -> None:
    st.sidebar.subheader("数据")
    mode = st.sidebar.radio("来源", ["Steam 采集", "本地文件", "上传 CSV"], horizontal=False)
    append = st.sidebar.checkbox("追加到当前数据集（用于竞品对比）", value=True)

    if mode == "Steam 采集":
        presets = {"DOTA 2": 570, "Elden Ring": 1245620, "Baldur's Gate 3": 1086940, "Cyberpunk 2077": 1091500, "自定义": 0}
        preset = st.sidebar.selectbox("游戏", list(presets.keys()))
        app_id = presets[preset]
        game_name = preset
        if preset == "自定义":
            app_id = st.sidebar.number_input("Steam App ID", min_value=1, value=570, step=1)
            game_name = st.sidebar.text_input("游戏名称", value="Custom Steam Game")
        max_reviews = st.sidebar.slider("采集评论数", 100, 5000, 1000, 100)
        language = st.sidebar.selectbox("语言", ["all", "english", "schinese"], index=0)
        review_type = st.sidebar.selectbox("评论类型", ["all", "positive", "negative"], index=0)
        if st.sidebar.button("采集数据", type="primary"):
            with st.spinner(f"正在采集 {game_name} 的 Steam 评论..."):
                df_new = fetch_steam_reviews(int(app_id), game_name, int(max_reviews), language, review_type)
                if df_new.empty:
                    st.sidebar.error("未采集到有效评论。")
                else:
                    out = save_collected_reviews(df_new, game_name)
                    set_active(df_new, f"Steam 采集：{game_name} · {out.name}", append=append)
                    st.sidebar.success(f"已采集 {len(df_new):,} 条")

    elif mode == "本地文件":
        files = find_default_files()
        if files:
            selected = st.sidebar.selectbox("选择文件", [str(p) for p in files], format_func=lambda x: Path(x).name)
            if st.sidebar.button("加载本地文件", type="primary"):
                set_active(load_data(selected), f"本地文件：{Path(selected).name}", append=append)
        else:
            st.sidebar.info("暂无本地 CSV。")
    else:
        uploaded = st.sidebar.file_uploader("上传 CSV", type=["csv"])
        if uploaded is not None and st.sidebar.button("加载上传文件", type="primary"):
            set_active(load_data(uploaded), f"上传文件：{uploaded.name}", append=append)

    if st.session_state.active_df is not None:
        st.sidebar.success(f"当前 {len(st.session_state.active_df):,} 条记录")
        st.sidebar.caption(st.session_state.active_source)
        if st.session_state.datasets:
            st.sidebar.caption("数据集：" + " / ".join([x["source"].split(" · ")[0] for x in st.session_state.datasets]))
    if st.sidebar.button("清空数据"):
        st.session_state.datasets = []
        st.session_state.active_df = None
        st.session_state.active_source = None
        st.rerun()


def render_overview(df: pd.DataFrame) -> None:
    s = executive_summary(df)
    st.markdown("<div class='section-title'>总览</div><div class='section-subtitle'>当前产品口碑和需要关注的风险点。</div>", unsafe_allow_html=True)
    cols = st.columns(4)
    with cols[0]: metric_card("健康分", "N/A" if s["health_score"] is None else f"{s['health_score']}/100", "基于公开评论")
    with cols[1]: metric_card("正向口碑", "N/A" if s["positive_rate"] is None else f"{s['positive_rate']:.1%}", "好评 / 差评")
    with cols[2]: metric_card("负向风险", "N/A" if s["negative_rate"] is None else f"{s['negative_rate']:.1%}", "关注负向趋势")
    with cols[3]: metric_card("游戏数", str(df["game_name"].nunique()) if "game_name" in df.columns else "1", "两款以上可做对比")

    st.markdown("<br>", unsafe_allow_html=True)
    for a in evidence_backed_actions(df):
        st.markdown(f"<div class='strategy-card'><h3>{a['title']}</h3><p><b>依据</b> · {a['evidence']}</p><p><b>建议</b> · {a['action']}</p><p class='small'><b>注意</b> · {a['risk']}</p></div>", unsafe_allow_html=True)


def render_quality_gate(df: pd.DataFrame) -> None:
    q = evaluate_data_quality(df)
    st.markdown("<div class='section-title'>数据质量</div><div class='section-subtitle'>数据够不够用、能支撑哪些分析。</div>", unsafe_allow_html=True)
    cols = st.columns(4)
    with cols[0]: metric_card("样本量", f"{q.sample_size:,}", q.grade)
    with cols[1]: metric_card("时间跨度", "N/A" if q.date_span_days is None else f"{q.date_span_days} 天", "不到14天看不出趋势")
    with cols[2]: metric_card("竞品数量", str(q.games_count), "两款以上才有对比意义")
    with cols[3]: metric_card("信号完整度", f"{sum([q.has_sentiment, q.has_topics, q.has_player_type, q.has_playtime])}/4", "口碑 / 主题 / 玩家分层 / 时长")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='ok'><b>可以看</b><br>" + "<br>".join([f"✅ {x}" for x in q.supported_modules]) + "</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='warning'><b>暂时不能看</b><br>" + "<br>".join([f"⚠️ {x}" for x in q.limitations]) + "</div>", unsafe_allow_html=True)


def render_voice(df: pd.DataFrame) -> None:
    st.markdown("<div class='section-title'>玩家反馈</div><div class='section-subtitle'>没有跑过主题模型的数据，会先用关键词做快速归类，标注清楚来源。</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if "sentiment" in df.columns:
            counts = df["sentiment"].value_counts()
            fig = px.pie(values=counts.values, names=counts.index, hole=.62, title="好评 vs 差评", color_discrete_sequence=[ACCENT, RED, AMBER])
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, width="stretch")
    with c2:
        if "topic_description" in df.columns:
            topics = df["topic_description"].value_counts().head(10).sort_values()
            fig = px.bar(x=topics.values, y=topics.index, orientation="h", title="玩家在说什么", color=topics.values, color_continuous_scale=[BLUE, ACCENT])
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
            st.plotly_chart(fig, width="stretch")
            if "topic_source" in df.columns:
                st.caption("这些主题是关键词归类的结果，正式对外前建议抽样复核。")


def render_lifecycle(df: pd.DataFrame) -> None:
    st.markdown("<div class='section-title'>玩家分层</div><div class='section-subtitle'>这里展示的是基于公开评论和游玩时长的风险判断，不等同于公司内部的真实 LTV 或留存模型。</div>", unsafe_allow_html=True)
    if not {"playtime_forever", "sentiment"}.issubset(df.columns):
        st.warning("需要游玩时长和口碑数据才能做这个分析。")
        return
    proxy = build_lifecycle_proxy(df)
    c1, c2 = st.columns(2)
    with c1:
        fig = px.histogram(proxy, x="value_potential_score", color="player_type" if "player_type" in proxy.columns else None, title="活跃价值分")
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")
    with c2:
        fig = px.histogram(proxy, x="churn_risk_proxy", color="crm_priority", title="流失风险分")
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")
    st.dataframe(proxy[[c for c in ["game_name", "player_type", "sentiment", "topic_description", "value_potential_score", "churn_risk_proxy", "crm_priority", "review_text"] if c in proxy.columns]].head(200), width="stretch")


def segment_stats(df: pd.DataFrame, segment: str) -> dict:
    part = df[df["player_type"].astype(str) == str(segment)] if "player_type" in df.columns else df
    neg = (part["sentiment"] == "negative").mean() if "sentiment" in part.columns and len(part) else 0
    topic = "泛体验反馈"
    if "topic_description" in part.columns and len(part):
        topic_counts = part["topic_description"].value_counts()
        useful_topics = topic_counts.drop(labels=["泛体验反馈/未分类", "待归类主题"], errors="ignore")
        topic = useful_topics.idxmax() if len(useful_topics) else topic_counts.idxmax()
    avg_play = part["playtime_forever"].mean() if "playtime_forever" in part.columns and len(part) else 0
    return {"n": len(part), "neg": neg, "topic": topic, "avg_play": avg_play}


def render_crm_content(df: pd.DataFrame) -> None:
    st.markdown("<div class='section-title'>触达策略</div><div class='section-subtitle'>不同类型的玩家，用不同的方式说话。</div>", unsafe_allow_html=True)
    if "player_type" in df.columns:
        segments = df["player_type"].dropna().astype(str).value_counts().index.tolist()[:4]
    else:
        segments = ["新手玩家", "普通玩家", "核心玩家"]
    for seg in segments:
        stat = segment_stats(df, seg)
        copy = SEGMENT_COPY.get(seg, SEGMENT_COPY.get("普通玩家"))
        if stat["neg"] >= .45:
            action = f"围绕「{stat['topic']}」先做解释和安抚，再给补偿/修复预期。"
            sample = f"我们注意到你在「{stat['topic']}」上的体验受挫，本周会优先同步处理进展，并邀请你参与反馈共创。"
        elif stat["avg_play"] >= 100:
            action = f"把「{stat['topic']}」包装成深度版本解读和核心玩家讨论议题。"
            sample = f"你已经是深度玩家，我们准备了一份关于「{stat['topic']}」的版本观察，欢迎参与高阶讨论。"
        else:
            action = f"用「{stat['topic']}」做低门槛任务/活动引导，提高继续体验动机。"
            sample = f"围绕你可能关注的「{stat['topic']}」，我们准备了一个轻量活动，完成即可解锁奖励和下一步目标。"
        st.markdown(
            f"""
            <div class="strategy-card">
              <h3>{seg} · 触达策略卡</h3>
              <p><b>数据概况：</b>{stat['n']:,} 条；负向占比 {stat['neg']:.1%}；主主题「{stat['topic']}」；平均时长 {stat['avg_play']:.1f}h</p>
              <p><b>目标：</b>{copy['goal']}</p>
              <p><b>触达内容：</b>{copy['content']}</p>
              <p><b>调性：</b>{copy['tone']}</p>
              <p><b>运营建议：</b>{action}</p>
              <p><b>参考文案：</b>“{sample}”</p>
              <p class="small">发布前请运营确认内容是否和当前版本一致。关键词归类的主题建议抽查。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_competitor(df: pd.DataFrame) -> None:
    st.markdown("<div class='section-title'>竞品对比</div><div class='section-subtitle'>连续采集两款以上游戏，开启“追加”就能做对比。</div>", unsafe_allow_html=True)
    if "game_name" not in df.columns or df["game_name"].nunique() < 2:
        st.warning("目前只有一款游戏。在左边再采集一款，“追加”开着就行。")
        return
    c1, c2 = st.columns(2)
    with c1:
        if "sentiment" in df.columns:
            comp = pd.crosstab(df["game_name"], df["sentiment"], normalize="index").reset_index()
            fig = px.bar(comp, x="game_name", y=[c for c in comp.columns if c != "game_name"], barmode="stack", title="各游戏口碑对比")
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, width="stretch")
    with c2:
        topic_game = df.groupby(["game_name", "topic_description"]).size().reset_index(name="count") if "topic_description" in df.columns else pd.DataFrame()
        if not topic_game.empty:
            top = topic_game.sort_values("count", ascending=False).groupby("game_name").head(3)
            fig = px.bar(top, x="count", y="topic_description", color="game_name", orientation="h", title="各游戏玩家关注点")
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, width="stretch")
    st.dataframe(df.groupby("game_name").agg(records=("review_text", "count"), positive_rate=("sentiment", lambda x: (x == "positive").mean() if len(x) else 0), top_topic=("topic_description", lambda x: x.value_counts().idxmax() if len(x) else "")).reset_index(), width="stretch")


def render_methodology() -> None:
    st.markdown("<div class='section-title'>说明</div>", unsafe_allow_html=True)
    st.markdown("""
- 公开评论能做的事：口碑分布、痛点排序、主题变化、时长分层、竞品对比。
- 做不到的事：真实 LTV、付费转化、留存和流失——这些需要公司内部数据。
- 当前主题是关键词归类，升级路径是 LDA / BERTopic / 人工标注。
- 数据不够的模块会降级，不编没依据的结论。
""")


def main() -> None:
    st.set_page_config(page_title="GamePulse 运营洞察台", page_icon="🎮", layout="wide", initial_sidebar_state="expanded")
    init_state()
    inject_css()
    page_header()
    render_collection_panel()

    if st.session_state.active_df is None:
        st.info("在左边选一个入口开始。要做竞品对比的话，连续采集两款以上游戏就行。")
        return

    df = normalize_loaded_df(st.session_state.active_df)
    page = st.sidebar.radio("功能", ["总览", "数据质量", "玩家分层", "玩家反馈", "触达策略", "竞品对比", "说明"])

    if page == "总览":
        render_overview(df)
        st.divider()
        render_quality_gate(df)
    elif page == "数据质量":
        render_quality_gate(df)
    elif page == "玩家分层":
        render_lifecycle(df)
    elif page == "玩家反馈":
        render_voice(df)
    elif page == "触达策略":
        render_crm_content(df)
    elif page == "竞品对比":
        render_competitor(df)
    else:
        render_methodology()


if __name__ == "__main__":
    main()
