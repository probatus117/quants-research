# 中文化迁移实施计划

> **For agentic workers:** 本计划按阶段执行。每次只推进一个 Phase，阶段完成后运行该阶段验证，再进入下一阶段。不要在 Phase 0 中修改 agent prompt、路由样例、运行时文案或测试断言。

**目标:** 将项目基础语言迁移为简体中文，并只保留中文自然语言入口。

**架构:** `.agents` 是 Codex canonical 资产，`.claude` 是 Claude Code mirror。先迁移 canonical，再同步 mirror；运行时代码只迁移说明性文本和用户可见文案，不改标识符、schema、枚举、数据格式和持久化路径。

**技术栈:** Codex agent assets、YAML routing/examples、Python tools/runtime、pytest E2E、Markdown docs。

---

## 迁移不变量

- 不修改代码标识符、函数名、类名、模块名、API schema、dict key、枚举值、环境变量、ticker、模型 ID、数据格式和持久化路径。
- 不迁移 `data/cache`、`.pyc`、真实个人数据、许可证正文和第三方生成物。
- 简体中文是唯一自然语言入口；后续 Phase 不保留旧日文入口样例。
- `.agents` 优先作为源资产修改；`.claude` 在 Phase 5 统一镜像同步。
- 每个 Phase 应独立验证、独立提交，避免 prompt、路由、测试和文档混在一次变更中。

## Phase 0 基线结果

状态: 已建立迁移基线，未修改运行时代码、路由、agent 定义或测试。

基线日期: 2026-05-19

### 扫描命令

以下命令用于复现 Phase 0 扫描结果。为避免计划文件自身新增旧日文字符，日文假名扫描使用 Unicode 范围写法。

```bash
rg --count-matches -P "[\x{3040}-\x{30ff}]" .agents .claude docs src tools tests scripts config AGENTS.md README.md CLAUDE.md -g '!**/__pycache__/**' -g '!data/cache/**'
rg -n "(Japanese prompt|English prompt|日文|英文|Japanese|English|news|portfolio|risk|recommend|output|prompt|Prompt)" .agents .claude docs src tools tests scripts config AGENTS.md README.md CLAUDE.md -g '!**/__pycache__/**' -g '!data/cache/**'
rg -n "(prompt|Prompt|system prompt|user_prompt|query_prompt|messages|Please|You are)" src tools scripts tests .agents .claude -g '!**/__pycache__/**' -g '!data/cache/**'
rg -n "^(\\s*- intent:|\\s*triggers:|\\s*header:|\\s*role:)" .agents .claude -g '*.yaml'
```

### 高密度旧语言区域

| 区域 | 代表文件 | 后续 Phase |
| --- | --- | --- |
| Codex canonical skill/rule/agent 说明 | `.agents/skills/stock-skills/SKILL.md`, `.agents/skills/deepthink/SKILL.md`, `.agents/rules/*.md`, `.agents/agents/*/agent.md` | Phase 1 |
| 中文自然语言路由入口 | `.agents/skills/stock-skills/routing.yaml`, `.agents/agents/*/examples.yaml` | Phase 2 |
| Claude mirror | `.claude/skills/*/SKILL.md`, `.claude/rules/*.md`, `.claude/agents/*/{agent.md,examples.yaml}` | Phase 5 |
| 运行时 prompt 和用户可见文案 | `src/data/grok_client/*.py`, `src/data/context/*.py`, `src/data/graph_store/linker.py`, `src/data/morning_summary.py`, `tools/*.py`, `scripts/backfill_*.py` | Phase 3 |
| 测试输入、mock 输出和断言 | `tests/test_kik746_dry_run.py`, `tests/e2e/test_scenarios.yaml`, `tests/e2e/test_mocked.py`, `tests/data/test_grok_client_research.py`, `tests/data/test_grok_client_trending*.py` | Phase 4 |
| 用户文档和配置说明 | `README.md`, `AGENTS.md`, `CLAUDE.md`, `docs/*.md`, `config/*.yaml` | Phase 5 |

### 日文假名扫描摘要

`rg --count-matches -P "[\x{3040}-\x{30ff}]"` 显示旧日文自然语言主要集中在以下文件组：

