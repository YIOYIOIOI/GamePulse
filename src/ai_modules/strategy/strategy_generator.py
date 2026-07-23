"""
AI 运营策略生成模块
基于玩家分析结果生成运营优化策略
"""

import pandas as pd
import logging
from typing import List, Dict, Optional
from pathlib import Path
import os
import json
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

logger = logging.getLogger(__name__)


class StrategyGenerator:
    """运营策略生成器"""

    def __init__(self, config: dict, client=None):
        self.config = config
        # 默认走 OpenAI 兼容 REST（requests 直调，支持 OpenAI/Ark/DeepSeek 等任意兼容网关）
        self.provider = config.get('llm', {}).get('provider', 'openai_compatible')

        if client is not None:
            # 依赖注入：测试可传 MockLLMClient，离线验证整条链路
            self.client = client
            self.model = getattr(client, 'model', 'injected')
        else:
            self._init_llm_client()

    def _init_llm_client(self):
        """初始化 LLM 客户端"""
        if self.provider == 'openai_compatible':
            from src.ai_modules.llm_client import from_env

            self.client = from_env(self.config)
            self.model = getattr(self.client, 'model', None)

        elif self.provider == 'openai':
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

    def generate_strategies(self,
                          analysis_results: Dict,
                          game_info: Optional[Dict] = None) -> str:
        """
        生成运营策略

        Args:
            analysis_results: 分析结果（包含情绪、主题、群体等信息）
            game_info: 游戏基本信息

        Returns:
            策略建议文本
        """
        if not self.client:
            logger.error("LLM 客户端未初始化")
            return "错误：LLM 客户端未初始化"

        logger.info("开始生成运营策略")

        # 构建策略生成 prompt
        prompt = self._build_strategy_prompt(analysis_results, game_info)

        # 调用 LLM
        try:
            strategies = self._call_llm(prompt)
            logger.info("策略生成完成")
            return strategies
        except Exception as e:
            logger.error(f"策略生成失败: {e}")
            return f"错误：{e}"

    def _build_strategy_prompt(self,
                              analysis_results: Dict,
                              game_info: Optional[Dict] = None) -> str:
        """构建策略生成 prompt"""

        game_name = game_info.get('name', '该游戏') if game_info else '该游戏'

        # 情绪统计
        sentiment_stats = analysis_results.get('sentiment_stats', {})
        sentiment_text = self._format_sentiment_stats(sentiment_stats)

        # 主题分析
        topics = analysis_results.get('topics', {})
        topics_text = self._format_topics(topics)

        # 玩家群体分析
        player_segments = analysis_results.get('player_segments', {})
        segments_text = self._format_player_segments(player_segments)

        # 主要问题
        negative_summary = analysis_results.get('negative_summary', '')

        # 版本影响
        version_impact = analysis_results.get('version_impact', '')

        prompt = f"""
你是一位资深的游戏运营策略专家。请基于以下玩家反馈分析结果，为 {game_name} 生成一份详细的运营优化策略。

## 一、玩家情绪分析
{sentiment_text}

## 二、主要讨论主题
{topics_text}

## 三、玩家群体分析
{segments_text}

## 四、主要负面反馈
{negative_summary}

## 五、版本更新影响
{version_impact}

请从以下几个维度生成运营策略：

### 1. 产品优化策略
- 需要优先修复的问题（按优先级排序）
- 功能改进建议
- 用户体验优化方向

### 2. 玩家运营策略
- 针对不同玩家群体的差异化运营策略
- 玩家留存提升方案
- 玩家活跃度提升方案

### 3. 内容更新策略
- 下个版本应该重点关注的内容
- 玩家期待的新功能
- 内容更新节奏建议

### 4. 社区管理策略
- 玩家沟通策略
- 负面舆情应对方案
- 社区活动建议

### 5. 数据监控建议
- 需要重点监控的指标
- 预警机制建议

请为每个策略提供：
- 具体的执行方案
- 预期效果
- 优先级评估（高/中/低）
- 实施难度评估（易/中/难）

输出格式要求：
- 使用中文
- 条理清晰，分点列出
- 每个策略要具体可执行
- 标注优先级和实施难度
"""

        return prompt

    def _format_sentiment_stats(self, sentiment_stats: Dict) -> str:
        """格式化情绪统计"""
        if not sentiment_stats:
            return "暂无情绪统计数据"

        distribution = sentiment_stats.get('sentiment_distribution', {})
        percentage = sentiment_stats.get('sentiment_percentage', {})

        lines = []
        for sentiment in ['positive', 'negative', 'neutral']:
            count = distribution.get(sentiment, 0)
            pct = percentage.get(sentiment, 0)
            lines.append(f"- {sentiment.capitalize()}: {count} ({pct:.1%})")

        return "\n".join(lines)

    def _format_topics(self, topics: Dict) -> str:
        """格式化主题信息"""
        if not topics:
            return "暂无主题分析数据"

        lines = []
        for topic_id, words in list(topics.items())[:10]:
            lines.append(f"主题 {topic_id}: {', '.join(words[:5])}")

        return "\n".join(lines)

    def _format_player_segments(self, player_segments: Dict) -> str:
        """格式化玩家群体信息"""
        if not player_segments:
            return "暂无玩家群体分析数据"

        lines = []
        for segment, info in player_segments.items():
            count = info.get('count', 0)
            top_concerns = info.get('top_concerns', [])
            lines.append(f"\n{segment}:")
            lines.append(f"  数量: {count}")
            if top_concerns:
                lines.append(f"  主要关注: {', '.join(top_concerns[:3])}")

        return "\n".join(lines)

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM API"""

        temperature = self.config.get('llm', {}).get(self.provider, {}).get('temperature', 0.7)
        max_tokens = self.config.get('llm', {}).get(self.provider, {}).get('max_tokens', 3000)

        if self.provider == 'openai_compatible' or hasattr(self.client, 'chat'):
            return self.client.chat(
                user=prompt,
                system="你是一位资深的游戏运营策略专家。",
                temperature=temperature,
                max_tokens=max_tokens,
            )

        if self.provider == 'openai':
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一位资深的游戏运营策略专家。"},
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

    def generate_quick_actions(self, analysis_results: Dict) -> List[Dict]:
        """
        生成快速行动建议

        Args:
            analysis_results: 分析结果

        Returns:
            行动建议列表
        """
        if not self.client:
            logger.error("LLM 客户端未初始化")
            return []

        prompt = f"""
