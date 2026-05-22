# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Design Philosophy

**本系统采用“自然语言优先”的 Agentic AI Pattern。**

用户不需要记忆命令或参数。只要用中文表达意图，编排器就会自主选择并启动合适的 agent。

- “有什么好股票？” → Screener 自主决定 region/preset 并执行筛选
- “丰田怎么样？” → Analyst 执行估值和技术面分析
- “PF 还健康吗？” → Health Checker 给出事实和数值，Strategist 给出建议
- “最新新闻告诉我” → Researcher 通过 Grok API 获取新闻和情绪

agent 通过 `tools/` 获取数据，并自行判断、整理和输出。

## Project Overview

投资助手系统。集成 Yahoo Finance API（yfinance）、Grok API（xAI）和 Neo4j（GraphRAG），通过中文自然语言完成选股、公司分析、投资组合管理和风险评估。系统按 Codex 的 Agentic AI Pattern 运行。

## Python Environment

本项目 Python 运行环境使用 Miniconda 的 `stock-skills-2`。

Codex 在本仓库运行 Python / pytest / pip 时，不依赖 `conda activate`，必须使用 `conda run -n stock-skills-2 ...`。Codex 的命令执行可能每次启动新 shell，因此不要假设交互式 shell 已经激活环境。

```bash
conda run -n stock-skills-2 python -m pytest tests/ -q
conda run -n stock-skills-2 python tests/e2e/run_e2e.py --dry-run
conda run -n stock-skills-2 python -m pip install -r requirements.txt
```

## Commands

```bash
# 单元测试（不需要 API key/网络，约 1381 个测试）
conda run -n stock-skills-2 python -m pytest tests/ -q

# Dry-run（验证 routing.yaml 和 agent 定义一致性，< 1 秒）KIK-746
conda run -n stock-skills-2 python tests/e2e/run_e2e.py --dry-run

# Mocked E2E（pytest fixture stub tools 层，< 1 秒）KIK-747
conda run -n stock-skills-2 python -m pytest tests/e2e/test_mocked.py -q

# 真实 API E2E（实际 API 验证 agent 行为，需要 API key）
conda run -n stock-skills-2 python tests/e2e/run_e2e.py

# 开发用 worktree 设置（KIK-745，不复制个人 PF）
bash scripts/setup_worktree.sh KIK-NNN [short-desc]

# 安装依赖
conda run -n stock-skills-2 python -m pip install -r requirements.txt
```

agent 会自主调用工具，用户不需要直接执行脚本。

## Output & Visibility v1（KIK-729）

所有 agent 输出按 4 层生成。详情见 `.agents/skills/stock-skills/SKILL.md` 的 “Output & Visibility v1” 部分。

- **Layer 1**: 页眉（执行前，始终开启）`🎯 [<agent or chain>] <task>`
- **Layer 2**: 进度（仅链式执行）`✅ <agent> 完成 (X.Xs) — <摘要>`
- **Layer 3**: 正文（Pattern A/B/C）
  - A: 最小输出（1-3 行即可回答的事实查询）
  - B: 标准输出（单一 agent，固定 4 节）
  - C: 链式输出（链式 ≥2 / routine）
- **Layer 4**: 页脚（固定顺序）`📊 执行 → 💾 保存 → 🔍 Reviewer? → ➡ 下一步`

Reviewer 按 3 类启动: 🔒 自动（买卖确认、conviction 违背、周度 routine） / 🔍 按需（`[y/skip]` 提示） / ⏭ 跳过。

## Architecture

详情见 [docs/architecture.md](docs/architecture.md) 和 [docs/neo4j-schema.md](docs/neo4j-schema.md)。

