"""
Steam 评论数据采集模块
支持采集 Steam 游戏评论数据
"""

import requests
import time
import json
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import logging
from tqdm import tqdm

logger = logging.getLogger(__name__)


class SteamReviewScraper:
    """Steam 评论爬虫"""

    def __init__(self, config: dict):
        self.config = config
        self.base_url = config.get('steam', {}).get('base_url', 'https://store.steampowered.com')
        self.api_key = config.get('steam', {}).get('api_key', '')
        self.timeout = config.get('steam', {}).get('request_timeout', 30)
        self.delay = config.get('steam', {}).get('request_delay', 1)
        self.max_retries = config.get('steam', {}).get('max_retries', 3)

    def get_reviews(self,
                   app_id: int,
                   max_reviews: int = 100000,
                   language: str = 'all',
                   review_type: str = 'all') -> List[Dict]:
        """
        采集游戏评论（支持大规模采集，10w+）

        Args:
            app_id: Steam游戏ID
            max_reviews: 最大采集数量（默认10万，支持更多）
            language: 语言过滤
            review_type: 评论类型 (all/positive/negative)

        Returns:
            评论列表
        """
        logger.info(f"开始采集游戏 {app_id} 的评论，目标数量: {max_reviews}")

        reviews = []
        cursor = "*"

        with tqdm(total=max_reviews, desc=f"采集 App {app_id}") as pbar:
            while len(reviews) < max_reviews:
                batch = self._fetch_review_batch(app_id, cursor, language, review_type)

                if not batch or 'reviews' not in batch:
                    logger.warning("未获取到更多评论，停止采集")
                    break

                batch_reviews = batch['reviews']
                if not batch_reviews:
                    break

                reviews.extend(batch_reviews)
                pbar.update(len(batch_reviews))

                # 获取下一页游标
                cursor = batch.get('cursor', '')
                if not cursor or cursor == '*':
                    logger.info("已到达最后一页")
                    break

                time.sleep(self.delay)

        logger.info(f"采集完成，共获取 {len(reviews)} 条评论")
        return reviews[:max_reviews]

    def _fetch_review_batch(self,
                           app_id: int,
                           cursor: str = "*",
                           language: str = 'all',
                           review_type: str = 'all') -> Optional[Dict]:
        """获取一批评论数据"""

        url = f"https://store.steampowered.com/appreviews/{app_id}"
        params = {
            'json': 1,
            'cursor': cursor,
            'language': language,
            'filter': review_type,
            'review_type': 'all',
            'purchase_type': 'all',
            'num_per_page': 100
        }

        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()

                if data.get('success') == 1:
                    return data
                else:
                    logger.warning(f"API返回失败: {data}")
                    return None

            except requests.RequestException as e:
                logger.warning(f"请求失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error("达到最大重试次数")
                    return None

    def parse_reviews(self, raw_reviews: List[Dict]) -> pd.DataFrame:
        """
        解析原始评论数据为结构化数据

        Args:
            raw_reviews: 原始评论数据

        Returns:
            DataFrame 格式的评论数据
        """
        logger.info(f"解析 {len(raw_reviews)} 条评论")

        parsed_data = []
        for review in raw_reviews:
            parsed_data.append({
                'review_id': review.get('recommendationid', ''),
                'author_steamid': review.get('author', {}).get('steamid', ''),
                'review_text': review.get('review', ''),
                'vote_up': review.get('voted_up', False),
                'votes_up': review.get('votes_up', 0),
                'votes_funny': review.get('votes_funny', 0),
                'weighted_vote_score': review.get('weighted_vote_score', 0),
                'playtime_forever': review.get('author', {}).get('playtime_forever', 0) / 60,  # 转换为小时
                'playtime_at_review': review.get('author', {}).get('playtime_at_review', 0) / 60,
                'timestamp_created': datetime.fromtimestamp(review.get('timestamp_created', 0)),
                'timestamp_updated': datetime.fromtimestamp(review.get('timestamp_updated', 0)),
                'language': review.get('language', ''),
                'num_games_owned': review.get('author', {}).get('num_games_owned', 0),
                'num_reviews': review.get('author', {}).get('num_reviews', 0),
                'comment_count': review.get('comment_count', 0),
                'steam_purchase': review.get('steam_purchase', True),
                'received_for_free': review.get('received_for_free', False),
                'written_during_early_access': review.get('written_during_early_access', False)
            })

        df = pd.DataFrame(parsed_data)
        logger.info(f"解析完成，数据形状: {df.shape}")
        return df

    def save_reviews(self, df: pd.DataFrame, game_name: str, output_dir: str = 'data/raw'):
        """保存评论数据"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{game_name}_{timestamp}"

        # 保存为多种格式
        csv_path = output_path / f"{filename}.csv"
        json_path = output_path / f"{filename}.json"

        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        df.to_json(json_path, orient='records', force_ascii=False, indent=2)

        logger.info(f"数据已保存到: {csv_path}")
        return csv_path


def main():
    """命令行入口"""
    import sys
    import io
    import argparse
    import yaml

    # 设置UTF-8编码
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    parser = argparse.ArgumentParser(description='Steam 评论采集工具')
    parser.add_argument('--game-id', type=int, required=True, help='Steam游戏ID')
    parser.add_argument('--game-name', type=str, help='游戏名称')
    parser.add_argument('--max-reviews', type=int, default=10000, help='最大采集数量')
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

    # 创建爬虫实例
    scraper = SteamReviewScraper(config)

    # 采集评论
    raw_reviews = scraper.get_reviews(args.game_id, max_reviews=args.max_reviews)

    # 解析评论
    df = scraper.parse_reviews(raw_reviews)

    # 保存评论
    game_name = args.game_name or f"game_{args.game_id}"
    scraper.save_reviews(df, game_name)

    print(f"\n✅ 采集完成！共获取 {len(df)} 条评论")
    print(f"正面评论: {df['vote_up'].sum()} ({df['vote_up'].mean():.1%})")
    print(f"负面评论: {(~df['vote_up']).sum()} ({(~df['vote_up']).mean():.1%})")


if __name__ == '__main__':
    main()
