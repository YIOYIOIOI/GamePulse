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
from src.analysis.pipeline import run_full
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


def run_analysis(config: dict, input_path: Path) -> tuple:
    """统一分析管线：语言归一 → 情绪 → 弱标签评测 → 语言感知主题 → KMeans 分层 → 质量门槛。

    所有工件落到 data/results/：
      {stem}_analyzed.csv                主数据（含 lang_code / sentiment / topic_id / segment_label）
      {stem}_topics.json                 主题词表
      {stem}_topic_metrics.json          NPMI / 多样性 / 建模口径 /（全量时）NMI 诊断
      {stem}_sentiment_evaluation.json   vote_up 弱标签评测
      {stem}_segmentation_meta.json      分层口径（k / silhouette / 簇画像）
      {stem}_quality_package.json        质量门槛与分析包
    """
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("步骤 3: 统一分析管线（情绪 / 评测 / 主题 / 分层 / 质量门槛）")
    logger.info("=" * 50)

    df = pd.read_csv(input_path)
    result = run_full(df, config)

    out_dir = Path('data/results')
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem

    output_path = out_dir / f"{stem}_analyzed.csv"
    result.df.to_csv(output_path, index=False, encoding='utf-8-sig')

    def _dump(name: str, obj) -> None:
        if obj is None:
            return
        with open(out_dir / f"{stem}_{name}.json", 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2, default=str)

    _dump('topics', {str(k): v for k, v in (result.topics or {}).items()} or None)
    _dump('topic_metrics', result.topic_metrics)
    _dump('sentiment_evaluation', result.sentiment_evaluation)
    _dump('segmentation_meta', result.segmentation_meta)
    _dump('quality_package', result.quality_package)

    stats = result.sentiment_stats or {}
    if stats:
        logger.info("   正面: %.1f%%", stats['sentiment_percentage'].get('positive', 0) * 100)
        logger.info("   负面: %.1f%%", stats['sentiment_percentage'].get('negative', 0) * 100)
    if result.sentiment_evaluation:
        overall = result.sentiment_evaluation.get('overall', {})
        logger.info("   弱标签一致率(整体): %s", overall.get('agreement'))
    if result.topic_metrics:
        logger.info("   主题建模口径: %s (%s docs), NPMI=%s",
                    result.topic_metrics.get('modeled_language'),
                    result.topic_metrics.get('n_docs_modeled'),
                    (result.topic_metrics.get('npmi') or {}).get('mean_npmi'))
    if result.segmentation_meta:
        logger.info("   分层: %s, k=%s", result.segmentation_meta.get('method'),
                    result.segmentation_meta.get('k'))
    for note in result.notes:
        logger.info("   ⚠ %s", note)

    logger.info("✅ 分析管线完成")
    return output_path, result


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

        # 质量与评测（统一管线新增）
        tm = analysis_results.get('topic_metrics')
        if tm:
            f.write("## 二.1 主题质量口径\n\n")
            f.write(f"- 建模语言子集: {tm.get('modeled_language')}（{tm.get('n_docs_modeled')} docs）\n")
            npmi = (tm.get('npmi') or {})
            f.write(f"- NPMI 连贯性: {npmi.get('mean_npmi')}；主题多样性: {tm.get('topic_diversity')}\n")
            assoc = tm.get('language_association')
            if assoc:
                f.write(f"- ⚠ 主题×语言 NMI: {assoc.get('nmi_topic_vs_language')}，"
                        f"语言簇主题数: {assoc.get('non_english_language_cluster_topics')}"
                        f"（未做语言过滤，主题可能在按语言聚类）\n")
            f.write("\n")

        se = analysis_results.get('sentiment_evaluation')
        if se:
            f.write("## 二.2 情绪输出弱标签评测（vote_up）\n\n")
            overall = se.get('overall', {})
            f.write(f"- 整体一致率: {overall.get('agreement')}（n={overall.get('n')}）\n")
            for lang, m in (se.get('by_language') or {}).items():
                f.write(f"- {lang}: 一致率 {m.get('agreement')}（n={m.get('n')}）\n")
            f.write("- 注意: vote_up 是弱标签，一致率不等于准确率\n\n")

        sm = analysis_results.get('segmentation_meta')
        if sm:
            f.write("## 二.3 玩家分层口径\n\n")
            f.write(f"- 方法: {sm.get('method')}；k={sm.get('k')}；silhouette={sm.get('silhouette')}\n")
            for name, prof in (sm.get('cluster_profiles') or {}).items():
                f.write(f"- {name}: n={prof.get('n')}（{prof.get('share')}）\n")
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
            # 统一分析管线（情绪 / 弱标签评测 / 语言感知主题 / 分层 / 质量门槛）
            analyzed_path, pipeline_result = run_analysis(config, current_file)
            analysis_results['sentiment_stats'] = pipeline_result.sentiment_stats or {}
            analysis_results['topics'] = pipeline_result.topics or {}
            analysis_results['sentiment_evaluation'] = pipeline_result.sentiment_evaluation
            analysis_results['topic_metrics'] = pipeline_result.topic_metrics
            analysis_results['segmentation_meta'] = pipeline_result.segmentation_meta
            current_file = analyzed_path

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
        logger.info("\n启动产品前端: python scripts/gamepulse_api_server.py --port 8765 + cd frontend && npm run dev")

    except Exception as e:
        logger.error(f"❌ 程序执行失败: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    main()