基于以下玩家反馈分析结果，列出 5-10 个可以立即采取的行动建议。

分析结果摘要：
{json.dumps(analysis_results, ensure_ascii=False, indent=2)[:2000]}

请为每个行动提供：
1. 行动名称（简短）
2. 行动描述（具体可执行）
3. 预期效果
4. 优先级（高/中/低）
5. 实施难度（易/中/难）
6. 预计时间（天数）

以 JSON 格式输出，例如：
[
  {{
    "name": "修复登录BUG",
    "description": "立即修复导致玩家无法登录的严重BUG",
    "expected_effect": "显著降低玩家流失率",
    "priority": "高",
    "difficulty": "中",
    "estimated_days": 3
  }}
]
"""

        try:
            response = self._call_llm(prompt)

            # 尝试解析 JSON
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                actions = json.loads(json_match.group())
                return actions
            else:
                logger.warning("无法解析快速行动建议")
                return []

        except Exception as e:
            logger.error(f"快速行动建议生成失败: {e}")
            return []

    def generate_roadmap(self, analysis_results: Dict, timeframe: str = '3个月') -> str:
        """
        生成产品路线图建议

        Args:
            analysis_results: 分析结果
            timeframe: 时间范围

        Returns:
            路线图文本
        """
        if not self.client:
            logger.error("LLM 客户端未初始化")
            return "错误：LLM 客户端未初始化"

        prompt = f"""
基于玩家反馈分析结果，为游戏规划一个 {timeframe} 的产品路线图。

分析结果摘要：
{json.dumps(analysis_results, ensure_ascii=False, indent=2)[:2000]}

请按时间顺序规划：

第一个月：
- 紧急问题修复
- 快速改进

第二个月：
- 功能优化
- 内容更新

第三个月：
- 大版本更新
- 新功能上线

每个阶段请包括：
1. 主要工作内容
2. 具体任务列表
3. 预期目标
4. 成功指标

输出中文，格式清晰。
"""

        try:
            roadmap = self._call_llm(prompt)
            logger.info("产品路线图生成完成")
            return roadmap
        except Exception as e:
            logger.error(f"产品路线图生成失败: {e}")
            return f"错误：{e}"


def main():
    """命令行入口"""
    import argparse
    import yaml

    parser = argparse.ArgumentParser(description='AI 策略生成工具')
    parser.add_argument('--analysis-results', type=str, required=True, help='分析结果文件路径')
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

    # 读取分析结果
    logger.info(f"读取分析结果: {args.analysis_results}")
    with open(args.analysis_results, 'r', encoding='utf-8') as f:
        analysis_results = json.load(f)

    # 创建策略生成器
    generator = StrategyGenerator(config)

    # 生成策略
    strategies = generator.generate_strategies(analysis_results)

    # 生成快速行动建议
    quick_actions = generator.generate_quick_actions(analysis_results)

    # 生成产品路线图
    roadmap = generator.generate_roadmap(analysis_results)

    # 保存结果
    output_name = args.output or "operation_strategies"
    output_dir = Path('data/results')
    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存策略文本
    with open(output_dir / f"{output_name}.txt", 'w', encoding='utf-8') as f:
        f.write("# 运营策略建议\n\n")
        f.write(strategies)
        f.write("\n\n# 快速行动建议\n\n")
        f.write(json.dumps(quick_actions, ensure_ascii=False, indent=2))
        f.write("\n\n# 产品路线图\n\n")
        f.write(roadmap)

    # 保存 JSON 格式
    with open(output_dir / f"{output_name}.json", 'w', encoding='utf-8') as f:
        json.dump({
            'strategies': strategies,
            'quick_actions': quick_actions,
            'roadmap': roadmap
        }, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 策略生成完成！结果已保存到: {output_dir / output_name}")


if __name__ == '__main__':
    main()
