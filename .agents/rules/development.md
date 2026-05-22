# 开发规则

## 语言和依赖

- Python 3.10+
- 主要依赖: yfinance, pyyaml, numpy, pandas, pytest, requests, python-dotenv
- 使用 Grok API 时设置 `XAI_API_KEY` 环境变量；未设置时仍应 graceful degradation
- 使用 Gemini API 时设置 `GEMINI_API_KEY` 环境变量；未设置时仍应 graceful degradation
- 使用 OpenAI API 时设置 `OPENAI_API_KEY` 环境变量；未设置时仍应 graceful degradation
- Neo4j 写入深度由 `NEO4J_MODE` 控制: `off` / `summary` / `full`。默认在可连接时使用 `full`
- Neo4j 连接失败默认静默。需要诊断时设置 `NEO4J_DEBUG=1`(或 `true` / `yes`)，首下一步失败时只向 stderr 输出一行简短信息(KIK-749)
- TEI 向量搜索由 `TEI_URL` 控制，默认 `http://localhost:8081`。TEI 未启动时跳过向量搜索
- Linear 集成通过 `LINEAR_ENABLED=on` 启用，默认 off

## 编码约定

### 工具层 (`tools/`)

- 只做薄 facade，原则上 re-export `src/data/` 的函数
- 不放投资判断逻辑
- 用 `try/except ImportError` 设置 `HAS_*` 标志并保持 graceful degradation

### Agent 层 (`.agents/agents/`)

- `agent.md`: 角色、判断流程、使用工具、输出方针
- `examples.yaml`: few-shot(intent -> steps -> reasoning)
- 由 agent 负责判断、计算和输出整理

### 数据层 (`src/data/`)

- 数据获取必须通过 `src/data/yahoo_client/`，不需要直接调用 yfinance
- yahoo_client 使用模块函数，不使用类封装
- 股息收益率归一化: `_normalize_ratio()` 在值 > 1 时除以 100 转为比例
- 数据模型定义参见 `docs/data-models.md`

### 共通工具 (`src/data/`)

- common.py, ticker_utils.py, portfolio_io.py 放在 `src/data/`
- 判断逻辑属于 agent；`src/data/` 只做纯数据操作

## 测试

- 本仓库 Python/pytest 必须使用 conda 环境: `conda run -n stock-skills-2 python -m pytest tests/ -q`
- `tests/conftest.py` 提供共通 fixtures: `stock_info_data`, `stock_detail_data`, `price_history_df`, `mock_yahoo_client`
- `tests/conftest.py` 的 autouse `_block_external_io` fixture 会自动 mock Neo4j / TEI / Grok
- `tests/fixtures/` 保存 JSON/CSV 测试数据(以 Toyota 7203.T 为基础)
- 测试文件按功能放在 `tests/core/`, `tests/data/`, `tests/e2e/`

## Git 工作流

开发流程(worktree 创建 -> 设计 -> 实装 -> 测试 -> 审查 -> 集成测试 -> 合并)参见 [workflow.md](workflow.md)。

- 分支名: `feature/kik-{NNN}-{short-desc}`
- worktree: `~/stock-skills-kik{NNN}`

## 文件结构指南

### 大小上限

- 生产代码: 建议 400 行以内，超过 500 行考虑拆分
- 测试: 建议 600 行以内
- Agent 定义: `agent.md` 保持简洁，`examples.yaml` 约 20 个例子

### 新模块位置

- 工具 facade -> `tools/`(只做数据操作，不做判断)
- Agent 定义 -> `.agents/agents/<name>/`(`agent.md` + `examples.yaml`)
- 数据获取/保存 -> `src/data/{yahoo_client,graph_store,graph_query,history,context}/`
- 共通工具 -> `src/data/`(common.py, ticker_utils.py, portfolio_io.py)
- 测试 -> `tests/{core,data,e2e}/`，尽量与 `src/` 结构对应

## 文档结构

- `docs/architecture.md`: 系统架构(Agentic AI Pattern、Mermaid 图)
- `docs/neo4j-schema.md`: Neo4j schema reference(node 类型、relationship)
- `docs/data-models.md`: stock_info / stock_detail dict schema

## 自动上下文注入

- `src/data/context/`: 上下文获取引擎(symbol 检出 + graph 状态判定)
- Agent 通过 `tools/graphrag.py` 的 `get_context()` 获取上下文
- Neo4j 未连接时必须 graceful degradation

## 工具定义

- `config/tools.yaml`: 统一管理所有工具的函数名、角色和使用时机
- `tools/` 增删或修改函数时，必须同步更新 `config/tools.yaml`
- `agent.md` 和 `SKILL.md` 不需要硬编码完整工具清单，应引用 `config/tools.yaml`

## 外部 LLM 调用

- 不需要硬编码 `call_llm()` 的模型名；`config/llm_routing.yaml` 是 Single Source of Truth

## gitignore 对象

- `data/cache/`: 按 symbol 保存的 JSON cache(TTL 24 小时)
- `data/watchlists/`: watchlist 数据
- `data/screening_results/`: 筛选结果
- `data/notes/`: 投资笔记数据
- 组合数据: `data/portfolio.csv`
