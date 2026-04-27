"""Product-grade Streamlit console for AI game strategy operations."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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

BRAND = {
    "bg": "#0B1020",
    "panel": "#111827",
    "panel2": "#172033",
    "text": "#E5E7EB",
    "muted": "#94A3B8",
    "blue": "#60A5FA",
    "green": "#34D399",
    "red": "#FB7185",
    "amber": "#FBBF24",
}


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        .stApp {{ background: linear-gradient(180deg, {BRAND['bg']} 0%, #0F172A 100%); color: {BRAND['text']}; }}
        section[data-testid="stSidebar"] {{ background: #0F172A; border-right: 1px solid rgba(148,163,184,.18); }}
        .hero {{ padding: 28px 30px; border-radius: 24px; background: radial-gradient(circle at top left, rgba(96,165,250,.28), rgba(17,24,39,.96) 45%); border: 1px solid rgba(148,163,184,.18); margin-bottom: 18px; }}
        .hero h1 {{ margin: 0; font-size: 34px; letter-spacing: -0.03em; }}
        .hero p {{ color: {BRAND['muted']}; font-size: 15px; max-width: 900px; }}
        .metric-card {{ background: rgba(17,24,39,.82); border: 1px solid rgba(148,163,184,.18); border-radius: 18px; padding: 18px; min-height: 120px; }}
        .metric-label {{ color: {BRAND['muted']}; font-size: 13px; }}
        .metric-value {{ color: white; font-size: 28px; font-weight: 700; margin-top: 8px; }}
        .metric-note {{ color: {BRAND['muted']}; font-size: 12px; margin-top: 8px; }}
        .action-card {{ background: rgba(15,23,42,.92); border: 1px solid rgba(96,165,250,.22); border-radius: 18px; padding: 18px; margin-bottom: 12px; }}
        .tag {{ display:inline-block; padding:4px 10px; border-radius:999px; background:rgba(96,165,250,.16); color:#BFDBFE; font-size:12px; margin-right:6px; }}
        .warning-box {{ padding: 14px 16px; border-radius: 16px; background: rgba(251,191,36,.12); border: 1px solid rgba(251,191,36,.35); }}
        .ok-box {{ padding: 14px 16px; border-radius: 16px; background: rgba(52,211,153,.10); border: 1px solid rgba(52,211,153,.28); }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def load_data(path_or_file) -> pd.DataFrame:
    if path_or_file is None:
        return pd.DataFrame()
    df = pd.read_csv(path_or_file)
    for col in ["timestamp_created", "created_at", "year_month", "date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def find_default_files() -> list[Path]:
    root = Path(__file__).resolve().parents[2]
    results = root / "data" / "results"
    if not results.exists():
        return []
    files = sorted(results.glob("*.csv"), key=lambda p: p.stat().st_size, reverse=True)
    return [p for p in files if "sentiment" in p.name or "topic" in p.name][:10]


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


def page_header() -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="tag">AI Strategy Operations</div><div class="tag">Evidence-first</div><div class="tag">Game Ops Console</div>
          <h1>GamePulse AI 运营策略控制台</h1>
          <p>面向游戏运营团队的玩家声音分析、生命周期代理洞察、智能触达策略与内容生产工作台。系统只输出当前数据能够支撑的结论；真实 LTV、付费转化与留存需要接入内部日志后才会启用。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_quality_gate(df: pd.DataFrame) -> None:
    q = evaluate_data_quality(df)
    st.subheader("Data Quality Gate · 数据可信度")
    cols = st.columns(4)
    with cols[0]:
        metric_card("样本量", f"{q.sample_size:,}", q.grade)
    with cols[1]:
        metric_card("时间跨度", "N/A" if q.date_span_days is None else f"{q.date_span_days} 天", "<14天不输出趋势")
    with cols[2]:
        metric_card("游戏/竞品数", str(q.games_count), "≥2 才启用竞品监控")
    with cols[3]:
        fields = sum([q.has_sentiment, q.has_topics, q.has_player_type, q.has_playtime])
        metric_card("关键信号完整度", f"{fields}/4", "情绪/主题/分群/时长")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='ok-box'><b>当前可支持模块</b><br>" + "<br>".join([f"✅ {x}" for x in q.supported_modules]) + "</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='warning-box'><b>限制与降级</b><br>" + "<br>".join([f"⚠️ {x}" for x in q.limitations]) + "</div>", unsafe_allow_html=True)


def render_overview(df: pd.DataFrame) -> None:
    s = executive_summary(df)
    st.subheader("Executive Overview · 运营总览")
    cols = st.columns(4)
    with cols[0]:
        metric_card("产品健康分", "N/A" if s["health_score"] is None else f"{s['health_score']}/100", "由公开口碑代理计算")
    with cols[1]:
        metric_card("正向口碑", "N/A" if s["positive_rate"] is None else f"{s['positive_rate']:.1%}", "sentiment / vote_up")
    with cols[2]:
        metric_card("负向风险", "N/A" if s["negative_rate"] is None else f"{s['negative_rate']:.1%}", "用于舆情风险判断")
    with cols[3]:
        metric_card("可用模块", str(len(s["supported_modules"])), "通过数据门槛后启用")

    actions = evidence_backed_actions(df)
    st.markdown("#### 今日运营动作建议")
    if not actions:
        st.info("当前数据不足以输出运营动作。请补采更多评论或上传已分析结果文件。")
    for a in actions:
        st.markdown(
            f"""
            <div class="action-card">
              <h4>{a['title']}</h4>
              <p><b>Evidence:</b> {a['evidence']}</p>
              <p><b>Action:</b> {a['action']}</p>
              <p style="color:{BRAND['muted']}"><b>Risk:</b> {a['risk']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sentiment_topic(df: pd.DataFrame) -> None:
    st.subheader("Voice of Player · 玩家声音洞察")
    c1, c2 = st.columns(2)
    with c1:
        if "sentiment" in df.columns:
            counts = df["sentiment"].value_counts()
            fig = px.pie(values=counts.values, names=counts.index, hole=.55, title="情绪结构")
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("缺少 sentiment 字段，情绪分析不可用。")
    with c2:
        if "topic_description" in df.columns:
            topics = df["topic_description"].value_counts().head(10).sort_values()
            fig = px.bar(x=topics.values, y=topics.index, orientation="h", title="Top 玩家主题/痛点")
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("缺少 topic_description 字段，主题洞察不可用。")

    time_col = "timestamp_created" if "timestamp_created" in df.columns else None
    if time_col and "sentiment" in df.columns:
        tmp = df.dropna(subset=[time_col]).copy()
        if len(tmp):
            tmp["month"] = tmp[time_col].dt.to_period("M").astype(str)
            trend = tmp.groupby(["month", "sentiment"]).size().reset_index(name="count")
            fig = px.line(trend, x="month", y="count", color="sentiment", markers=True, title="口碑趋势")
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)


