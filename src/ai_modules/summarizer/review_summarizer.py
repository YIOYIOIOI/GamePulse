"""
AI 评论总结模块
使用大语言模型自动总结玩家反馈
"""

import pandas as pd
import logging
from typing import List, Dict, Optional
from pathlib import Path
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

logger = logging.getLogger(__name__)


class ReviewSummarizer:
    """评论总结器"""

    def __init__(self, config: dict):
        self.config = config
        self.provider = config.get('llm', {}).get('provider', 'openai')

        # 初始化 LLM 客户端
        self._init_llm_client()

    def _init_llm_client(self):
        """初始化 LLM 客户端"""
        if self.provider == 'openai':
            try:
                import openai
            except ImportError:
                logger.warning("未安装 openai 库，请运行: pip install openai")
                self.client = None
                return

            api_key = os.getenv('OPENAI_API_KEY') or self.config.get('llm', {}).get('openai', {}).get('api_key')
            if not api_key:
                logger.warning("未设置 OpenAI API Key")
                self.client = None
            else:
                self.client = openai.OpenAI(api_key=api_key)
                self.model = self.config.get('llm', {}).get('openai', {}).get('model', 'gpt-4')

        elif self.provider == 'anthropic':
            try:
                import anthropic
            except ImportError:
                logger.warning("未安装 anthropic 库，请运行: pip install anthropic")
                self.client = None
                return

            api_key = os.getenv('ANTHROPIC_API_KEY') or self.config.get('llm', {}).get('anthropic', {}).get('api_key')
            if not api_key:
                logger.warning("未设置 Anthropic API Key")
                self.client = None
            else:
                self.client = anthropic.Anthropic(api_key=api_key)
                self.model = self.config.get('llm', {}).get('anthropic', {}).get('model', 'claude-3-opus-20240229')

    def summarize_reviews(self,
                         reviews: List[str],
                         sentiment: str = 'all',
                         max_reviews: int = 2000) -> str:
        """
        总结评论内容

        Args:
            reviews: 评论列表
            sentiment: 情绪类型 (all/positive/negative)
            max_reviews: 最大处理评论数

        Returns:
            总结文本
        """
        if not self.client:
            logger.error("LLM 客户端未初始化")
            return "错误：LLM 客户端未初始化"

        logger.info(f"开始总结 {len(reviews)} 条 {sentiment} 评论")

        # 限制评论数量
        if len(reviews) > max_reviews:
            reviews = reviews[:max_reviews]

        # 构建 prompt
        prompt = self._build_summary_prompt(reviews, sentiment)

        # 调用 LLM
        try:
            summary = self._call_llm(prompt)
            logger.info("总结生成完成")
            return summary
        except Exception as e:
            logger.error(f"总结生成失败: {e}")
            return f"错误：{e}"

    def _build_summary_prompt(self, reviews: List[str], sentiment: str) -> str:
        """构建总结 prompt"""

        # 采样评论（避免超过 token 限制）
        sample_size = min(len(reviews), 500)
        import random
        sampled_reviews = random.sample(reviews, sample_size)

        reviews_text = "\n".join([f"{i+1}. {review[:200]}" for i, review in enumerate(sampled_reviews)])

        sentiment_desc = {
            'positive': '正面',
            'negative': '负面',
            'all': '所有'
        }

        prompt = f"""
你是一位专业的游戏用户研究分析师。请分析以下 {sentiment_desc.get(sentiment, '所有')} 玩家评论，并生成一份详细的总结报告。

评论数据：
{reviews_text}

请从以下几个方面进行分析：

1. 核心问题/关注点（列出玩家最关注的5-8个问题）
2. 具体细节（每个问题的详细描述和玩家反馈）
3. 问题严重程度（根据提及频率评估）
4. 玩家情绪强度（强烈/中等/轻微）

请用中文输出，格式清晰，条理分明。
"""

        return prompt

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM API"""

        temperature = self.config.get('llm', {}).get(self.provider, {}).get('temperature', 0.7)
        max_tokens = self.config.get('llm', {}).get(self.provider, {}).get('max_tokens', 2000)

        if self.provider == 'openai':
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一位专业的游戏用户研究分析师。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content

        elif self.provider == 'anthropic':
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text

    def summarize_by_sentiment(self, df: pd.DataFrame,
                               text_column: str = 'review_text_clean') -> Dict[str, str]:
        """
        按情绪分类总结评论

        Args:
            df: 数据框
            text_column: 文本列名

        Returns:
            情绪-总结字典
        """
        summaries = {}

        for sentiment in ['positive', 'negative']:
            df_sentiment = df[df['sentiment'] == sentiment]

            if len(df_sentiment) == 0:
                logger.warning(f"没有 {sentiment} 评论")
                continue

            reviews = df_sentiment[text_column].tolist()
            summary = self.summarize_reviews(reviews, sentiment=sentiment)
            summaries[sentiment] = summary

        return summaries

    def summarize_by_topic(self, df: pd.DataFrame,
                          text_column: str = 'review_text_clean',
                          top_n: int = 5) -> Dict[int, str]:
        """
        按主题总结评论

        Args:
            df: 数据框
            text_column: 文本列名
            top_n: 总结前N个主题

        Returns:
            主题-总结字典
        """
        if 'topic_id' not in df.columns:
            logger.warning("数据中没有主题信息")
            return {}

        summaries = {}

        # 获取最热门的主题
        top_topics = df['topic_id'].value_counts().head(top_n).index

        for topic_id in top_topics:
            df_topic = df[df['topic_id'] == topic_id]
            reviews = df_topic[text_column].tolist()

            topic_desc = df_topic['topic_description'].iloc[0] if 'topic_description' in df_topic.columns else f"主题 {topic_id}"

            logger.info(f"总结主题: {topic_desc}")

            summary = self.summarize_reviews(reviews, sentiment='all')
            summaries[topic_id] = {
                'description': topic_desc,
                'summary': summary,
                'num_reviews': len(df_topic)
            }

        return summaries

    def generate_insights(self, df: pd.DataFrame,
                         sentiment_stats: Dict,
                         topics: Dict) -> str:
        """
        生成整体洞察报告

        Args:
            df: 数据框
            sentiment_stats: 情绪统计
            topics: 主题信息

        Returns:
            洞察报告
        """
        if not self.client:
            logger.error("LLM 客户端未初始化")
            return "错误：LLM 客户端未初始化"

        # 构建洞察 prompt
        prompt = self._build_insights_prompt(df, sentiment_stats, topics)

        # 调用 LLM
        try:
            insights = self._call_llm(prompt)
            logger.info("洞察报告生成完成")
            return insights
        except Exception as e:
            logger.error(f"洞察报告生成失败: {e}")
            return f"错误：{e}"

    def _build_insights_prompt(self, df: pd.DataFrame,
                              sentiment_stats: Dict,
                              topics: Dict) -> str:
        """构建洞察 prompt"""

        # 情绪统计
        sentiment_text = "\n".join([
            f"- {sentiment}: {count} ({pct:.1%})"
            for sentiment, (count, pct) in zip(
                sentiment_stats['sentiment_distribution'].keys(),
                zip(
                    sentiment_stats['sentiment_distribution'].values(),
                    sentiment_stats['sentiment_percentage'].values()
                )
            )
        ])

        # 主题信息
        topics_text = "\n".join([
            f"主题 {topic_id}: {', '.join(words[:5])}"
            for topic_id, words in list(topics.items())[:10]
        ])

        # 玩家类型分布
        player_type_dist = ""
        if 'player_type' in df.columns:
            player_type_dist = "\n".join([
                f"- {player_type}: {count}"
                for player_type, count in df['player_type'].value_counts().items()
            ])

        prompt = f"""