| 文件组 | 典型计数特征 |
| --- | --- |
| `.agents/skills/stock-skills/SKILL.md` 与 `.claude/skills/stock-skills/SKILL.md` | 单文件约 3.8k 假名字符，属于最高优先级说明和输出规则迁移对象 |
| `.agents/skills/deepthink/SKILL.md` 与 `.claude/skills/deepthink/SKILL.md` | 单文件约 1.8k 假名字符，包含 DeepThink 触发、限制和输出规则 |
| `.agents/skills/stock-skills/routing.yaml` 与 `.claude/skills/stock-skills/routing.yaml` | 单文件约 850 假名字符，包含旧自然语言入口、trigger、header |
| `.agents/agents/*/examples.yaml` 与 `.claude/agents/*/examples.yaml` | risk-assessor、reviewer、screener、strategist、researcher、health-checker、analyst 均有大量 few-shot 文案 |
| `README.md`, `AGENTS.md`, `CLAUDE.md`, `docs/neo4j-schema.md` | 文档层残留较多，留到 Phase 5 统一处理 |
| `src/`, `tools/`, `scripts/`, `tests/` | 分散在 prompt builder、context formatter、warning/error、docstring、测试断言中 |

### 路由入口基线

后续 Phase 2 必须重点处理：

- `.agents/skills/stock-skills/routing.yaml`
  - `agents.*.role`
  - `agents.*.triggers`
  - `routes[*].intent`
  - `routes[*].header`
  - `routes[*].note` 与链路说明
- `.agents/agents/*/examples.yaml`
  - `intent`
  - `input`
  - `params.user_input`
  - `judge`
  - `reasoning`
  - `conclude`
  - `recommend`
  - 示例输出块

`.claude` 下同名结构暂不在 Phase 2 直接编辑，Phase 5 由 `.agents` 同步。

### Prompt 和用户可见文案基线

后续 Phase 3 必须重点处理：

- `src/data/grok_client/stock.py`
  - `_build_sentiment_prompt`
  - `_build_stock_deep_prompt`
- `src/data/grok_client/market.py`
  - `_build_trending_prompt`
  - `_build_market_prompt`
  - `_build_trending_themes_prompt`
- `src/data/grok_client/industry.py`
  - `_build_industry_prompt`
- `src/data/grok_client/business.py`
  - `_build_business_prompt`
  - `synthesize_text` 的说明性 docstring
- `src/data/graph_store/linker.py`
  - relationship detection prompt
- `scripts/backfill_persistence_tags.py`
  - lesson persistence classifier prompt
- `scripts/backfill_lesson_fields.py`
  - lesson metadata extraction prompt
- `src/data/context/auto_context.py`, `fallback_context.py`, `context_formatter.py`, `freshness.py`, `summary_builder.py`, `skill_recommender.py`, `screen_annotator.py`
  - 注入到 agent 的上下文标题、推荐理由、状态说明
- `src/data/morning_summary.py`, `src/data/session_state.py`, `src/data/sanity_gate.py`
  - session-start、morning summary、guardrail 文案
- `tools/*.py`
  - CLI facade 的 warning/error、help、docstring

### 测试基线

后续 Phase 4 必须重点处理：

- `tests/data/test_grok_client_research.py`
  - 现有测试显式区分 Japanese prompt 和 English prompt，Phase 4 需要改为统一中文 prompt 断言。
- `tests/data/test_grok_client_trending.py`
  - trending prompt 断言中包含旧市场名称和输出语言假设。
- `tests/data/test_grok_client_trending_themes.py`
  - theme prompt 断言中包含旧市场名称和输出语言假设。
- `tests/e2e/test_scenarios.yaml`
  - E2E 输入和期望输出需要改为中文自然语言入口。
- `tests/e2e/test_mocked.py`
  - mocked E2E 的输入、mock 响应、文本断言需要同步。
- `tests/test_kik746_dry_run.py`
  - routing dry-run 的输入、header、agent 选择断言需要同步。
- `tests/test_session_start_routing.py`, `tests/test_history_check_routing.py`
  - session-start、history-check 入口断言需要检查并转为中文。

## 允许保留的英文技术词

以下词属于技术标识、市场术语、产品名或 schema 兼容项，迁移时默认保留英文：

