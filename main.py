"""
AI-Powered Game Player Insight & Operation Strategy (GPI-OSS) System
主程序 - 整合所有分析模块
"""

import argparse
import logging
import yaml
import json
from pathlib import Path
from datetime import datetime
import pandas as pd

from src.data_collection.steam_scraper import SteamReviewScraper
from src.data_processing.data_cleaner import DataCleaner
from src.analysis.sentiment.sentiment_analyzer import SentimentAnalyzer
from src.analysis.topic.topic_analyzer import TopicAnalyzer
from src.ai_modules.summarizer.review_summarizer import ReviewSummarizer
from src.ai_modules.strategy.strategy_generator import StrategyGenerator


def setup_logging(config: dict):
    """设置日志"""
    log_config = config.get('logging', {})

    log_level = getattr(logging, log_config.get('level', 'INFO'))
    log_format = log_config.get('log_format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
        ]
    )

    # 如果配置了文件日志
    if log_config.get('log_to_file', False):
        log_file = log_config.get('log_file', 'logs/gpi_system.log')
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(file_handler)


def load_config(config_path: str = 'config/config.yaml') -> dict:
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def collect_data(config: dict, game_id: int, game_name: str, max_reviews: int) -> Path:
    """数据采集"""
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("步骤 1: 数据采集")
    logger.info("=" * 50)

    scraper = SteamReviewScraper(config)
    raw_reviews = scraper.get_reviews(game_id, max_reviews=max_reviews)
    df = scraper.parse_reviews(raw_reviews)
    output_path = scraper.save_reviews(df, game_name)

    logger.info(f"✅ 数据采集完成，共 {len(df)} 条评论")
    return output_path


def process_data(config: dict, input_path: Path) -> Path:
    """数据清洗"""
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("步骤 2: 数据清洗与处理")
    logger.info("=" * 50)

    df = pd.read_csv(input_path)
    cleaner = DataCleaner(config)

    df_clean = cleaner.clean(df)
    df_clean = cleaner.add_features(df_clean)

    output_name = input_path.stem + "_cleaned"
    output_path = cleaner.save_processed_data(df_clean, output_name)

    logger.info(f"✅ 数据清洗完成，保留 {len(df_clean)} 条评论")
    return output_path


def analyze_sentiment(config: dict, input_path: Path) -> tuple:
    """情绪分析"""
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("步骤 3: 情绪分析")
    logger.info("=" * 50)

    df = pd.read_csv(input_path)
    analyzer = SentimentAnalyzer(config)

    df = analyzer.analyze_dataframe(df)
    stats = analyzer.get_sentiment_stats(df)

    # 保存结果
    output_name = input_path.stem + "_sentiment"
    output_path = Path('data/results') / f"{output_name}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')

    logger.info(f"✅ 情绪分析完成")
    logger.info(f"   正面: {stats['sentiment_percentage'].get('positive', 0):.1%}")
    logger.info(f"   负面: {stats['sentiment_percentage'].get('negative', 0):.1%}")
    logger.info(f"   中立: {stats['sentiment_percentage'].get('neutral', 0):.1%}")

    return output_path, stats


def analyze_topic(config: dict, input_path: Path) -> tuple:
    """主题分析"""
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("步骤 4: 主题分析")
    logger.info("=" * 50)

    df = pd.read_csv(input_path)
    analyzer = TopicAnalyzer(config)

    df, topics = analyzer.analyze_dataframe(df)

    # 保存结果
    output_name = input_path.stem + "_topic"
    output_path = Path('data/results') / f"{output_name}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')

    # 保存主题信息
    topics_path = Path('data/results') / f"{output_name}_topics.json"
    with open(topics_path, 'w', encoding='utf-8') as f:
        json.dump({str(k): v for k, v in topics.items()}, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ 主题分析完成，发现 {len(topics)} 个主题")

    return output_path, topics


def summarize_reviews(config: dict, input_path: Path) -> dict:
    """AI 总结"""
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("步骤 5: AI 评论总结")
    logger.info("=" * 50)

    df = pd.read_csv(input_path)
    summarizer = ReviewSummarizer(config)

    # 按情绪总结
    summaries = summarizer.summarize_by_sentiment(df)

    # 保存结果
    output_path = Path('data/results') / f"{input_path.stem}_summary.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ AI 总结完成")

    return summaries


def generate_strategies(config: dict, analysis_results: dict, game_name: str) -> dict:
    """生成运营策略"""
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("步骤 6: 生成运营策略")
    logger.info("=" * 50)

    generator = StrategyGenerator(config)

    game_info = {'name': game_name}
    strategies = generator.generate_strategies(analysis_results, game_info)
    quick_actions = generator.generate_quick_actions(analysis_results)
    roadmap = generator.generate_roadmap(analysis_results)

    # 保存结果
    output_path = Path('data/results') / 'operation_strategies.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'strategies': strategies,
            'quick_actions': quick_actions,
            'roadmap': roadmap
        }, f, ensure_ascii=False, indent=2)

    # 保存文本版本
    text_path = Path('data/results') / 'operation_strategies.txt'
    with open(text_path, 'w', encoding='utf-8') as f:
        f.write(f"# {game_name} 运营策略建议\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## 一、运营策略\n\n")
        f.write(strategies)
        f.write("\n\n## 二、快速行动建议\n\n")
        f.write(json.dumps(quick_actions, ensure_ascii=False, indent=2))
        f.write("\n\n## 三、产品路线图\n\n")
        f.write(roadmap)

    logger.info(f"✅ 策略生成完成")

    return {
        'strategies': strategies,
        'quick_actions': quick_actions,
        'roadmap': roadmap
    }