def render_lifecycle(df: pd.DataFrame) -> None:
    st.subheader("Player Lifecycle Lab · 生命周期代理分析")
    q = evaluate_data_quality(df)
    if "玩家分群与生命周期代理分析" not in q.supported_modules:
        st.warning("当前数据不足以启用生命周期代理分析。需要 ≥1000 样本，并具备玩家分群与游玩时长字段。")
        return

    proxy = build_lifecycle_proxy(df)
    c1, c2 = st.columns(2)
    with c1:
        fig = px.histogram(proxy, x="value_potential_score", nbins=30, title="价值潜力代理分布")
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = px.histogram(proxy, x="churn_risk_proxy", color="crm_priority", nbins=30, title="流失风险代理与触达优先级")
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    st.caption("说明：这里是公开评论数据上的代理指标，不是真实 LTV/付费/留存。真实模型需要接入登录、充值、活动曝光和召回数据。")
    st.dataframe(proxy[[c for c in ["player_type", "sentiment", "playtime_hours_proxy", "value_potential_score", "churn_risk_proxy", "crm_priority", "review_text"] if c in proxy.columns]].head(200), use_container_width=True)


def render_crm_content(df: pd.DataFrame) -> None:
    st.subheader("CRM Strategy & AI Content Pipeline · 触达策略与内容生产")
    q = evaluate_data_quality(df)
    if q.sample_size < 300:
        st.warning("样本不足，不生成触达策略。")
        return

    segments = df["player_type"].value_counts().index.tolist() if "player_type" in df.columns else ["新手玩家", "普通玩家", "核心玩家"]
    for seg in segments[:4]:
        st.markdown(
            f"""
            <div class="action-card">
              <h4>{seg} · 触达策略卡</h4>
              <p><b>目标：</b>提升体验理解、降低负面扩散、促进社区参与。</p>
              <p><b>触达内容：</b>基于该分群最高频痛点生成 FAQ / 活动说明 / 版本亮点文案。</p>
              <p><b>AI文案草案：</b>“我们看到你最近关注的体验问题，团队已经整理了本周优化重点。完成指定任务可领取补给，并参与社区共创反馈。”</p>
              <p style="color:{BRAND['muted']}"><b>审核要求：</b>AI只生成草案，发布前必须由运营确认是否符合真实版本内容。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_competitor(df: pd.DataFrame) -> None:
    st.subheader("Competitor Monitor · 竞品监控")
    game_col = None
    for col in ["game_name", "game", "app_name", "appid", "app_id"]:
        if col in df.columns:
            game_col = col
            break
    if not game_col or df[game_col].nunique() < 2:
        st.warning("当前文件不足以做竞品监控：需要至少2款游戏/竞品数据。建议补采同品类游戏 Steam 评论，并保留 game_name 或 appid 字段。")
        st.markdown("可采集方向：同品类头部产品、网易相近品类产品、近期爆款产品、直接竞争产品。")
        return
    if "sentiment" in df.columns:
        comp = pd.crosstab(df[game_col], df["sentiment"], normalize="index").reset_index()
        fig = px.bar(comp, x=game_col, y=[c for c in comp.columns if c != game_col], barmode="stack", title="竞品口碑结构")
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("缺少 sentiment 字段，无法比较竞品口碑结构。")


def render_methodology() -> None:
    st.subheader("Methodology · 方法与边界")
    st.markdown(
        """
        - **可真实支持**：公开评论规模、情绪结构、主题痛点、口碑趋势、基于游玩时长的玩家分层代理。
        - **不可伪造**：真实 LTV、真实付费转化、真实留存/流失，需要公司内部日志、充值、活动曝光和触达回流数据。
        - **产品原则**：数据不足则降级或隐藏，不用 AI 生成没有证据的经营结论。
        - **接入内部数据后的升级**：用户级生命周期表 → LTV/转化/流失监督学习模型 → A/B触达实验 → 自动策略迭代。
        """
    )


def render_collection_panel() -> pd.DataFrame | None:
    if "active_df" not in st.session_state:
        st.session_state.active_df = None
    if "active_source" not in st.session_state:
        st.session_state.active_source = None

    st.sidebar.markdown("---")
    st.sidebar.subheader("Steam 真实数据采集")
    presets = {
        "DOTA 2": 570,
        "Elden Ring": 1245620,
        "Baldur's Gate 3": 1086940,
        "Cyberpunk 2077": 1091500,
        "自定义": 0,
    }
    preset = st.sidebar.selectbox("游戏", list(presets.keys()))
    app_id = presets[preset]
    game_name = preset
    if preset == "自定义":
        app_id = st.sidebar.number_input("Steam App ID", min_value=1, value=570, step=1)
        game_name = st.sidebar.text_input("游戏名称", value="Custom Steam Game")
    max_reviews = st.sidebar.slider("采集评论数", min_value=100, max_value=5000, value=1000, step=100)
    language = st.sidebar.selectbox("语言", ["all", "english", "schinese"], index=0)
    review_type = st.sidebar.selectbox("评论类型", ["all", "positive", "negative"], index=0)
    if st.sidebar.button("采集 Steam 评论并加载", type="primary"):
        with st.spinner(f"正在从 Steam 采集 {game_name} 评论..."):
            df_new = fetch_steam_reviews(
                app_id=int(app_id),
                game_name=game_name,
                max_reviews=int(max_reviews),
                language=language,
                review_type=review_type,
            )
            if df_new.empty:
                st.error("没有采集到有效评论。请检查 App ID、网络或 Steam 接口状态。")
                return None
            out = save_collected_reviews(df_new, game_name)
            st.session_state.active_df = df_new
            st.session_state.active_source = f"Steam采集：{game_name} · {out.name}"
            st.sidebar.success(f"采集完成：{len(df_new):,} 条，已保存 {out.name}")
            return df_new
    return st.session_state.active_df


def main() -> None:
    st.set_page_config(page_title="GamePulse AI Ops Console", page_icon="🎮", layout="wide", initial_sidebar_state="expanded")
    inject_css()
    page_header()

    st.sidebar.title("GamePulse Console")
    collected_df = render_collection_panel()
    default_files = find_default_files()
    file_choice = None
    if default_files:
        options = ["上传文件"] + [str(p) for p in default_files]
        selected = st.sidebar.selectbox("选择已有分析文件", options)
        if selected != "上传文件":
            file_choice = selected
    uploaded = st.sidebar.file_uploader("或上传 CSV", type=["csv"])

    if uploaded is not None:
        df = load_data(uploaded)
        st.session_state.active_df = df
        st.session_state.active_source = f"上传文件：{getattr(uploaded, 'name', 'uploaded.csv')}"
    elif file_choice:
        df = load_data(file_choice)
        st.session_state.active_df = df
        st.session_state.active_source = f"本地文件：{Path(file_choice).name}"
    elif collected_df is not None:
        df = collected_df
    else:
        st.info("请在侧边栏采集 Steam 评论、选择已有分析结果或上传 CSV。")
        st.stop()

    if st.sidebar.button("清空当前数据"):
        st.session_state.active_df = None
        st.session_state.active_source = None
        st.rerun()

    st.sidebar.success(f"已加载 {len(df):,} 条记录")
    if st.session_state.active_source:
        st.sidebar.caption(st.session_state.active_source)
    page = st.sidebar.radio(
        "产品模块",
        [
            "运营总览",
            "数据可信度",
            "生命周期代理",
            "玩家声音洞察",
            "触达与内容生产",
            "竞品监控",
            "方法与边界",
        ],
    )

    if page == "运营总览":
        render_overview(df)
        st.divider()
        render_quality_gate(df)
    elif page == "数据可信度":
        render_quality_gate(df)
    elif page == "生命周期代理":
        render_lifecycle(df)
    elif page == "玩家声音洞察":
        render_sentiment_topic(df)
    elif page == "触达与内容生产":
        render_crm_content(df)
    elif page == "竞品监控":
        render_competitor(df)
    else:
        render_methodology()


if __name__ == "__main__":
    main()
