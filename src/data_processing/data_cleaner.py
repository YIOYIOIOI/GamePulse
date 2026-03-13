"""
数据清洗模块
对原始评论数据进行清洗和预处理
"""

import pandas as pd
import re
import logging
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class DataCleaner:
    """数据清洗器"""

    def __init__(self, config: dict):
        self.config = config
        self.min_length = config.get('data_processing', {}).get('min_review_length', 20)
        self.remove_duplicates = config.get('data_processing', {}).get('remove_duplicates', True)
        self.remove_spam = config.get('data_processing', {}).get('remove_spam', True)
        self.language_filter = config.get('data_processing', {}).get('language_filter', ['en', 'zh'])

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        执行完整的数据清洗流程

        Args:
            df: 原始数据

        Returns:
            清洗后的数据
        """
        logger.info(f"开始数据清洗，原始数据量: {len(df)}")

        original_count = len(df)

        # 1. 删除重复数据
        if self.remove_duplicates:
            df = self._remove_duplicates(df)
            logger.info(f"删除重复后: {len(df)} 条 (删除 {original_count - len(df)} 条)")

        # 2. 删除过短评论
        df = self._remove_short_reviews(df)
        logger.info(f"删除过短评论后: {len(df)} 条")

        # 3. 删除垃圾评论
        if self.remove_spam:
            df = self._remove_spam_reviews(df)
            logger.info(f"删除垃圾评论后: {len(df)} 条")

        # 4. 文本标准化
        df = self._normalize_text(df)

        # 5. 处理缺失值
        df = self._handle_missing_values(df)

        logger.info(f"数据清洗完成，最终数据量: {len(df)} (保留率: {len(df)/original_count:.1%})")

        return df

    def _remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """删除重复评论"""
        # 基于评论ID去重
        df = df.drop_duplicates(subset=['review_id'], keep='first')

        # 基于评论内容去重（避免内容完全相同但ID不同的情况）
        df = df.drop_duplicates(subset=['review_text'], keep='first')

        return df

    def _remove_short_reviews(self, df: pd.DataFrame) -> pd.DataFrame:
        """删除过短的评论"""
        df['text_length'] = df['review_text'].str.len()
        df = df[df['text_length'] >= self.min_length]
        return df

    def _remove_spam_reviews(self, df: pd.DataFrame) -> pd.DataFrame:
        """删除垃圾/广告评论"""

        # 垃圾评论特征
        spam_patterns = [
            r'^\+{5,}',  # 连续加号
            r'^-{5,}',   # 连续减号
            r'(?:http|www)\.',  # 包含链接
            r'discount|促销|打折|优惠|代购',  # 广告关键词
            r'^[^a-zA-Z\u4e00-\u9fa5]{20,}',  # 过多特殊字符
        ]

        spam_mask = pd.Series([False] * len(df), index=df.index)

        for pattern in spam_patterns:
            spam_mask |= df['review_text'].str.contains(pattern, regex=True, na=False, flags=0)

        logger.info(f"检测到 {spam_mask.sum()} 条垃圾评论")

        return df[~spam_mask]

    def _normalize_text(self, df: pd.DataFrame) -> pd.DataFrame:
        """文本标准化处理"""

        def normalize(text: str) -> str:
            if pd.isna(text):
                return ""

            # 1. 转换为小写（保留中文）
            # text = text.lower()

            # 2. 删除多余空白
            text = re.sub(r'\s+', ' ', text)

            # 3. 删除特殊字符（保留基本标点）
            text = re.sub(r'[^\w\s\u4e00-\u9fa5.,!?;:\-\'\"()]+', ' ', text)

            # 4. 去除首尾空格
            text = text.strip()

            return text

        df['review_text_clean'] = df['review_text'].apply(normalize)

        return df

    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """处理缺失值"""

        # 填充数值型缺失值
        numeric_columns = ['playtime_forever', 'playtime_at_review', 'votes_up', 'comment_count']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = df[col].fillna(0)

        # 删除评论内容为空的行
        df = df[df['review_text_clean'].str.len() > 0]

        return df

    def add_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加衍生特征"""

        logger.info("添加衍生特征")

        # 1. 评论长度
        df['review_length'] = df['review_text_clean'].str.len()

        # 2. 词数统计
        df['word_count'] = df['review_text_clean'].str.split().str.len()

        # 3. 玩家类型（基于游戏时长）
        df['player_type'] = pd.cut(
            df['playtime_forever'],
            bins=[-0.1, 10, 100, float('inf')],
            labels=['new_player', 'regular_player', 'hardcore_player']
        )

        # 4. 时间特征
        df['year'] = pd.to_datetime(df['timestamp_created']).dt.year
        df['month'] = pd.to_datetime(df['timestamp_created']).dt.month
        df['year_month'] = pd.to_datetime(df['timestamp_created']).dt.to_period('M')

        # 5. 评论热度（基于点赞数）
        df['review_popularity'] = pd.cut(
            df['votes_up'],
            bins=[-1, 0, 5, 20, float('inf')],
            labels=['unpopular', 'normal', 'popular', 'very_popular']
        )

        return df

    def save_processed_data(self, df: pd.DataFrame, filename: str, output_dir: str = 'data/processed'):
        """保存清洗后的数据"""

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 保存为多种格式
        csv_path = output_path / f"{filename}.csv"
        json_path = output_path / f"{filename}.json"
        excel_path = output_path / f"{filename}.xlsx"

        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        df.to_json(json_path, orient='records', force_ascii=False, indent=2)

        # Excel 格式（如果数据量不大）
        if len(df) < 50000:
            df.to_excel(excel_path, index=False, engine='openpyxl')

        logger.info(f"处理后的数据已保存到: {csv_path}")

        return csv_path


def main():
    """命令行入口"""
    import argparse
    import yaml

    parser = argparse.ArgumentParser(description='数据清洗工具')
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

    # 创建清洗器
    cleaner = DataCleaner(config)

    # 执行清洗
    df_clean = cleaner.clean(df)

    # 添加特征
    df_clean = cleaner.add_features(df_clean)

    # 保存数据
    output_name = args.output or Path(args.input).stem + "_cleaned"
    cleaner.save_processed_data(df_clean, output_name)

    # 打印统计信息
    print(f"\n✅ 数据清洗完成！")
    print(f"原始数据: {len(df)} 条")
    print(f"清洗后: {len(df_clean)} 条")
    print(f"保留率: {len(df_clean)/len(df):.1%}")
    print(f"\n玩家类型分布:")
    print(df_clean['player_type'].value_counts())


if __name__ == '__main__':
    main()