你是一位资深的游戏运营分析师。请基于以下玩家反馈数据生成一份综合洞察报告。

数据概况：
- 总评论数：{len(df)}
- 数据时间范围：{df['timestamp_created'].min()} 到 {df['timestamp_created'].max()}

情绪分布：
{sentiment_text}

玩家类型分布：
{player_type_dist}

主要讨论主题：
{topics_text}

请从以下角度生成洞察报告：

1. 整体玩家满意度评估
2. 玩家最关注的问题和需求
3. 不同玩家群体的差异化需求
4. 潜在的问题和风险
5. 玩家期望和建议

请用中文输出，格式清晰，分析深入。
"""

        return prompt


def main():
    """命令行入口"""
    import argparse
    import yaml
    import json

    parser = argparse.ArgumentParser(description='AI 评论总结工具')
    parser.add_argument('--input', type=str, required=True, help='输入文件路径')
    parser.add_argument('--output', type=str, help='输出文件名')
    parser.add_argument('--config', type=str, default='config/config.yaml', help='配置文件路径')
    parser.add_argument('--mode', type=str, default='sentiment',
                       choices=['sentiment', 'topic', 'all'],
                       help='总结模式')

    args = parser.parse_args()

    # 加载配置
    with open(args.config, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 读取数据
    logger.info(f"读取数据: {args.input}")
    df = pd.read_csv(args.input)

    # 创建总结器
    summarizer = ReviewSummarizer(config)

    # 执行总结
    summaries = {}

    if args.mode in ['sentiment', 'all']:
        logger.info("按情绪总结评论")
        sentiment_summaries = summarizer.summarize_by_sentiment(df)
        summaries['sentiment'] = sentiment_summaries

    if args.mode in ['topic', 'all'] and 'topic_id' in df.columns:
        logger.info("按主题总结评论")
        topic_summaries = summarizer.summarize_by_topic(df)
        summaries['topic'] = topic_summaries

    # 保存结果
    output_name = args.output or Path(args.input).stem + "_summary"
    output_path = Path('data/results') / f"{output_name}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)

    print(f"\n✅ AI 总结完成！结果已保存到: {output_path}")


if __name__ == '__main__':
    main()
