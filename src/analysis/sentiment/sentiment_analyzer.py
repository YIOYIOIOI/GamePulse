"""
情绪分析模块
使用预训练模型进行情绪分析
"""

import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """情绪分析器"""

    def __init__(self, config: dict):
        self.config = config
        self.model_name = config.get('sentiment_analysis', {}).get(
            'model_name',
            'distilbert-base-uncased-finetuned-sst-2-english'
        )
        self.batch_size = config.get('sentiment_analysis', {}).get('batch_size', 32)
        self.use_gpu = config.get('sentiment_analysis', {}).get('use_gpu', True)
        self.use_transformer = config.get('sentiment_analysis', {}).get('use_transformer', False)

        # 初始化模型（如果启用）
        self.pipeline = None
        if self.use_transformer:
            self._init_model()
        else:
            logger.info("使用规则基础的情绪分析（快速模式）")

    def _init_model(self):
        """初始化情绪分析模型"""
        logger.info(f"加载情绪分析模型: {self.model_name}")

        try:
            import torch
            from transformers import pipeline
        except ImportError as e:
            logger.warning(f"transformers库未安装，将使用规则基础的分析方法")
            logger.info("如需使用深度学习模型，请安装: pip install transformers torch")
            self.pipeline = None
            return

        device = 0 if self.use_gpu and torch.cuda.is_available() else -1

        try:
            self.pipeline = pipeline(
                'sentiment-analysis',
                model=self.model_name,
                device=device,
                truncation=True,
                max_length=512
            )
            logger.info("模型加载成功")
        except Exception as e:
            logger.warning(f"模型加载失败: {e}，将使用规则基础的分析方法")
            self.pipeline = None

    def _rule_based_sentiment(self, text: str) -> Dict:
        """规则基础的情绪分析"""
        if not text or pd.isna(text):
            return {'label': 'NEUTRAL', 'score': 0.5}

        text_lower = str(text).lower()

        # 正面词汇
        positive_words = [
            'good', 'great', 'love', 'amazing', 'best', 'perfect', 'excellent',
            'fun', 'enjoy', 'awesome', 'fantastic', 'wonderful', 'nice', 'recommend',
            'beautiful', 'incredible', 'outstanding', 'superb', 'brilliant'
        ]

        # 负面词汇
        negative_words = [
            'bad', 'worst', 'hate', 'awful', 'terrible', 'boring', 'disappointing',
            'waste', 'broken', 'trash', 'garbage', 'sucks', 'frustrating', 'horrible',
            'poor', 'useless', 'annoying', 'stupid', 'lame', 'fail'
        ]

        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)

        total = pos_count + neg_count
        if total == 0:
            return {'label': 'NEUTRAL', 'score': 0.5}

        if pos_count > neg_count:
            score = 0.5 + (pos_count / (pos_count + neg_count)) * 0.5
            return {'label': 'POSITIVE', 'score': score}
        elif neg_count > pos_count:
            score = 0.5 + (neg_count / (pos_count + neg_count)) * 0.5
            return {'label': 'NEGATIVE', 'score': score}
        else:
            return {'label': 'NEUTRAL', 'score': 0.5}

    def analyze(self, texts: List[str]) -> List[Dict]:
        """
        批量分析文本情绪

        Args:
            texts: 文本列表

        Returns:
            情绪分析结果列表
        """
        logger.info(f"开始情绪分析，文本数量: {len(texts)}")

        # 如果没有深度学习模型，使用规则基础的方法
        if self.pipeline is None:
            logger.info("使用规则基础的情绪分析")
            results = [self._rule_based_sentiment(text) for text in texts]
            logger.info("情绪分析完成")
            return results

        # 使用深度学习模型
        try:
            from tqdm import tqdm
        except ImportError:
            # 如果没有tqdm，定义一个简单的替代
            def tqdm(iterable, **kwargs):
                return iterable

        results = []
        num_batches = (len(texts) + self.batch_size - 1) // self.batch_size

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]

            try:
                batch_results = self.pipeline(batch)
                results.extend(batch_results)
            except Exception as e:
                logger.warning(f"批次 {i} 分析失败: {e}，使用规则方法")
                # 使用规则方法作为fallback
                results.extend([self._rule_based_sentiment(text) for text in batch])

        logger.info("情绪分析完成")
        return results

    def analyze_dataframe(self, df: pd.DataFrame, text_column: str = 'review_text_clean') -> pd.DataFrame:
        """
        对 DataFrame 进行情绪分析

        Args:
            df: 数据框
            text_column: 文本列名

        Returns:
            添加了情绪分析结果的数据框
        """
        logger.info(f"对 {len(df)} 条评论进行情绪分析")

        # 确保文本列存在
        if text_column not in df.columns:
            logger.error(f"列 {text_column} 不存在")
            raise ValueError(f"列 {text_column} 不存在")

        # 获取文本列表
        texts = df[text_column].fillna('').tolist()

        # 执行情绪分析
        results = self.analyze(texts)

        # 解析结果
        df['sentiment_label'] = [r['label'] for r in results]
        df['sentiment_score'] = [r['score'] for r in results]

        # 标准化标签
        df['sentiment'] = df['sentiment_label'].apply(self._normalize_label)

        # 计算情绪强度（正面情绪得分）
        df['sentiment_positive_score'] = df.apply(
            lambda row: row['sentiment_score'] if row['sentiment'] == 'positive'
            else 1 - row['sentiment_score'],
            axis=1
        )

        logger.info("情绪分析完成")

        return df

    @staticmethod
    def _normalize_label(label: str) -> str:
        """标准化情绪标签"""
        label = label.upper()
        if label in ['POSITIVE', 'POS', '1']:
            return 'positive'
        elif label in ['NEGATIVE', 'NEG', '0']:
            return 'negative'
        else:
            return 'neutral'

    def get_sentiment_stats(self, df: pd.DataFrame) -> Dict:
        """
        获取情绪统计信息

        Args:
            df: 包含情绪分析结果的数据框

        Returns:
            统计信息字典
        """
        stats = {
            'total_reviews': len(df),
            'sentiment_distribution': df['sentiment'].value_counts().to_dict(),
            'sentiment_percentage': df['sentiment'].value_counts(normalize=True).to_dict(),
            'avg_positive_score': df[df['sentiment'] == 'positive']['sentiment_score'].mean(),
            'avg_negative_score': df[df['sentiment'] == 'negative']['sentiment_score'].mean(),
            'avg_overall_score': df['sentiment_positive_score'].mean()
        }

        return stats

    def get_sentiment_trend(self, df: pd.DataFrame, time_column: str = 'year_month') -> pd.DataFrame:
        """
        获取情绪随时间变化趋势

        Args:
            df: 数据框
            time_column: 时间列名

        Returns:
            时间序列统计
        """
        if time_column not in df.columns:
            logger.warning(f"时间列 {time_column} 不存在，无法生成趋势")
            return pd.DataFrame()

        # 按时间分组统计
        trend = df.groupby([time_column, 'sentiment']).size().unstack(fill_value=0)

        # 计算百分比
        trend_pct = trend.div(trend.sum(axis=1), axis=0) * 100

        # 添加总数
        trend['total'] = trend.sum(axis=1)

        return trend, trend_pct

    def compare_sentiment_by_group(self,
                                  df: pd.DataFrame,
                                  group_column: str = 'player_type') -> pd.DataFrame:
        """
        比较不同群体的情绪差异

        Args:
            df: 数据框
            group_column: 分组列名

        Returns:
            分组统计结果
        """
        if group_column not in df.columns:
            logger.warning(f"分组列 {group_column} 不存在")
            return pd.DataFrame()

        # 按组统计情绪
        grouped = df.groupby([group_column, 'sentiment']).size().unstack(fill_value=0)

        # 计算百分比
        grouped_pct = grouped.div(grouped.sum(axis=1), axis=0) * 100

        return grouped, grouped_pct


def main():
    """命令行入口"""
    import argparse
    import yaml

    parser = argparse.ArgumentParser(description='情绪分析工具')
    parser.add_argument('--input', type=str, required=True, help='输入文件路径')
    parser.add_argument('--output', type=str, help='输出文件名')
    parser.add_argument('--config', type=str, default='config/config.yaml', help='配置文件路径')

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

    # 创建分析器
    analyzer = SentimentAnalyzer(config)

    # 执行情绪分析
    df = analyzer.analyze_dataframe(df)

    # 获取统计信息
    stats = analyzer.get_sentiment_stats(df)

    # 保存结果
    output_name = args.output or Path(args.input).stem + "_sentiment"
    output_path = Path('data/results') / f"{output_name}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')

    # 打印统计信息
    print(f"\n✅ 情绪分析完成！")
    print(f"\n情绪分布:")
    for sentiment, count in stats['sentiment_distribution'].items():
        percentage = stats['sentiment_percentage'][sentiment]
        print(f"  {sentiment}: {count} ({percentage:.1%})")

    print(f"\n平均情绪得分: {stats['avg_overall_score']:.2f}")


if __name__ == '__main__':
    main()
