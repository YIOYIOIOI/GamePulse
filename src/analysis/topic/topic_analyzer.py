"""
主题分析模块
使用 LDA、NMF 等方法提取评论中的核心主题
"""

import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Tuple
from pathlib import Path
from collections import Counter
import re

logger = logging.getLogger(__name__)


class TopicAnalyzer:
    """主题分析器"""

    def __init__(self, config: dict):
        self.config = config
        self.method = config.get('topic_analysis', {}).get('method', 'lda')
        self.num_topics = config.get('topic_analysis', {}).get('num_topics', 10)
        self.max_features = config.get('topic_analysis', {}).get('max_features', 5000)
        self.ngram_range = tuple(config.get('topic_analysis', {}).get('ngram_range', [1, 2]))
        self.min_df = config.get('topic_analysis', {}).get('min_df', 5)
        self.max_df = config.get('topic_analysis', {}).get('max_df', 0.8)

        # 下载必要的 NLTK 数据
        self._download_nltk_data()

        # 初始化停用词
        self.stop_words = self._get_stop_words()

        # 模型
        self.vectorizer = None
        self.model = None
        self.feature_names = None

    @staticmethod
    def _download_nltk_data():
        """下载 NLTK 数据"""
        try:
            import nltk
            nltk.download('stopwords', quiet=True)
            nltk.download('punkt', quiet=True)
        except Exception as e:
            logger.warning(f"NLTK 数据下载失败: {e}")

    def _get_stop_words(self) -> set:
        """获取停用词列表"""
        stop_words = set()

        # 英文停用词
        try:
            import nltk
            from nltk.corpus import stopwords
            stop_words.update(stopwords.words('english'))
        except Exception as e:
            logger.warning(f"无法加载 NLTK 停用词: {e}")
            # 使用基本的停用词列表
            stop_words.update([
                'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
                'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at'
            ])

        # 添加游戏相关的通用词
        game_common_words = {
            'game', 'play', 'played', 'playing', 'player', 'games',
            'good', 'bad', 'great', 'nice', 'best', 'worst',
            'like', 'love', 'hate', 'really', 'just', 'get',
            'time', 'hours', 'hour', 'min', 'mins',
            'recommend', 'recommended', 'buy', 'bought'
        }
        stop_words.update(game_common_words)

        return stop_words

    def fit_transform(self, texts: List[str]) -> Tuple[np.ndarray, np.ndarray]:
        """
        训练主题模型并转换文本

        Args:
            texts: 文本列表

        Returns:
            文档-主题矩阵，主题-词矩阵
        """
        try:
            from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
            from sklearn.decomposition import LatentDirichletAllocation, NMF
        except ImportError as e:
            logger.error(f"缺少必要的依赖: {e}")
            logger.error("请安装: pip install scikit-learn")
            raise ImportError("缺少依赖: scikit-learn")

        logger.info(f"开始主题分析，文档数: {len(texts)}, 方法: {self.method}")

        # 1. 文本向量化
        if self.method == 'lda':
            self.vectorizer = CountVectorizer(
                max_features=self.max_features,
                ngram_range=self.ngram_range,
                min_df=self.min_df,
                max_df=self.max_df,
                stop_words=list(self.stop_words)
            )
        else:
            self.vectorizer = TfidfVectorizer(
                max_features=self.max_features,
                ngram_range=self.ngram_range,
                min_df=self.min_df,
                max_df=self.max_df,
                stop_words=list(self.stop_words)
            )

        doc_term_matrix = self.vectorizer.fit_transform(texts)
        self.feature_names = self.vectorizer.get_feature_names_out()

        logger.info(f"特征数量: {len(self.feature_names)}")

        # 2. 主题建模
        if self.method == 'lda':
            self.model = LatentDirichletAllocation(
                n_components=self.num_topics,
                random_state=42,
                n_jobs=-1,
                max_iter=20
            )
        elif self.method == 'nmf':
            self.model = NMF(
                n_components=self.num_topics,
                random_state=42,
                max_iter=200
            )
        else:
            raise ValueError(f"不支持的方法: {self.method}")

        doc_topic_matrix = self.model.fit_transform(doc_term_matrix)

        logger.info("主题建模完成")

        return doc_topic_matrix, self.model.components_

    def get_top_words_per_topic(self, n_words: int = 10) -> Dict[int, List[str]]:
        """
        获取每个主题的关键词

        Args:
            n_words: 每个主题的词数

        Returns:
            主题-关键词字典
        """
        if self.model is None or self.feature_names is None:
            logger.error("模型未训练")
            return {}

        topics = {}
        for topic_idx, topic in enumerate(self.model.components_):
            top_indices = topic.argsort()[-n_words:][::-1]
            top_words = [self.feature_names[i] for i in top_indices]
            topics[topic_idx] = top_words

        return topics

    def assign_topics_to_documents(self, doc_topic_matrix: np.ndarray) -> np.ndarray:
        """
        为每个文档分配主题

        Args:
            doc_topic_matrix: 文档-主题矩阵

        Returns:
            主题标签数组
        """
        return doc_topic_matrix.argmax(axis=1)

    def analyze_dataframe(self, df: pd.DataFrame, text_column: str = 'review_text_clean') -> pd.DataFrame:
        """
        对 DataFrame 进行主题分析

        Args:
            df: 数据框
            text_column: 文本列名

        Returns:
            添加了主题信息的数据框
        """
        logger.info(f"对 {len(df)} 条评论进行主题分析")

        # 获取文本
        texts = df[text_column].fillna('').tolist()

        # 主题分析
        doc_topic_matrix, topic_term_matrix = self.fit_transform(texts)

        # 分配主题
        df['topic_id'] = self.assign_topics_to_documents(doc_topic_matrix)

        # 添加主题概率
        for i in range(self.num_topics):
            df[f'topic_{i}_prob'] = doc_topic_matrix[:, i]

        # 获取主题关键词
        topics = self.get_top_words_per_topic(n_words=10)

        # 为每个主题生成描述
        topic_descriptions = {}
        for topic_id, words in topics.items():
            topic_descriptions[topic_id] = ', '.join(words[:5])

        df['topic_description'] = df['topic_id'].map(topic_descriptions)

        logger.info("主题分析完成")

        return df, topics

    def get_topic_sentiment_distribution(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        获取每个主题的情绪分布

        Args:
            df: 包含主题和情绪信息的数据框

        Returns:
            主题-情绪分布表
        """
        if 'topic_id' not in df.columns or 'sentiment' not in df.columns:
            logger.warning("缺少必要的列")
            return pd.DataFrame()

        # 统计主题-情绪分布
        topic_sentiment = df.groupby(['topic_id', 'sentiment']).size().unstack(fill_value=0)

        # 计算百分比
        topic_sentiment_pct = topic_sentiment.div(topic_sentiment.sum(axis=1), axis=0) * 100

        return topic_sentiment, topic_sentiment_pct

    def extract_keywords_by_tfidf(self, df: pd.DataFrame,
                                  text_column: str = 'review_text_clean',
                                  top_n: int = 50) -> List[Tuple[str, float]]:
        """
        使用 TF-IDF 提取关键词

        Args:
            df: 数据框
            text_column: 文本列名
            top_n: 返回前N个关键词

        Returns:
            关键词-权重列表
        """
        texts = df[text_column].fillna('').tolist()

        vectorizer = TfidfVectorizer(
            max_features=1000,
            ngram_range=(1, 2),
            stop_words=list(self.stop_words)
        )

        tfidf_matrix = vectorizer.fit_transform(texts)
        feature_names = vectorizer.get_feature_names_out()

        # 计算每个词的平均 TF-IDF 值
        avg_tfidf = tfidf_matrix.mean(axis=0).A1
        top_indices = avg_tfidf.argsort()[-top_n:][::-1]

        keywords = [(feature_names[i], avg_tfidf[i]) for i in top_indices]

        return keywords

    def analyze_topics_by_sentiment(self, df: pd.DataFrame,
                                   text_column: str = 'review_text_clean') -> Dict:
        """
        分别分析正面和负面评论的主题

        Args:
            df: 数据框
            text_column: 文本列名

        Returns:
            正负面主题分析结果
        """
        results = {}

        for sentiment in ['positive', 'negative']:
            df_subset = df[df['sentiment'] == sentiment]

            if len(df_subset) < 100:
                logger.warning(f"{sentiment} 评论数量过少，跳过")
                continue

            logger.info(f"分析 {sentiment} 评论的主题")

            texts = df_subset[text_column].fillna('').tolist()
            doc_topic_matrix, _ = self.fit_transform(texts)
            topics = self.get_top_words_per_topic(n_words=10)

            results[sentiment] = {
                'topics': topics,
                'num_reviews': len(df_subset)
            }

        return results


def main():
    """命令行入口"""
    import argparse
    import yaml
    import json

    parser = argparse.ArgumentParser(description='主题分析工具')
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
    analyzer = TopicAnalyzer(config)

    # 执行主题分析
    df, topics = analyzer.analyze_dataframe(df)

    # 获取主题-情绪分布
    if 'sentiment' in df.columns:
        topic_sentiment, topic_sentiment_pct = analyzer.get_topic_sentiment_distribution(df)

    # 保存结果
    output_name = args.output or Path(args.input).stem + "_topic"
    output_path = Path('data/results') / f"{output_name}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')

    # 保存主题信息
    topics_path = Path('data/results') / f"{output_name}_topics.json"
    with open(topics_path, 'w', encoding='utf-8') as f:
        json.dump({k: v for k, v in topics.items()}, f, ensure_ascii=False, indent=2)

    # 打印结果
    print(f"\n✅ 主题分析完成！")
    print(f"\n发现 {len(topics)} 个主题:")
    for topic_id, words in topics.items():
        print(f"\n主题 {topic_id}: {', '.join(words[:5])}")


if __name__ == '__main__':
    main()