def generate_report(game_name: str, analysis_results: dict):
    """生成分析报告"""
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("生成分析报告")
    logger.info("=" * 50)

    report_path = Path('data/results') / f'{game_name}_analysis_report.txt'

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# {game_name} 玩家反馈分析报告\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("=" * 80 + "\n\n")

        # 情绪分析
        if 'sentiment_stats' in analysis_results:
            stats = analysis_results['sentiment_stats']
            f.write("## 一、玩家情绪分析\n\n")
            for sentiment, pct in stats.get('sentiment_percentage', {}).items():
                f.write(f"- {sentiment.capitalize()}: {pct:.1%}\n")
            f.write("\n")

        # 主题分析
        if 'topics' in analysis_results:
            topics = analysis_results['topics']
            f.write("## 二、主要讨论主题\n\n")
            for topic_id, words in list(topics.items())[:10]:
                f.write(f"主题 {topic_id}: {', '.join(words[:5])}\n")
            f.write("\n")

        # AI 总结
        if 'summaries' in analysis_results:
            summaries = analysis_results['summaries']
            f.write("## 三、AI 评论总结\n\n")
            for sentiment, summary in summaries.items():
                f.write(f"### {sentiment.capitalize()} 评论总结\n\n")
                f.write(summary)
                f.write("\n\n")

        # 运营策略
        if 'strategy_results' in analysis_results:
            strategy_results = analysis_results['strategy_results']
            f.write("## 四、运营策略建议\n\n")
            f.write(strategy_results.get('strategies', ''))
            f.write("\n\n")

    logger.info(f"✅ 报告已生成: {report_path}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='AI-Powered Game Player Insight System')
    parser.add_argument('--config', type=str, default='config/config.yaml', help='配置文件路径')
    parser.add_argument('--mode', type=str, default='all',
                       choices=['collect', 'process', 'analyze', 'all'],
                       help='运行模式')
    parser.add_argument('--game-id', type=int, help='Steam 游戏 ID')
    parser.add_argument('--game-name', type=str, help='游戏名称')
    parser.add_argument('--input', type=str, help='输入文件路径（用于非采集模式）')
    parser.add_argument('--max-reviews', type=int, help='最大采集评论数')

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 设置日志
    setup_logging(config)
    logger = logging.getLogger(__name__)

    logger.info("=" * 50)
    logger.info("AI-Powered Game Player Insight System")
    logger.info("=" * 50)

    try:
        analysis_results = {}

        if args.mode in ['collect', 'all']:
            # 数据采集
            game_id = args.game_id or config['data_collection']['target_games'][0]['app_id']
            game_name = args.game_name or config['data_collection']['target_games'][0]['name']
            max_reviews = args.max_reviews or config['data_collection']['max_reviews_per_game']

            raw_data_path = collect_data(config, game_id, game_name, max_reviews)
            current_file = raw_data_path
        else:
            current_file = Path(args.input)
            game_name = args.game_name or current_file.stem

        if args.mode in ['process', 'all']:
            # 数据处理
            processed_data_path = process_data(config, current_file)
            current_file = processed_data_path

        if args.mode in ['analyze', 'all']:
            # 情绪分析
            sentiment_data_path, sentiment_stats = analyze_sentiment(config, current_file)
            analysis_results['sentiment_stats'] = sentiment_stats
            current_file = sentiment_data_path

            # 主题分析
            topic_data_path, topics = analyze_topic(config, current_file)
            analysis_results['topics'] = topics
            current_file = topic_data_path

            # AI 总结
            summaries = summarize_reviews(config, current_file)
            analysis_results['summaries'] = summaries
            analysis_results['negative_summary'] = summaries.get('negative', '')

            # 生成运营策略
            strategy_results = generate_strategies(config, analysis_results, game_name)
            analysis_results['strategy_results'] = strategy_results

            # 生成报告
            generate_report(game_name, analysis_results)

        logger.info("=" * 50)
        logger.info("🎉 分析流程全部完成！")
        logger.info("=" * 50)
        logger.info(f"\n最终结果文件: {current_file}")
        logger.info(f"分析报告: data/results/{game_name}_analysis_report.txt")
        logger.info(f"\n启动可视化 Dashboard: streamlit run src/visualization/dashboard.py")

    except Exception as e:
        logger.error(f"❌ 程序执行失败: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    main()
