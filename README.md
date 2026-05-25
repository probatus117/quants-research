# stock-skills v2

> **Version 2** — 基于 [stock_skills v1](https://github.com/okikusan-public/stock_skills)，按 Agentic AI Pattern 全面重构。
> v1 中脚本承载了大量规则和判断逻辑；v2 废除脚本驱动方式，改为由 AI 自主选择工具、决定参数、执行分析并触发审查。

这是一个投资助手系统。用户只需要用中文自然语言表达意图，系统就会自动完成选股、公司分析、投资组合管理和风险评估。

## 系统要求

- **Codex or [Claude Code](https://claude.ai/code)** — 读取 `SKILL.md` 作为编排器，从中文自然语言中自主选择并执行 agent 角色
- **Python 3.10+** — 运行 `tools/` 中的数据工具
- **LLM/API keys（可选）** — Grok/Gemini/OpenAI/Neo4j 未设置时会 graceful degradation

## 设置

```bash
pip install -r requirements.txt
```

依赖: yfinance, pyyaml, numpy, pandas, requests, python-dotenv

### 环境变量

```bash
# Grok API（X 情绪分析，可选）
export XAI_API_KEY=xai-xxxxxxxxxxxxx

# Gemini API（多 LLM 审查，可选）
export GEMINI_API_KEY=AIzaSy...

# OpenAI API（多 LLM 审查，可选）
export OPENAI_API_KEY=sk-proj-...

# Neo4j（GraphRAG，可选）
export NEO4J_URI=bolt://localhost:7688
export NEO4J_MODE=full  # off/summary/full
export NEO4J_DEBUG=1    # 连接失败时仅首次向 stderr 输出诊断信息；默认静默
```

以上全部可选。未设置时使用默认值运行。

## 用法

只需用中文自然语言提问:

```text
「有什么好股票？」      → Screener 自主筛选
「丰田怎么样？」        → Analyst 做估值分析
「最新新闻告诉我」      → Researcher 通过 Grok API 获取新闻
「PF 还健康吗？」       → Health Checker 给出数值，Strategist 给出建议
「暴跌时会怎样？」      → Health Checker 执行压力测试
「评价 momentum 因子」  → Quant Researcher 给出 IC/coverage/实验 artifact
「帮我记一笔」          → 直接保存投资笔记
```

### Codex 自然语言触发

Codex 会根据 `.agents/skills/*/SKILL.md` 的 frontmatter 自动启用 skill。本仓库使用以下 Codex canonical path:

```text
.agents/skills/stock-skills/  # 投资助手编排器
.agents/skills/deepthink/     # 复杂情景分析
.agents/agents/               # screener/analyst/... 角色定义
.agents/rules/                # 开发、测试、工作流规则
```

为兼容 Claude Code，仓库保留 `.claude/` mirror。两者同时存在时，Codex 的执行和 dry-run 以 `.agents/` 为准。

### 输出格式（Output & Visibility v1）

所有响应按 4 层显示（KIK-729）。

```text
🎯 [<agent or chain>] <task summary>        ← Layer 1 页眉（始终显示）
✅ <agent> 完成 (X.Xs) — <1 行摘要>         ← Layer 2 进度（仅链式执行）

[Layer 3 正文: Pattern A/B/C]
- Pattern A: 最小输出（VIX/TODO/价格等即时事实）
- Pattern B: 标准 4 节（单一 agent 分析）
- Pattern C: 链式输出（多个 agent 或 routine）

📊 执行: A → B → C                          ← Layer 4 页脚（固定顺序）
💾 保存: data/<path>
🔍 是否用 Reviewer 检查？ [y/skip]
➡ 下一步: <下一步建议>
```

Reviewer 按 3 类启动:

- 🔒 **自动**: 买卖确认前、conviction 违背、周度 routine
- 🔍 **按需**: strategist/screener 等输出末尾显示 `[y/skip]`，下一轮输入 `y` 时启动
- ⏭ **跳过**: HC/researcher/analyst/risk-assessor 单独执行

## 架构

```text
Orchestrator (.agents/skills/stock-skills/, Claude Code mirror: .claude/skills/stock-skills/)
  ├─ SKILL.md           — 路由和自主控制
  ├─ routing.yaml       — agent 选择 few-shot
  └─ orchestration.yaml — 重试和升级处理

Agents (.agents/agents/, Claude Code mirror: .claude/agents/) — 8 个角色
  ├─ screener/       — 选股，自主决定 region/preset/theme
  ├─ analyst/        — 估值、低估度、ETF 评估
  ├─ researcher/     — 新闻、情绪、行业和市场状况
  ├─ health-checker/ — 投资组合事实和数值，不做判断
  ├─ strategist/     — 投资判断和建议，整合其他 agent 结果
  ├─ risk-assessor/  — 市场风险判定（risk-on/neutral/risk-off）
  ├─ quant-researcher/ — 量化证据、因子评价、TopN 回测、实验查询
  └─ reviewer/       — 质量和风险检查（GPT+Gemini+Codex/Claude 并行审查）

Tools (tools/)
  ├─ yahoo_finance.py — 股价和基本面
  ├─ graphrag.py      — Neo4j 知识图谱
  ├─ grok.py          — Grok API（X/Web 搜索）
  ├─ llm.py           — 多 LLM（Gemini/GPT/Grok）
  └─ quant_*.py       — 因子计算、评价、TopN 回测、DuckDB/Alphalens/Qlib/vectorbt adapter、Qlib native 通路、实验报告

Data (src/data/) — yahoo_client, grok_client, graph_store, graph_query, common, ticker_utils, portfolio_io
Quant (src/quant/) — data schema/storage, factors, evaluation, backtest, optional adapters, experiments, reports
```

详情见 [docs/architecture.md](docs/architecture.md)。

## Neo4j 知识图谱（可选）

系统可以将 agent 执行历史保存到 Neo4j，以便横向检索历史分析、交易和研究记录。

```bash
docker compose up -d
```

**新用户只使用 `data/` 本地存储即可。Neo4j 是可选功能。** 已经运行 Neo4j 的用户可以继续使用。未连接 Neo4j 时，系统会从 `data/notes/`、`data/portfolio.csv`、`data/screening_results/` 等本地文件自动注入上下文（KIK-719），并保持静默。需要诊断时设置 `NEO4J_DEBUG=1`（KIK-749）。

## 测试

```bash
# 单元测试（不需要 API key/网络，autouse fixture 完整 mock 外部 I/O）
python3 -m pytest tests/ -q           # 约 1381 个测试，约 55 秒

# Dry-run（验证 routing.yaml 和 agent 定义一致性，不需要 API key）KIK-746
python3 tests/e2e/run_e2e.py --dry-run

# Mocked E2E（pytest fixture stub tools 层，不需要 API key）KIK-747
python3 -m pytest tests/e2e/test_mocked.py -q

# 真实 API E2E（实际调用 Yahoo Finance / LLM，需要 API key）
python3 tests/e2e/run_e2e.py
python3 tests/e2e/run_e2e.py e2e_001
```

### Quant Phase 7b Optional Stack

成熟库集成是 optional dependency，但 adapter 本身必须 graceful degradation。缺包或导入失败时会写入 `skip_reason`，不会阻塞 Phase 0-6。

```bash
conda run -n stock-skills-2 python tools/quant_scale_test.py --sizes 2000 --duckdb
conda run -n stock-skills-2 python tools/quant_eval.py run --factor momentum_12_1 --alphalens
conda run -n stock-skills-2 python tools/quant_data.py qlib-convert --market cn
conda run -n stock-skills-2 python tools/quant_qlib.py convert --market cn
conda run -n stock-skills-2 python tools/quant_qlib.py run --market cn
conda run -n stock-skills-2 python tools/quant_qlib.py compare --market cn --mode native-research
conda run -n stock-skills-2 python tools/quant_backtest.py run --qlib --vectorbt --robustness
```

主要 artifact: DuckDB scale report、Alphalens tear sheet HTML/PNG、Qlib legacy staging + pandas/Qlib comparison、Qlib native bin_data / `qlib_native_summary.json` / same-signal 或 native-research 比较报告、vectorbt ranking/heatmap、walk-forward、IC decay、factor correlation、分年份/市值组/成本/TopN/市场状态稳健性报告。Qlib native 会分层记录 `qlib_data_available`、`qlib_model_available`、`qlib_backtest_available`；例如 LightGBM 动态库缺失时只标记 model 层 `skip_reason`，不会影响 pandas MVP。

### Worktree 设置（KIK-745）

开发用 worktree 通过 `scripts/setup_worktree.sh` 设置，并使用通用 fixture，避免复制个人投资组合数据:

```bash
bash scripts/setup_worktree.sh KIK-NNN feature-name
# 展开到 ~/stock-skills-kikNNN，并将 tests/fixtures/sample_portfolio.csv
# 复制到 data/，使用通用测试标的而不是个人 PF
```

### E2E 测试情景

| ID | agent | 输入例 | 验证内容 |
|:---|:---|:---|:---|
| e2e_001 | Screener | 有什么好股票？ | EquityQuery、标的列表、region |
| e2e_002 | Analyst | 7203.T 怎么样？ | PER/PBR/ROE、价格历史 |
| e2e_003 | Health Checker | PF 还健康吗？ | 15 个标的、thesis/observation、还原率 |
| e2e_004 | Researcher | 最新新闻 | Grok API、情绪、GraphRAG |
| e2e_005 | Risk Assessor | 做风险判定 | VIX/利率/WTI、RSI 计算 |
| e2e_006 | HC + Strategist | 想改善 PF | lesson、thesis、what-if |
| quant_001 | Quant Researcher | 评价 momentum_12_1 因子的 IC 和分组收益 | 因子评价路由、artifact guardrail |
| quant_002 | Quant → Strategist | 用量化结果帮我设计再平衡策略 | 量化证据到策略链式路由 |
| quant_003 | Analyst → Quant | 分析丰田并看因子暴露 | 个股分析和因子暴露链式路由 |

## 从 v1 迁移

可以从 v1（[stock_skills](https://github.com/okikusan-public/stock_skills)）迁移。

### 数据兼容性

v1 中积累的以下数据可以直接在 v2 中使用:

| 数据 | v1 位置 | v2 位置 | 兼容性 |
|:---|:---|:---|:---|
| 投资笔记和 lesson | `data/notes/*.json` | `data/notes/*.json` | 完全兼容 |
| 筛选历史 | `data/history/screen/*.json` | `data/history/screen/*.json` | 完全兼容 |
| 交易记录 | `data/history/trade/*.json` | `data/history/trade/*.json` | 完全兼容 |
| 报告历史 | `data/history/report/*.json` | `data/history/report/*.json` | 完全兼容 |
| 研究历史 | `data/history/research/*.json` | `data/history/research/*.json` | 完全兼容 |
| 健康检查历史 | `data/history/health/*.json` | `data/history/health/*.json` | 完全兼容 |
| 投资组合 | `data/portfolio.csv` | `data/portfolio.csv` | 完全兼容 |
| 观察清单 | `data/watchlists/*.json` | `data/watchlists/*.json` | 完全兼容 |
| Neo4j（GraphRAG） | 原连接 | 原连接 | 完全兼容 |

### 迁移步骤

```bash
# 1. 克隆 v2
git clone https://github.com/okikusan-public/stock_skills_2.git
cd stock_skills_2

# 2. 复制 v1 的 data/ 目录
cp -r /path/to/stock_skills/data/ ./data/

# 3. 安装依赖
pip install -r requirements.txt

# 4. 可选：同步 GraphRAG
# 在 v2 中说“同步一下”即可执行 data/ → Neo4j 同步
```

v1 的 `scripts/`、`src/output/`、旧 `SKILL.md` 集合在 v2 中不再需要。仅复制 `data/` 即可完成迁移。

## 免责声明

本软件仅提供投资判断的参考信息，**不保证任何投资结果**。基于本软件输出做出的投资决策均由使用者自行承担责任。开发者不对使用本软件产生的任何损失负责。

## 许可证

MIT License。详情见 [LICENSE](LICENSE)。