- Agentic AI Pattern
- API, CLI, SDK, MCP
- JSON, YAML, CSV
- GraphRAG, RAG, Neo4j, yfinance
- Grok API, xAI, WebSearch
- GPT, Gemini, Codex, Claude Code, LLM
- `XAI_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DEBUG`
- `risk-on`, `neutral`, `risk-off`
- ETF, REIT, PF
- RSI, VIX, WTI, HHI
- EPS, PER, PBR, ROE, ROIC, EBITDA, CAGR, DCF
- PASS, WARN, FAIL, FRESH, RECENT, STALE
- buy, hold, sell, trim, exit, close
- thesis, observation, lesson, conviction, watchlist
- ticker, symbol, region, preset, theme, score
- model IDs and provider names such as `gpt-5.4`, `gemini-3.1-pro-preview`, `grok-4.20-0309-reasoning`

## Phase 计划

### Phase 1: 迁移 Codex canonical 资产

**文件:**

- 修改: `.agents/skills/*/SKILL.md`
- 修改: `.agents/rules/*.md`
- 修改: `.agents/agents/*/agent.md`

**范围:**

- 将角色说明、输出格式、操作规则、Reviewer/DeepThink 说明统一为简体中文。
- 不改路由样例，不改 `.agents/agents/*/examples.yaml`。
- 不改 `.claude` mirror。

**验证:**

```bash
rg -n -P "[\x{3040}-\x{30ff}]" .agents/skills .agents/rules .agents/agents -g 'SKILL.md' -g 'agent.md' -g '*.md'
```

### Phase 2: 迁移中文路由入口

**文件:**

- 修改: `.agents/skills/stock-skills/routing.yaml`
- 修改: `.agents/agents/*/examples.yaml`

**范围:**

- 将 `intent`、`triggers`、`header`、few-shot 示例全部切换为中文。
- 不保留旧日文自然语言入口。
- 保持 agent 名称、tool 名称、参数 key 和枚举值不变。

**验证:**

```bash
conda run -n stock-skills-2 python tests/e2e/run_e2e.py --dry-run
```

### Phase 3: 迁移运行时 prompt 和用户可见文案

**文件:**

- 修改: `src/`
- 修改: `tools/`
- 修改: `scripts/`

**范围:**

- 迁移 docstring、注释、warning/error、Grok prompt、context formatter 输出。
- Grok 研究类 prompt 默认要求中文输出，不再按市场切换日文或英文 prompt。
- 保持所有 dict key、返回 schema、函数名和文件格式不变。

**验证:**

```bash
conda run -n stock-skills-2 python -m pytest tests/data/test_grok_client_research.py tests/data/test_grok_client_trending.py tests/data/test_grok_client_trending_themes.py -q
```

### Phase 4: 迁移测试和 fixture 基线

**文件:**

- 修改: `tests/test_kik746_dry_run.py`
- 修改: `tests/e2e/test_scenarios.yaml`
- 修改: `tests/e2e/test_mocked.py`
- 修改: `tests/data/test_grok_client_research.py`
- 修改: `tests/data/test_grok_client_trending*.py`

**范围:**

- 将测试输入、mock 输出、断言文本改为中文。
- 将 Grok prompt 测试从按日文/英文分支断言改为统一中文 prompt 断言。

**验证:**

```bash
conda run -n stock-skills-2 python -m pytest tests/e2e/test_mocked.py -q
```

### Phase 5: 迁移文档和 Claude mirror

**文件:**

- 修改: `README.md`
- 修改: `AGENTS.md`
- 修改: `CLAUDE.md`
- 修改: `docs/*.md`
- 修改: `config/*.yaml`
- 同步: `.claude`

**范围:**

- 文档和配置说明统一为简体中文。
- 将 `.agents` 结果同步到 `.claude`，保留 Claude Code 专用路径和平台名。

**验证:**

```bash
diff -qr .agents .claude
```

只允许平台差异和已知结构差异。

## 最终验证

```bash
conda run -n stock-skills-2 python tests/e2e/run_e2e.py --dry-run
conda run -n stock-skills-2 python -m pytest tests/e2e/test_mocked.py -q
conda run -n stock-skills-2 python -m pytest tests/ -q
rg -n -P "[\x{3040}-\x{30ff}]" .agents .claude docs src tools tests scripts config AGENTS.md README.md CLAUDE.md -g '!**/__pycache__/**' -g '!data/cache/**'
rg -n "(Japanese prompt|English prompt|日文|英文)" .agents .claude docs src tools tests scripts config AGENTS.md README.md CLAUDE.md -g '!**/__pycache__/**' -g '!data/cache/**'
```

最终验证中的 `rg` 命令应无输出；若输出仅来自历史计划说明，需要在 Phase 5 一并迁移或移除。
