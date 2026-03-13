"""
可视化 Dashboard
使用 Streamlit 构建交互式分析面板
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from pathlib import Path
import sys

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent.parent))


def load_data(data_path: str) -> pd.DataFrame:
    """加载数据"""
    try:
        df = pd.read_csv(data_path)
        # 确保时间列是 datetime 类型
        if 'timestamp_created' in df.columns:
            df['timestamp_created'] = pd.to_datetime(df['timestamp_created'])
        if 'year_month' in df.columns:
            df['year_month'] = pd.to_datetime(df['year_month'].astype(str))
        return df
    except Exception as e:
        st.error(f"数据加载失败: {e}")
        return pd.DataFrame()


def plot_sentiment_distribution(df: pd.DataFrame):
    """情绪分布饼图"""
    if 'sentiment' not in df.columns:
        st.warning("数据中没有情绪信息")
        return

    sentiment_counts = df['sentiment'].value_counts()

    fig = px.pie(
        values=sentiment_counts.values,
        names=sentiment_counts.index,
        title='玩家情绪分布',
        color=sentiment_counts.index,
        color_discrete_map={
            'positive': '#2ecc71',
            'negative': '#e74c3c',
            'neutral': '#95a5a6'
        }
    )

    fig.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig, use_container_width=True)


def plot_sentiment_trend(df: pd.DataFrame):
    """情绪趋势折线图"""
    if 'year_month' not in df.columns or 'sentiment' not in df.columns:
        st.warning("缺少必要的数据列")
        return

    # 按月统计情绪
    sentiment_by_month = df.groupby(['year_month', 'sentiment']).size().unstack(fill_value=0)

    fig = go.Figure()

    for sentiment in sentiment_by_month.columns:
        color = {'positive': '#2ecc71', 'negative': '#e74c3c', 'neutral': '#95a5a6'}.get(sentiment, '#3498db')
        fig.add_trace(go.Scatter(
            x=sentiment_by_month.index,
            y=sentiment_by_month[sentiment],
            name=sentiment.capitalize(),
            mode='lines+markers',
            line=dict(color=color, width=2),
            marker=dict(size=6)
        ))

    fig.update_layout(
        title='玩家情绪随时间变化趋势',
        xaxis_title='时间',
        yaxis_title='评论数量',
        hovermode='x unified'
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_player_type_distribution(df: pd.DataFrame):
    """玩家类型分布"""
    if 'player_type' not in df.columns:
        st.warning("数据中没有玩家类型信息")
        return

    player_counts = df['player_type'].value_counts()

    fig = px.bar(
        x=player_counts.index,
        y=player_counts.values,
        title='玩家类型分布',
        labels={'x': '玩家类型', 'y': '数量'},
        color=player_counts.index,
        text=player_counts.values
    )

    fig.update_traces(texttemplate='%{text}', textposition='outside')
    st.plotly_chart(fig, use_container_width=True)


def plot_player_sentiment_by_type(df: pd.DataFrame):
    """不同玩家类型的情绪对比"""
    if 'player_type' not in df.columns or 'sentiment' not in df.columns:
        st.warning("缺少必要的数据列")
        return

    # 统计每种玩家类型的情绪分布
    cross_tab = pd.crosstab(df['player_type'], df['sentiment'], normalize='index') * 100

    fig = px.bar(
        cross_tab,
        barmode='group',
        title='不同玩家类型的情绪分布对比',
        labels={'value': '百分比 (%)', 'player_type': '玩家类型'},
        color_discrete_map={
            'positive': '#2ecc71',
            'negative': '#e74c3c',
            'neutral': '#95a5a6'
        }
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_topic_distribution(df: pd.DataFrame):
    """主题分布"""
    if 'topic_description' not in df.columns:
        st.warning("数据中没有主题信息")
        return

    topic_counts = df['topic_description'].value_counts().head(10)

    fig = px.bar(
        x=topic_counts.values,
        y=topic_counts.index,
        orientation='h',
        title='玩家关注主题 TOP10',
        labels={'x': '评论数量', 'y': '主题'},
        text=topic_counts.values
    )

    fig.update_traces(texttemplate='%{text}', textposition='outside')
    fig.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig, use_container_width=True)


def plot_topic_sentiment_heatmap(df: pd.DataFrame):
    """主题-情绪热力图"""
    if 'topic_description' not in df.columns or 'sentiment' not in df.columns:
        st.warning("缺少必要的数据列")
        return

    # 选择 TOP10 主题
    top_topics = df['topic_description'].value_counts().head(10).index
    df_filtered = df[df['topic_description'].isin(top_topics)]

    # 创建交叉表
    cross_tab = pd.crosstab(df_filtered['topic_description'], df_filtered['sentiment'])

    fig = px.imshow(
        cross_tab,
        labels=dict(x="情绪", y="主题", color="评论数量"),
        title='主题-情绪热力图',
        color_continuous_scale='RdYlGn',
        aspect='auto'
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_review_length_distribution(df: pd.DataFrame):
    """评论长度分布"""
    if 'review_length' not in df.columns:
        st.warning("数据中没有评论长度信息")
        return

    fig = px.histogram(
        df,
        x='review_length',
        nbins=50,
        title='评论长度分布',
        labels={'review_length': '评论长度（字符）', 'count': '数量'},
        color_discrete_sequence=['#3498db']
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_playtime_vs_sentiment(df: pd.DataFrame):
    """游戏时长 vs 情绪"""
    if 'playtime_forever' not in df.columns or 'sentiment' not in df.columns:
        st.warning("缺少必要的数据列")
        return

    fig = px.box(
        df,
        x='sentiment',
        y='playtime_forever',
        title='不同情绪评论者的游戏时长对比',
        labels={'sentiment': '情绪', 'playtime_forever': '游戏时长（小时）'},
        color='sentiment',
        color_discrete_map={
            'positive': '#2ecc71',
            'negative': '#e74c3c',
            'neutral': '#95a5a6'
        }
    )

    st.plotly_chart(fig, use_container_width=True)


def display_summary_stats(df: pd.DataFrame):
    """显示摘要统计"""
    st.header("📊 数据概览")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("总评论数", f"{len(df):,}")

    with col2:
        if 'sentiment' in df.columns:
            positive_rate = (df['sentiment'] == 'positive').mean()
            st.metric("好评率", f"{positive_rate:.1%}")

    with col3:
        if 'playtime_forever' in df.columns:
            avg_playtime = df['playtime_forever'].mean()
            st.metric("平均游戏时长", f"{avg_playtime:.1f}h")

    with col4:
        if 'timestamp_created' in df.columns:
            try:
                df['timestamp_created'] = pd.to_datetime(df['timestamp_created'])
                date_range = (df['timestamp_created'].max() - df['timestamp_created'].min()).days
                st.metric("数据时间跨度", f"{date_range} 天")
            except:
                st.metric("数据时间跨度", "N/A")


def display_sentiment_summary(df: pd.DataFrame):
    """显示情绪摘要"""
    if 'sentiment' not in df.columns:
        return

    st.header("😊 情绪分析")

    col1, col2 = st.columns(2)

    with col1:
        plot_sentiment_distribution(df)

    with col2:
        st.subheader("详细统计")
        sentiment_stats = df['sentiment'].value_counts()
        sentiment_pct = df['sentiment'].value_counts(normalize=True)

        for sentiment in ['positive', 'negative', 'neutral']:
            if sentiment in sentiment_stats.index:
                count = sentiment_stats[sentiment]
                pct = sentiment_pct[sentiment]
                emoji = {'positive': '👍', 'negative': '👎', 'neutral': '😐'}.get(sentiment)
                st.markdown(f"**{emoji} {sentiment.capitalize()}**: {count:,} ({pct:.1%})")

    st.markdown("---")
    plot_sentiment_trend(df)


def display_player_analysis(df: pd.DataFrame):
    """显示玩家分析"""
    st.header("👥 玩家群体分析")

    col1, col2 = st.columns(2)

    with col1:
        plot_player_type_distribution(df)

    with col2:
        plot_player_sentiment_by_type(df)

    st.markdown("---")
    plot_playtime_vs_sentiment(df)


def display_topic_analysis(df: pd.DataFrame):
    """显示主题分析"""
    st.header("🔍 主题分析")

    col1, col2 = st.columns([1, 1])

    with col1:
        plot_topic_distribution(df)

    with col2:
        plot_topic_sentiment_heatmap(df)


def display_review_samples(df: pd.DataFrame):
    """显示评论样本"""
    st.header("📝 评论样本")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("最新好评")
        if 'sentiment' in df.columns and 'review_text' in df.columns:
            positive_reviews = df[df['sentiment'] == 'positive'].sort_values('timestamp_created', ascending=False)
            for _, review in positive_reviews.head(5).iterrows():
                st.success(review['review_text'][:200] + "...")

    with col2:
        st.subheader("最新差评")
        if 'sentiment' in df.columns and 'review_text' in df.columns:
            negative_reviews = df[df['sentiment'] == 'negative'].sort_values('timestamp_created', ascending=False)
            for _, review in negative_reviews.head(5).iterrows():
                st.error(review['review_text'][:200] + "...")


def main():
    """主函数"""
    st.set_page_config(
        page_title="游戏玩家反馈分析系统",
        page_icon="🎮",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("🎮 AI驱动的游戏玩家反馈分析系统")
    st.markdown("---")

    # 侧边栏
    st.sidebar.header("📁 数据加载")

    # 文件上传
    uploaded_file = st.sidebar.file_uploader("上传分析结果文件 (CSV)", type=['csv'])

    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)

        # 确保时间列是 datetime 类型
        if 'timestamp_created' in df.columns:
            df['timestamp_created'] = pd.to_datetime(df['timestamp_created'], errors='coerce')
        if 'year_month' in df.columns:
            df['year_month'] = pd.to_datetime(df['year_month'].astype(str), errors='coerce')

        st.sidebar.success(f"成功加载 {len(df)} 条评论")

        # 数据预览
        st.sidebar.markdown("---")
        st.sidebar.header("⚙️ 显示选项")

        show_overview = st.sidebar.checkbox("数据概览", value=True)
        show_sentiment = st.sidebar.checkbox("情绪分析", value=True)
        show_player = st.sidebar.checkbox("玩家分析", value=True)
        show_topic = st.sidebar.checkbox("主题分析", value=True)
        show_samples = st.sidebar.checkbox("评论样本", value=False)

        # 显示内容
        if show_overview:
            display_summary_stats(df)
            st.markdown("---")

        if show_sentiment:
            display_sentiment_summary(df)
            st.markdown("---")

        if show_player:
            display_player_analysis(df)
            st.markdown("---")

        if show_topic:
            display_topic_analysis(df)
            st.markdown("---")

        if show_samples:
            display_review_samples(df)

    else:
        st.info("👈 请在侧边栏上传数据文件开始分析")

        # 显示示例
        st.subheader("📖 使用说明")
        st.markdown("""
        1. 在侧边栏上传已分析的评论数据 CSV 文件
        2. 系统将自动生成可视化分析报告
        3. 可以在侧边栏选择要显示的分析模块

        **数据要求**：
        - 必须包含 `review_text` 列（评论内容）
        - 建议包含 `sentiment` 列（情绪标签）
        - 建议包含 `topic_description` 列（主题描述）
        - 建议包含 `player_type` 列（玩家类型）
        """)


if __name__ == '__main__':
    main()