```text
Orchestrator (.agents/skills/stock-skills/)
  SKILL.md           — 路由和自主控制
  routing.yaml       — agent 选择 few-shot
  orchestration.yaml — 重试和升级处理

Agents (.agents/agents/)
  screener/       — 选股和筛选
  analyst/        — 公司分析和估值评估
  researcher/     — 新闻、情绪、行业动向
  health-checker/ — 投资组合事实和数值，不做判断
  strategist/     — 投资判断和建议
  risk-assessor/  — 市场风险判定（risk-on/neutral/risk-off）
  reviewer/       — 质量、矛盾和风险检查（多 LLM）

Tools (tools/)
  yahoo_finance.py — 股价和基本面（src/data/yahoo_client/ facade）
  graphrag.py      — Neo4j 知识图谱（src/data/graph_store/ + graph_query/ facade）
  grok.py          — Grok API 搜索（src/data/grok_client/ facade）
  llm.py           — 多 LLM 调用（Gemini/GPT/Grok）
  portfolio_io.py  — PF CSV 读写（src/data/portfolio_io facade）
  notes.py         — 投资笔记读写（src/data/note_manager facade）
  watchlist.py     — 观察清单读写（JSON 直接 I/O）
  scoring.py       — 3 轴质量评分（src/data/scoring.py facade）

Data (src/data/)
  yahoo_client/   — yfinance wrapper（24h JSON cache）
  grok_client/    — Grok API (xAI) wrapper
  graph_store/    — Neo4j 写入（dual-write）
  graph_query/    — Neo4j 读取
  context/        — 自动上下文注入
  history/        — 执行历史 store
  note_manager    — 投资笔记管理
  common.py       — 通用工具（is_etf, safe_float 等）
  ticker_utils.py — ticker 推断（货币/地区映射）
  portfolio_io.py — PF CSV 读写
  scoring.py      — 3 轴质量评分（还原性、成长性、持续性）

Orchestrator (src/orchestrator/) — KIK-746
  dry_run.py      — routing.yaml + agent 定义一致性验证（不调用 API）
                    verify_routing(user_input), verify_routing_yaml_integrity()

Scripts (scripts/) — KIK-745
  setup_worktree.sh — worktree 创建 + sample fixture 复制（不复制个人 PF）

Config: .agents/agents/screener/examples.yaml (regions, themes, presets, few-shot)
Config: config/scoring.yaml (评分权重、阈值、行业配置)
Config: config/allocation.yaml (PF 目标配置、集中度约束、偏离判定)
Config: config/etf_universe.yaml (ETF 常用列表，行业/债券/商品/地区)
Config: config/llm_routing.yaml (LLM 选择、模型路由、成本定义)
Rules:  .agents/rules/ (development, workflow, testing)
Docs:   docs/ (architecture, neo4j-schema, data-models)
Tests:  tests/ (unit ~1381), tests/e2e/ (E2E)
        - run_e2e.py: 真实 API 情景执行
        - run_e2e.py --dry-run: 仅验证 routing（< 1 秒）KIK-746
        - test_mocked.py: Mocked E2E（pytest fixture stub tools）KIK-747
Fixtures: tests/fixtures/sample_portfolio.csv / sample_cash_balance.json
          (KIK-745，通用测试标的，worktree 集成测试替代个人 PF)
```

## Quant Research Extension（WIP）

量化功能追加正在进行中。进度和任务追踪以 checklist 为准，两份方案文档仅在遇到设计决策问题时才读取。

### 高效工作流（省 token）

```text
1. 读取 checklist 顶部 20 行 → 获取当前状态和 Phase
2. 读取 checklist 中当前 Phase 的未完成条目（~30-40 行）
3. 按条目编码 → 完成一项 → 勾选一项
4. 每 Phase 结束跑 pytest 确认不破坏现有测试
5. 方案文档（Downloads/stock_skills_2_quant_*_plan.md）仅在设计问题/阻塞时读取
```

### 文件位置

| 文件 | 路径 | 何时读 |
|---|---|---|
| **Checklist（主）** | `～/Documents/Codex Project/stock_skills_2-main/docs/plans/stock_skills_2_quant_implementation_checklist_selfcontained.md` | 每次编码前读取当前 Phase |
| 方案设计 | `～/Documents/Codex Project/stock_skills_2-main/docs/plans/stock_skills_2_quant_extension_plan.md` | 仅设计问题/阻塞时 |
| 实装计划 | `～/Documents/Codex Project/stock_skills_2-main/docs/plans/stock_skills_2_quant_implementation_plan.md` | 仅实现细节不确定时 |

### 关键规则

- `data/quant/**` 本地数据产物，gitignored；仅 `tests/fixtures/quant/` 可提交
- 量化 CLI 统一用 `conda run -n stock-skills-2 python tools/quant_*.py ...`
- P0 不依赖 Qlib/Alphalens；core 依赖仅 pandas/numpy/pyarrow/matplotlib/pyyaml
- 量化 agent 定义以 `.agents/agents/quant-researcher/` 为 canonical，同步 `.claude/agents/quant-researcher/` mirror
- 每个 Phase 结束必须：`conda run -n stock-skills-2 python -m pytest tests/ -q` 全量通过

## Post-Implementation Rule

**功能实现后必须检查并更新以下内容。**

- agent 定义: 对应 `agent.md` + `examples.yaml`
- 路由: `routing.yaml` 的 triggers/examples
- Codex/Claude 兼容: `.agents/` 是 Codex canonical，`.claude/` 是 Claude Code mirror，二者需要同步
- 文档: `AGENTS.md`、`README.md`、`docs/architecture.md`
- 测试: `conda run -n stock-skills-2 python -m pytest tests/ -q` 全部通过
