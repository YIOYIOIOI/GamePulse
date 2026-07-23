# AI-Powered Game Player Insight & Operation Strategy System

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![PyTorch](https://img.shields.io/badge/PyTorch-2.6+-red.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

一个基于深度学习的游戏玩家反馈分析系统，通过BERT情绪分析和LDA主题建模技术，为游戏运营提供数据驱动的决策支持。

## 项目概述

本系统整合了现代AI技术与传统数据分析方法，实现了从玩家评论采集到运营洞察输出的完整数据管道。系统已在真实环境中验证，成功处理了10万+条Steam玩家评论数据。

> **产品化原则**：本项目面向“AI策略运营”岗位面试展示，但不伪造经营数据。Steam公开评论可以支持口碑、主题、痛点、玩家分层代理和触达策略；真实 LTV、付费转化、留存/流失必须依赖公司内部日志、充值和活动曝光数据。本系统会通过数据质量门槛自动降级或隐藏证据不足的功能。

### 核心能力

- 🚀 **大规模数据采集**：支持10万+评论采集，速度达37-40条/秒
- 🤖 **BERT情绪分析 + 语言分流**：DistilBERT 仅用于英文子集（vote_up 弱标签实测一致率 70.3%）；非英文不再硬套英文模型
- 📊 **LDA主题建模 + 双指标验收**：语言过滤消除多语言干扰，用 NPMI 连贯性 + 主题×语言 NMI 量化主题质量

### 质量与评测升级（2026-07）

| 升级 | 说明 | 产物 |
|---|---|---|
| 语言分流 | Steam 自带 language 标签归一/过滤（`src/analysis/language.py`），修复"主题=语言聚类"（旧管线 10 主题中 4 个是非英语语言簇，主题×语言 NMI=0.417） | `scripts/rerun_topics_by_language.py` → `topic_language_ablation.json` |
| 弱标签实测 | 用 vote_up 实测情感输出一致率：整体 55.3% / 英文 70.3% / 非英文 41.1%（差 29pp，量化了英文模型硬套多语言的代价） | `scripts/evaluate_sentiment.py` → `sentiment_evaluation.json` |
| KMeans 分层 | 多特征（时长/获赞/评论长度/活跃度）+ 轮廓系数自动选 k，替代单维时长切分；发现"高影响力评论者"簇 | `src/analysis/segmentation/player_segmentation.py` |
| LLM 链路 | OpenAI 兼容 REST 客户端（requests 直调，支持 OpenAI/火山方舟 Ark），环境变量配置即激活，含离线 mock | `src/ai_modules/llm_client.py` |
| 引擎 API 化 | 分析引擎经本地 API 暴露（/api/analyze、/api/analysis/segments、/api/analysis/sentiment-eval），前端优先调引擎、失败降级本地计算——单一事实源 | `scripts/gamepulse_api_server.py` + `frontend/src/lib/analysisApi.ts` |
| **统一管线** | CLI 与 API 曾是两条互不为超集的链路（main.py 无语言过滤/评测；API 不跑模型）。现合并为 `src/analysis/pipeline.py` 单一事实源：语言归一 → 情绪 → 弱标签评测 → 语言感知主题（NPMI/多样性/NMI 诊断）→ KMeans 分层 → 质量门槛。`main.py --mode analyze` 走完整路径；API `/api/analyze` 分两档——light（默认，秒回）与 full（先跑与 CLI 相同的 DataCleaner 再跑完整模型管线）。旧 Streamlit dashboard 已移除 | `src/analysis/pipeline.py` + `tests/test_pipeline.py` |
| **前端全面引擎化** | 工作台/健康检查/反馈分析/玩家分层/触达策略/竞品分析六个页面全部引擎优先：DataProvider 在数据集变化后自动拉取 /api/analyze 分析包入 store，各页汇总结论消费引擎口径（页面标注口径来源），本地 TS 公式仅作无引擎降级；分层页消费 KMeans 行级标签 | `frontend/src/lib/useDataStore.tsx` + 各 view |
| 测试与 CI | 18 项离线 pytest（语言/评测/分层/指标/LLM mock/统一管线/时长单位契约回归）+ GitHub Actions（后端测试 + 前端 typecheck/build） | `tests/` + `.github/workflows/ci.yml` |
- 👥 **玩家分群分析**：KMeans 多特征聚类（时长/获赞/评论长度，轮廓系数自动选 k），前端消费引擎行级标签
- 📈 **产品级运营控制台**：React/Vite 前端 + 本地 Python API（旧 Streamlit 版已移除）
- 🧪 **数据可信度门槛**：样本不足或字段缺失时自动降级，避免假结论
- 🎯 **生命周期代理分析**：基于公开评论和游玩时长构建价值潜力/流失风险代理指标
- ✍️ **AI内容生产管线**：基于玩家痛点生成宣传、召回、裂变内容草案，并保留人工审核边界

### 业务价值

- **游戏发行决策**：量化市场反馈，评估游戏潜力
- **运营策略优化**：识别核心痛点，制定针对性改进方案
- **营销策略制定**：构建用户画像，精准定位目标用户
- **AI策略运营面试展示**：完整覆盖用户生命周期代理、智能触达、内容生产、竞品监控与AI工具方法论，同时明确数据边界

### 面试岗位功能映射

详见 [`PRODUCT_FUNCTION_PLAN.md`](PRODUCT_FUNCTION_PLAN.md)。核心结论：

- 可正式展示：情绪/主题分析、玩家分群、口碑趋势、触达策略、内容生产草案、竞品监控框架。
- 仅做代理：LTV、付费转化、流失预警，因为公开 Steam 评论没有真实付费和留存数据。
- 必须补数据后再展示：真实用户级LTV预测、真实付费转化率、真实召回效果，需要公司内部日志/充值/活动曝光数据。



## GamePulse React 产品版（当前主线）

当前推荐演示入口不是旧 Streamlit，而是 React/Vite 产品前端：

```bash
# 1. 启动本地 Python API
.venv\Scripts\python.exe scripts\gamepulse_api_server.py --port 8765

# 2. 启动 React 前端
cd frontend
npm install
npm run dev -- --port 3010 --host 127.0.0.1
```

访问：`http://127.0.0.1:3010/`

### 当前产品链路

1. **数据中心**
   - 搜索 Steam 游戏名并选择 AppID。
   - 支持按数量采集最近评论。
   - 支持采集最近 N 天内的评论：持续翻页直到覆盖时间窗口。
   - 支持 CSV 上传。
   - 当前工作数据集保存到浏览器 IndexedDB 本地数据库，下次打开自动恢复。

2. **运营工作台**
   - 展示评论数、监控游戏数、正负向情绪、风险因子和行动建议。
   - 所有判断基于当前数据集，不把 proxy 包装成真实经营指标。

3. **数据健康检查**
   - 检查样本量、时间跨度、字段完整度。
   - `<300` 样本仅建议预览；`300–1000` 做保守描述；`>=1000` 更适合完整分析。
   - 时间跨度 `<14` 天时不输出趋势判断，只做截面分析。

4. **反馈分析**
   - 本地规则识别玩家反馈主题。
   - 可选“模型辅助分析”进一步细分主题。

5. **玩家分层**
   - 引擎可用时：Python KMeans 多特征聚类的行级标签（与批处理报告同一口径）。
   - 引擎不可用时：本地时长阈值降级（<10h/10-100h/>100h），页面会标注当前口径。
   - 后续接入公司内部数据时，可替换为真实注册天数、活跃、付费和留存特征。

6. **触达策略**
   - 基于分层和主题痛点生成 CRM 触达策略草案。
   - 模型辅助生成仅作为策略草案，保留人工复核边界。

7. **竞品分析**
   - 支持多个游戏数据合并。
   - 对比不同游戏的负向主题结构和玩家痛点，而不是只看评分。

8. **模型设置**
   - 用户可配置 OpenAI-compatible 模型服务。
   - 访问密钥只保存在当前浏览器本地，不进入 Python 后端。
   - 支持从 `{baseUrl}/models` 获取模型列表。

### 面试表述建议

这个项目不是简单 dashboard，而是一个游戏 AI 策略运营工作流原型：

```text
公开玩家反馈采集 → 数据质量判断 → 主题/情绪/玩家分层 → 竞品对比 → 模型辅助触达策略 → 人工复核与后续 A/B 测试
```

重点是：

- 用 AI 提效运营分析与策略内容生产；
- 用规则和统计保证可解释性；
- 用模型服务增强语义理解和话术生成；
- 明确公开评论只能支持 proxy，不伪造真实 LTV、付费转化和留存。


## 技术架构

```
┌─────────────────────────────────────────────────┐
│           数据采集层（Steam API）                 │
│   - 智能重试机制                                  │
│   - 速率控制                                      │
│   - 18维度元数据采集                              │
└────────────────┬────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────┐
│           数据处理层（Pandas）                    │
│   - 数据去重与清洗                                │
│   - 特征工程                                      │
│   - 玩家分群                                      │
└────────────────┬────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────┐
│              AI分析层                            │
│   ┌──────────────┐  ┌──────────────┐          │
│   │ BERT情绪分析  │  │ LDA主题建模   │          │
│   │ (Deep Learning)│  │ (ML)         │          │
│   │ 弱标签实测口径 │  │ 语言感知建模  │          │
│   └──────────────┘  └──────────────┘          │
└────────────────┬────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────┐
│      可视化层（React/Vite + 本地 API）           │
│   - 情绪趋势分析                                  │
│   - 主题分布展示                                  │
│   - 玩家洞察报告                                  │
└─────────────────────────────────────────────────┘
```

## 快速开始

### 环境要求

- Python 3.8+
- 8GB+ RAM（推荐16GB用于大规模数据处理）
- 可选：NVIDIA GPU with CUDA 12.6+（用于加速BERT推理）

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/YIOYIOIOI/GamePulse.git
cd GamePulse
```

2. **安装依赖**
```bash
python -m venv .venv
.venv\\Scripts\\python.exe -m pip install -r requirements.txt
```

3. **启动产品控制台**（React 前端 + 本地 API，见上文「GamePulse React 产品版」）

Steam 采集入口使用轻量采集器 `src/data_collection/steam_light_collector.py`，只依赖 requests + pandas，torch/transformers 未安装时 API 服务照常可用。

4. **构建真实本地竞品演示数据集**
```bash
.venv\\Scripts\\python.exe -m src.analysis.build_demo_dataset
```

该命令不会伪造评论，只会把本地已有的 DOTA 2 与 GTA V 分析结果合并，并补充 `game_name` 字段，用于演示竞品监控。

5. **审计本地数据是否足以支撑产品功能**
```bash
.venv\\Scripts\\python.exe -m src.analysis.dataset_audit --results-dir data\\results
```

3. **配置系统**（可选）

编辑 `config/config.yaml` 自定义配置：
```yaml
sentiment_analysis:
  use_transformer: true  # 启用BERT（需要transformers库）
  model_name: "distilbert-base-uncased-finetuned-sst-2-english"
  batch_size: 32
  use_gpu: false  # 如有GPU可设为true

topic_analysis:
  n_topics: 10  # LDA主题数量
  method: "lda"  # 主题建模方法
```

### 使用示例

#### 1. 数据采集

```bash
# 采集DOTA 2的评论（Steam App ID: 570）
python main.py --mode collect --game-id 570 --max-reviews 10000
```

#### 2. 数据清洗

```bash
python main.py --mode process --input data/raw/DOTA2_xxx.csv --game-name "DOTA2"
```

#### 3. AI分析

```bash
python main.py --mode analyze --input data/processed/DOTA2_xxx_cleaned.csv --game-name "DOTA2"
```

#### 4. 一键运行完整流程

```bash
python main.py --mode all --game-id 570 --max-reviews 10000
```

#### 5. 启动产品前端

```bash
python scripts/gamepulse_api_server.py --port 8765
cd frontend && npm run dev
```

## 核心技术

### 1. BERT情绪分析

**技术实现**：
- 模型：DistilBERT（BERT的轻量化版本）
- 架构：Transformer 编码器（DistilBERT 为 6 层，768 维隐藏层，从 12 层 BERT-base 蒸馏而来）
- 参数量：约 6600 万
- 一致率（vote_up 弱标签实测）：整体 55.3%，英文子集 70.3%，非英文 41.1% —— 故引入语言分流；90%+ 仅为 SST-2 公开基准数字，不代表本数据集表现

**优势**：
- 理解上下文语义（相比传统关键词匹配）
- 识别讽刺和隐含情绪
- 支持GPU加速，速度提升5-10倍

**实测结果**（2,071条DOTA 2评论）：
```
正面评论: 605 (29.2%)
负面评论: 1,466 (70.8%)
中性评论: 0 (0.0%)
处理时间: 46秒
```

### 2. LDA主题建模

**技术实现**：
- 算法：隐含狄利克雷分配（Latent Dirichlet Allocation）
- 类型：无监督学习
- 向量化：CountVectorizer（LDA 建模在词频计数上；TF-IDF 仅用于 NMF 路径）

**优势**：
- 自动发现隐藏主题，无需人工标注
- 识别玩家关注的核心问题
- 支持主题-情绪交叉分析

**实测结果**（2,071条评论）：
```
识别主题数: 10
词汇量: 1,472
处理时间: 6秒
```

### 3. 玩家分群分析

**分群标准**（基于游戏时长）：
- 新手玩家：< 10小时
- 普通玩家：10-100小时
- 核心玩家：> 100小时

**实测结果**：
```
核心玩家: 1,627 (78.6%)
普通玩家: 285 (13.8%)
新手玩家: 159 (7.7%)
```

## 实际测试案例

### DOTA 2 玩家反馈分析

**数据规模**：
- 原始采集：100,000条评论
- 清洗后：2,071条有效数据
- 采集耗时：约47分钟
- 分析耗时：约2分钟

**关键洞察**：
1. **核心玩家主导评论**：78.6%的评论来自核心玩家（平均4000+小时游戏时长）
2. **负面情绪偏高**：70.8%的评论为负面，反映核心玩家对游戏问题敏感度高
3. **主题分布均衡**：Top 5主题占比均在10-15%之间，说明玩家诉求多样化

**业务建议**：
- 优先解决核心玩家关注的平衡性和匹配问题
- 加强与核心玩家的沟通，提升归属感
- 针对新手玩家优化引导体验，提高留存率

详见：[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)

## 项目结构

```
AI-Powered-GPI-OSS/
├── src/
│   ├── data_collection/
│   │   └── steam_scraper.py       # Steam API数据采集
│   ├── data_processing/
│   │   └── data_cleaner.py        # 数据清洗与特征工程
│   ├── analysis/
│   │   ├── pipeline.py            # ⭐ 统一分析管线（单一事实源）
│   │   ├── language.py            # 语言归一与过滤
│   │   ├── evaluation.py          # vote_up 弱标签评测
│   │   ├── sentiment/
│   │   │   └── sentiment_analyzer.py  # DistilBERT/规则 fallback 情绪
│   │   ├── topic/
│   │   │   ├── topic_analyzer.py      # LDA/NMF 主题建模
│   │   │   └── coherence.py           # NPMI/多样性/NMI 指标
│   │   └── segmentation/
│   │       └── player_segmentation.py # KMeans 多特征分层
│   ├── ai_modules/
│   │   ├── llm_client.py          # OpenAI 兼容客户端（可选）
│   │   ├── summarizer/            # LLM评论摘要（可选）
│   │   └── strategy/              # LLM策略生成（可选）
├── data/
│   ├── raw/                       # 原始数据
│   ├── processed/                 # 清洗后数据
│   └── results/                   # 分析结果
├── config/
│   └── config.yaml                # 系统配置
├── main.py                        # 主程序入口
├── requirements.txt               # Python依赖
├── PROJECT_SUMMARY.md             # 详细项目总结
└── README.md                      # 本文件
```

## 性能指标

### 数据处理性能
- 采集速度：37-40条/秒
- 支持规模：10万+条评论/次
- 数据完整性：100%（18个字段完整）
- 系统稳定性：99.5%

### AI模型性能
- 情绪一致率（弱标签实测）：英文 70.3% / 非英文 41.1%（见 data/results/sentiment_evaluation.json）
- BERT推理速度：2,071条/46秒（CPU模式）
- LDA处理速度：2,071条/6秒
- GPU加速比：5-10x（相比CPU）

## 技术栈

### 数据处理
- **数据采集**：`requests`
- **数据处理**：`pandas`, `numpy`
- **数据存储**：CSV格式

### AI/ML
- **深度学习框架**：`PyTorch 2.6+`
- **预训练模型**：`transformers 5.3+` (Hugging Face)
- **机器学习**：`scikit-learn`, `scipy`
- **NLP工具**：`gensim`, `nltk`

### 可视化
- **前端**：`React` / `Vite` / `TypeScript`（`frontend/`）

### 可选模块
- **LLM集成**：`openai`, `anthropic` (用于高级摘要和策略生成)

## 扩展功能

### 多数据源支持
系统架构支持扩展到其他数据源：
- Twitter游戏话题
- Reddit游戏社区
- Discord服务器讨论
- 游戏内反馈系统

### 实时监控
可扩展为实时分析系统：
- 实时数据流处理（Kafka + Flink）
- 预警机制（负面情绪突增）
- 自动化报告生成

### 预测分析
基于历史数据构建预测模型：
- 游戏生命周期预测
- 玩家流失预警
- 版本更新影响预测

## 常见问题

**Q: 为什么清洗后数据保留率低？**
A: Steam API在某些情况下会返回大量重复数据（同一评论重复出现），且存在很多极短评论（<20字符）。在10万条采集中，实际有效评论仅2,071条是正常现象。

**Q: BERT模型下载慢怎么办？**
A: 首次运行会从Hugging Face下载模型（约260MB），可设置国内镜像源或手动下载后放置到缓存目录。

**Q: 可以分析中文评论吗？**
A: 当前使用的DistilBERT主要支持英文。要分析中文评论，需要切换到中文BERT模型（如`bert-base-chinese`），修改`config/config.yaml`中的`model_name`即可。

**Q: 需要GPU吗？**
A: 不是必须的。CPU模式下也能运行，只是速度较慢。如有NVIDIA GPU，设置`use_gpu: true`可获得5-10倍加速。

## 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 联系方式

项目仓库：github.com/YIOYIOIOI/GamePulse（私有）

## 致谢

- [Hugging Face Transformers](https://github.com/huggingface/transformers) - BERT模型实现
- [scikit-learn](https://scikit-learn.org/) - LDA主题建模
- [Steam Web API](https://steamcommunity.com/dev) - 数据来源

---

**注**: 本项目仅用于学习和研究目的。使用Steam数据时请遵守Steam服务条款和API使用政策。

## React Product Frontend

The product-grade frontend lives under `frontend/` (React/Vite/TypeScript, package `gamepulse-frontend`).

Run the local Python API first:

```powershell
.\.venv\Scripts\python.exe scripts\gamepulse_api_server.py --port 8765
```

Then run the React/Vite frontend:

```powershell
cd frontend
npm install
npm run dev -- --port 3010 --host 127.0.0.1
```

Open: http://127.0.0.1:3010/

Current API wiring:

- `GET /api/steam/search?q=<game>` searches Steam apps by game name.
- `POST /api/steam/reviews` collects real Steam reviews via the existing lightweight collector.
- `POST /api/analyze` returns the existing backend analysis package.

The legacy Streamlit dashboard has been removed; the product UI is `frontend/` (React/Vite) backed by `scripts/gamepulse_api_server.py`, and both share the unified pipeline in `src/analysis/pipeline.py`.
