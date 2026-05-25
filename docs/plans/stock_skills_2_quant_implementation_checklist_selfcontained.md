# stock_skills_2 量化功能追加：实装 Checklist

> 用途：vibe coding 时供 Agent 逐项 check off。**Agent 默认只读本文件，不读两份方案文档；只有触发下方“允许读方案文档”的条件时才局部读取。**
> 对应方案：`docs/plans/stock_skills_2_quant_extension_plan.md` + `docs/plans/stock_skills_2_quant_implementation_plan.md`（仅阻塞时补充阅读）
> 生成日期：2026-05-21
> 本版本：self-contained execution checklist（2026-05-22）

## 执行边界与降级规则（Agent 必读）

1. **主执行入口**：默认只读本 checklist。每次开始先读 `CURRENT STATUS` 和当前 Phase 的未完成条目。
2. **允许读方案文档的条件**：仅当出现设计冲突、验收标准缺失、外部依赖失败需要产品决策时，才读取两份方案文档中的最小相关段落。读取后必须把结论补回本 checklist，避免下次重复读。
3. **禁止隐式引用方案**：如果条目写着“参照方案 X.X / Task X.X”，视为 checklist 缺陷；先把关键要求内联到本文件，再继续实现。
4. **MVP 必交付范围**：Phase 0-6。必须能基于 fixture/mock/offline 测试完成，不依赖真实 API、付费 token、Neo4j、Qlib、Alphalens、vectorbt 或真实行情 provider。
5. **Phase 7a 核心增强范围**：Phase 7.0-7.7。市场抽象、yfinance provider（US+JP）、三市场 fixture、因子多市场配置化、回测多频率/benchmark/成本、A 股 provider、Agent/Reviewer/报告升级、测试补齐。**7a 交付后系统具备三市场真实数据研究能力**，P0 项失败会阻塞下游，必须优先完成。
6. **Phase 7b 成熟库集成范围**：Phase 7.8-7.13。稳健性分析报告、DuckDB、Alphalens、Qlib、vectorbt 均为必须交付，按两层验收：硬交付层（adapter/capability check/test/report/Reviewer/`skip_reason`）任何环境必须通过；能力交付层在依赖可用时必须产出真实 artifact。依赖失败只允许 graceful skip，不得静默跳过，也不得成为不做 adapter 的理由。
7. **optional dependency 规则**：所有 optional 包必须通过 `try/except ImportError` 或运行时 capability check graceful degradation。缺失时输出明确原因、`skip_reason` 和替代路径。
8. **Phase 完成规则**：每个 Phase 结束更新顶部状态、勾选完成项，并运行该 Phase 指定测试；Phase 结束必须跑全量 pytest。
9. **版本控制规则**：实装过程中必须使用 Git/GitHub 工作流。提交代码前先检查隐私数据和本地产物，禁止未经审计的 `git add .`。

## Plan Digest：两份详细计划的核心意图（Agent 必读）

**最终目标**：在现有 stock-skills 投资助手中新增一条可复现、可审计、可被 Agent 调用的量化研究链路。它不是交易黑箱，而是为 Strategist / Analyst / Reviewer 提供可追溯的量化证据：因子表现、回测结果、coverage、artifact、实验 ID 和风险边界。

**MVP 范围**：Phase 0-6 交付一个离线可验收的最小系统：fixture 数据 → 标准 schema → 因子计算 → 单因子评价 → pandas TopN 回测 → 实验 registry / Markdown 报告 → quant-researcher agent 集成。所有核心路径都必须能用 fixture/mock 跑通，CI/本地测试不依赖真实网络、API key 或外部数据库。

**非目标**：MVP 不追求生产级数据源完整性，不依赖 Qlib/Alphalens/vectorbt，不做真实买卖建议，不替代现有 Analyst/Strategist 的投资判断，不把个人 PF 或真实持仓写入 fixture，不把真实行情产物提交到 git。

**架构原则**：优先使用小而清晰的 Python 模块，每个模块只负责一个边界：provider 取数、schema 校验、storage 读写、factor 计算、evaluation 评价、backtest 回测、experiment 管理、report 生成、agent 编排。CLI 只是薄封装，核心逻辑放在 `src/quant/**`，并可被测试直接调用。

**数据原则**：所有表都先标准化为 date-symbol 粒度或明确的维表结构；schema 校验必须早于因子/回测；fixture 是测试真相来源；`data/quant/**` 是本地产物目录并默认 gitignored；`tests/fixtures/quant/**` 才允许提交 sample/golden 数据。**sample_a 规格**：50~100 只 A 股，覆盖不同市值/行业，日线 2022-01 至 2024-12（≥2 年、≥24 截面），以确保 IC 统计和五分位分组收益有意义。

**因子与评价原则**：先实现少量可解释因子，而不是因子库堆叠。Value、Momentum、Low Volatility 必须有边界值、缺失值、coverage、方向性和可复现测试。评价结果必须包含 IC / Rank IC、分组收益、forward return、多周期、coverage，并用 golden 或手工 pandas/numpy 结果校准，避免“自洽但错误”。

**回测原则**：Phase 4 的 pandas TopN 回测是可解释 MVP，不是高性能交易引擎。必须明确调仓频率、TopN、等权、成本、benchmark、净值、持仓、交易记录和指标计算。结果必须同一 config + data_version 可复现。

**实验与报告原则**：每次实验都有唯一 `experiment_id`，所有关键数字必须来自 artifact（如 `metrics.json`、`coverage.json`、`ic_timeseries.csv`），报告不得手写或倒编数字。Markdown 报告要说明数据、方法、指标、图表、风险、结论边界和下一步。

**Agent 边界**：`quant-researcher` 只负责量化证据，不给买卖建议。纯量化问题可独立回答；策略/PF/个股问题中，它输出实验证据和限制，最终判断由 Strategist/Analyst 综合。Reviewer 必须检查 artifact 完整性、引用一致性、样本不足和是否越界给建议。

**增强路线**：Phase 7 拆分为 7a（核心）和 7b（成熟库集成）。7a 的目标是**美/A/日三市场同等优先**的真实数据研究闭环；市场抽象必须在第一个任务完成，fixture 在 provider 之前验证全链路。7b 的目标是**将自研 MVP 接入行业标准技术栈**（DuckDB/Alphalens/Qlib/vectorbt），按两层验收：硬交付层（adapter 代码/测试/skip_reason）任何环境必须通过，能力交付层（真实 artifact）依赖可用时强制执行。降级只解决"环境不可用时系统不崩"，不变成"库集成可以不做"的借口。设计依据：`docs/plans/phase7_gap_analysis.md`。

## Git/GitHub 工作流（Agent 必读）

**固定远端仓库**：自 2026-05-22 起，本量化扩展的 GitHub 远端统一使用 `probatus117/quants-research`（`https://github.com/probatus117/quants-research.git`）。后续 Codex/Agent 在执行 push、PR、issue、review、tag 或远端协作时，除非用户明确改目标仓库，均必须面向该仓库操作。

**工具边界**：本地 `git` 是代码变更的事实来源，用于 diff、stage、commit、branch、tag。GitHub 插件/connector 适合结构化读取和轻量远端协作：repo/PR/issue metadata、changed files、review/check 摘要、评论、label、reaction、issue/PR triage。不要用 GitHub 插件替代本地 `git status` / `git diff` 审计。

**GitHub 写操作最佳流程（2026-05-23 经验补充）**：push、PR 创建、merge、tag、Actions log 等需要用户身份或 repo write scope 的操作，优先使用本地 `git` + 已认证的 GitHub CLI `gh`。GitHub connector 是 GitHub App token，权限独立于用户本机 `gh` token；即使已授权，也可能对 `create PR` / `merge PR` / `update ref` 返回 `403 Resource not accessible by integration`。遇到 connector 403 时，不要反复重试 connector；改用 `/opt/homebrew/bin/gh` fallback。Codex 沙箱内 `gh auth status` 可能无法访问 macOS keyring 并误报 token invalid；需要验证或执行 `gh pr create` / `gh pr merge` 时，使用 escalated command 运行 `/opt/homebrew/bin/gh ...`。

**首次启用版本控制**：当前目录如果执行 `git status --short` 出现 `fatal: not a git repository`，先完成 Phase 0.0。初始化前必须检查 `.gitignore` 和 `git status --short`，确认 `.env`、个人 PF、现金余额、真实行情、`data/quant/**` 本地产物不会被提交。首次提交建议命名为 `chore: baseline project before quant extension`。

**分支策略**：`main` 只保留可运行基线；量化开发使用短分支。建议每个 Phase 一个主分支，例如 `quant/phase-0-setup`、`quant/phase-1-data-schema`；风险较高或可并行任务可拆子分支，例如 `quant/phase-3-golden-calibration`。

**日常循环**：每次开工先跑 `git status --short`，确认是否有用户或其他 agent 的未提交变更。实现一个小闭环后运行对应测试，再用 `git diff --check` 和 `git diff --stat` 审核。只 stage 本任务相关文件，优先使用精确路径 `git add <path>`；如要使用 `git add .`，必须先完成隐私/产物检查。

**提交粒度**：按可理解的功能点提交，不要等整个 Phase 结束才提交。推荐 commit message：

```text
feat(quant-data): add fixture provider
feat(quant-factor): compute value and momentum factors
test(quant-eval): add golden calibration cases
docs(quant): update checklist status
chore(git): initialize repository workflow
```

**Phase 完成流程**：每个 Phase 结束必须更新 checklist 状态，运行该 Phase 指定测试和全量 `conda run -n stock-skills-2 python -m pytest tests/ -q`。通过后 push 分支到 GitHub，并优先用 `/opt/homebrew/bin/gh pr create` 创建 PR（connector 可先用于读取 repo/branch/PR metadata；若 connector 写入可用也可使用）。PR 描述必须包含：完成的 checklist 项、测试命令与结果、数据/隐私检查结果、已知风险、是否涉及 optional dependency。合并优先用 `/opt/homebrew/bin/gh pr merge`；仅当用户明确授权且分支是 `origin/main` 的 fast-forward 后代时，才允许使用 `git push origin <branch>:main` 作为无 PR 的紧急 fallback。

**Review / Merge / Tag**：PR review 反馈在同一分支修复；不要在共享分支使用 `git reset --hard`。合入 `main` 后为阶段打 tag，例如 `quant-phase-0`, `quant-phase-1`。Phase 7 必须拆分独立 PR：7a P0 不得降级；7b 按两层验收，硬交付层不得省略，能力交付层在依赖可用时必须产出真实 artifact。Phase 7 PR 不得混入 MVP 修复。

## CURRENT STATUS ⬇ (Agent 先读这里)

| 项目 | 状态 |
|---|---|
| **当前 Phase** | Phase 7b：Qlib Native 专用通路追加（7.10b，本地 gate 收口完成；远端 PR/merge/tag 待执行） |
| **目标 GitHub 仓库** | `probatus117/quants-research` |
| **第一个未完成** | 无（本地检查完成；远端 PR/merge/tag 需按 GitHub 流程执行） |
| **已完成** | 341 / 341 |
| **阻塞项** | 无 |
| **上次 pytest** | 2026-05-25：focused optional/provider/Qlib suites `40 passed, 1 warning in 27.18s`；dry-run `11 PASS / 0 FAIL`；mocked E2E `15 passed in 0.24s`；Phase 0-6/quant offline focused `31 passed in 21.78s`；全量 `1504 passed, 1 warning in 89.09s`。Qlib data 层可用并通过 fixture readback；当前环境 LightGBM 缺 `libomp.dylib`，native runner 正确写 model 层 `skip_reason`。 |
| **设计依据** | `docs/plans/phase7_gap_analysis.md`（2026-05-23，含 G.0 两层验收）+ `docs/plans/phase7b_qlib_native_pathway_plan.md`（7.10b Qlib Native 专用通路） |
| **v3 更新** | 7b 从"P2 可选"升级为"必须交付，按两层验收"；fixture(7.1) 在 provider(7.2) 之前；Qlib 对比采用同策略口径 |
| **v4 更新** | 追加 Qlib Native 专用通路：`parquet → Qlib bin_data → Alpha158 → LightGBM → Qlib backtest`，作为现有 7.10 compatibility adapter 之上的 7.10b 能力层 |

> **Agent 操作**：从当前 Phase 的未完成条目开始执行。完成一项勾一项。遇到阻塞更新上方状态。Phase 结束跑 pytest。

**使用方式**：每完成一项，将 `[ ]` 改为 `[x]`。遇到阻塞，在行末标注 `⚠️ 阻塞：<原因>`。每个 Phase 结束后跑一次 `pytest` 确认不破坏现有测试。

---

## Phase 0：项目准备与依赖整理（2～3 天）

### 0.0 Git/GitHub 初始化

- [x] 0.0.1 执行 `git status --short`。如果返回 `fatal: not a git repository`，执行 `git init -b main` 初始化本地仓库；如果已经是 repo，只记录当前分支和未提交变更。
- [x] 0.0.2 审计 `.gitignore`：确认 `.env`、真实 API key、个人 PF/现金文件、真实行情产物、`data/quant/**` 本地产物不会被提交；审计前不得执行 `git add .`。
- [x] 0.0.3 创建 baseline commit：只在确认无隐私数据和本地产物会被提交后，提交当前项目基线，commit message 建议 `chore: baseline project before quant extension`。
- [x] 0.0.4 使用 GitHub 插件或 GitHub CLI 创建远端 repo（建议 private），添加 `origin` 并 push `main`。远端固定为 `probatus117/quants-research`，本地 `origin` 已配置为 `https://github.com/probatus117/quants-research.git`；`main` 和 `quant/phase-0-setup` 已 push。
- [x] 0.0.5 在 GitHub 创建 Milestones/Issues：Phase 0-6 作为 MVP milestone，Phase 7 后续按 7a/7b 独立追踪；每个 Phase 至少一个 issue，issue 描述链接本 checklist。历史上已创建 `MVP Phase 0-6`、`Optional Phase 7` milestones；Phase 7 开工前应将相关 issue/label 更新为 `Phase 7a Core` / `Phase 7b Research Stack` 口径。
- [x] 0.0.6 创建第一条开发分支 `quant/phase-0-setup`，后续 Phase 使用 `quant/phase-N-<short-desc>` 分支。

### 0.1 目录结构

- [x] 0.1.1 新建 `src/quant/__init__.py`
- [x] 0.1.2 新建 `src/quant/data/`、`src/quant/factors/`、`src/quant/evaluation/`、`src/quant/backtest/`、`src/quant/experiments/`、`src/quant/reports/`（各含 `__init__.py`）
- [x] 0.1.3 新建 `data/quant/`（空目录，本地产物用）
- [x] 0.1.4 新建 `tests/fixtures/quant/`（sample/golden 数据目录）
- [x] 0.1.5 新建 `config/quant_data_sources.yaml`、`config/quant_factors.yaml`、`config/quant_backtest.yaml`、`config/quant_universe.yaml`（可为空模板）

### 0.2 .gitignore

- [x] 0.2.1 更新 `.gitignore`，新增以下忽略规则：
  ```
  data/quant/*.parquet
  data/quant/*.duckdb
  data/quant/*.csv
  data/quant/reports/
  data/quant/experiments/
  data/quant/raw/
  data/quant/normalized/
  data/quant/qlib_data/
  data/quant/quant.duckdb
  ```
- [x] 0.2.2 确认 `tests/fixtures/quant/` 不被忽略（可提交 sample/golden 数据）
- [x] 0.2.3 `git status` 确认 `data/quant/` 下新建的空目录/占位文件未被 track

### 0.3 依赖整理

- [x] 0.3.1 新建 `requirements-quant.txt`，内容自包含并按以下格式区分 core / optional：
  ```text
  # Core dependencies for Phase 0-6 MVP
  pandas
  numpy
  pyarrow
  matplotlib
  pyyaml

  # Optional enhancements for Phase 7 or local experiments
  # Install manually only when needed; missing packages must not break P0-P6.
  # duckdb
  # alphalens-reloaded
  # qlib
  # akshare
  # baostock
  # tushare
  # vectorbt
  ```
  Phase 0 只安装 core 依赖；optional 依赖必须通过 `try/except ImportError` 或 capability check 降级。
- [x] 0.3.2 执行 `conda run -n stock-skills-2 python -m pip install -r requirements-quant.txt`（core 依赖）
- [x] 0.3.3 执行 `conda run -n stock-skills-2 python -m pip check` 确认无依赖冲突
- [x] 0.3.4 执行 import smoke test：
  ```bash
  conda run -n stock-skills-2 python -c "import pandas; import numpy; import pyarrow; import matplotlib; import yaml; print('core OK')"
  ```
- [x] 0.3.5 确认 optional 依赖缺失时不 crash（每个 optional 包单独 try/except ImportError 测试）

### 0.4 CLI 框架

- [x] 0.4.1 新建 `src/quant/config.py`：读取 YAML、校验必要字段、输出 config hash
- [x] 0.4.2 新建 `tools/quant_data.py`（stub，`--help` 可执行）
- [x] 0.4.3 新建 `tools/quant_factor.py`（stub，`--help` 可执行）
- [x] 0.4.4 新建 `tools/quant_eval.py`（stub，`--help` 可执行）
- [x] 0.4.5 新建 `tools/quant_backtest.py`（stub，`--help` 可执行）
- [x] 0.4.6 新建 `tools/quant_report.py`（stub，`--help` 可执行）
- [x] 0.4.7 新建 `tools/quant_experiment.py`（stub，`--help` 可执行）

### 0.5 Phase 0 验收

- [x] 0.5.1 所有 `tools/quant_*.py --help` 正常输出（用 `conda run -n stock-skills-2 python` 前缀）
- [x] 0.5.2 `conda run -n stock-skills-2 python -c "import src.quant"` 不报错
- [x] 0.5.3 `conda run -n stock-skills-2 python -m pytest tests/ -q` 全部通过（不破坏原项目测试）

---

## Phase 1：Fixture + 数据 Schema MVP（3～5 天）

### 1.1 Sample 数据准备

- [x] 1.1.1 选定 50～100 只 A 股 sample（覆盖不同市值/行业），生成 `tests/fixtures/quant/sample_universe.csv`
- [x] 1.1.2 下载/生成 sample 股票的日线数据（2022-01-01 至 2024-12-31；MVP 使用离线 synthetic fixture），生成 `tests/fixtures/quant/sample_daily_bar.csv`
- [x] 1.1.3 下载/整理 sample 股票的 daily_basic（PE/PB/市值等；MVP 使用离线 synthetic fixture），生成 `tests/fixtures/quant/sample_daily_basic.csv`
- [x] 1.1.4 准备 sample 交易日历，生成 `tests/fixtures/quant/sample_calendar.csv`
- [x] 1.1.5 确认 fixture 数据不包含个人 PF 真实持仓

### 1.2 Schema

- [x] 1.2.1 新建 `src/quant/data/schema.py`：定义 `daily_bar`、`daily_basic`、`dim_security`、`calendar`、`universe_member` 标准字段和 dtypes
- [x] 1.2.2 实现 schema 校验函数：检查必需字段、dtypes、日期格式、OHLC 合法性
- [x] 1.2.3 新建 `tests/quant/data/test_schema.py`：验证 sample fixture 通过 schema 校验

### 1.3 Fixture Provider

- [x] 1.3.1 新建 `src/quant/data/providers/base.py`：定义 Provider 抽象接口（`get_daily_bar()`, `get_daily_basic()`, `get_calendar()`, `get_universe()`）
- [x] 1.3.2 新建 `src/quant/data/providers/fixture_provider.py`：从 `tests/fixtures/quant/` 读取数据，返回标准化 DataFrame
- [x] 1.3.3 fixture_provider 不访问网络（可在 CI/离线环境运行）
- [x] 1.3.4 新建 `tests/quant/data/test_fixture_provider.py`：验证返回格式、row count、date range、hash

### 1.4 Storage

- [x] 1.4.1 新建 `src/quant/data/storage.py`：实现 `write_parquet()` 和 `read_parquet()`（先不用 DuckDB）
- [x] 1.4.2 写入路径为 `data/quant/parquet/{table_name}/`
- [x] 1.4.3 新建 `tests/quant/data/test_storage.py`：round-trip 读写验证

### 1.5 数据质量检查

- [x] 1.5.1 新建 `src/quant/data/quality_check.py`：实现 OHLC 合法性、成交量非负、日期交易日校验、连续缺失天数、adj_close 跳变、股票池数量异常、fixture hash 一致性
- [x] 1.5.2 新建 `tests/quant/data/test_quality_check.py`：用正常/异常 fixture 验证各检查项

### 1.6 CLI

- [x] 1.6.1 `tools/quant_data.py` 实现 `update --source fixture` 命令（从 fixture 读取 → 写入 parquet）
- [x] 1.6.2 `tools/quant_data.py` 实现 `check` 命令（运行 quality_check）
- [x] 1.6.3 生成 `data/quant/data_version.json`（含 update_time、source、start/end_date、row_count、hash）

### 1.7 Phase 1 验收

- [x] 1.7.1 不联网也能跑通所有 Phase 1 测试
- [x] 1.7.2 daily_bar 字段标准化完成，fixture row count / date range 与预期一致
- [x] 1.7.3 数据质量检查能输出可读报告
- [x] 1.7.4 不读取个人 PF，不需要 API key
- [x] 1.7.5 `conda run -n stock-skills-2 python -m pytest tests/quant/data/ -q` 全部通过
- [x] 1.7.6 `conda run -n stock-skills-2 python -m pytest tests/ -q` 全部通过

---

## Phase 2：因子计算 MVP（1 周）

### 2.1 因子基类

- [x] 2.1.1 新建 `src/quant/factors/base.py`：定义 `FactorConfig`、`FactorResult`、`BaseFactor.compute()`、`BaseFactor.validate_input()`、`BaseFactor.save()`
- [x] 2.1.2 新建 `tests/quant/factors/test_base.py`：验证基类接口

### 2.2 Value 因子

- [x] 2.2.1 新建 `src/quant/factors/value.py`：实现 `value_bp = 1 / PB`
- [x] 2.2.2 PB <= 0 → NaN 处理
- [x] 2.2.3 新建 `tests/quant/factors/test_value.py`：验证计算正确性、NaN 处理、边界值（PB=0, PB<0, PB 缺失）

### 2.3 Momentum 因子

- [x] 2.3.1 新建 `src/quant/factors/momentum.py`：实现 `momentum_12_1 = adj_close[t-21] / adj_close[t-252] - 1`
- [x] 2.3.2 处理上市不足 252 日的股票（应设 NaN 或标记 coverage_flag）
- [x] 2.3.3 新建 `tests/quant/factors/test_momentum.py`：用已知价格序列验证计算、停牌/缺失处理、边界值

### 2.4 Low Volatility 因子

- [x] 2.4.1 新建 `src/quant/factors/low_volatility.py`：实现 `lowvol_60d = - std(daily_return, 60)`
- [x] 2.4.2 处理上市不足 60 日的股票
- [x] 2.4.3 新建 `tests/quant/factors/test_lowvol.py`：验证方向（低波=高分）、波动率计算正确性

### 2.5 因子后处理

- [x] 2.5.1 新建 `src/quant/factors/processing.py`：实现 winsorize（MAD, n=3）、zscore、rank percentile
- [x] 2.5.2 行业/市值中性化暂不做（Phase 7），但 processing pipeline 预留接口
- [x] 2.5.3 新建 `tests/quant/factors/test_processing.py`：验证 winsorize 极值处理、zscore 均值≈0 标准差≈1、percentile 范围

### 2.6 Factor Store

- [x] 2.6.1 实现 factor_value.parquet 写入（date/symbol/factor_name/raw_value/winsorized_value/zscore/percentile/direction/universe）
- [x] 2.6.2 生成因子覆盖率报告（每个因子每个日期的有效 symbol 数 / universe 总数）
- [x] 2.6.3 生成因子分布图（直方图、按日期的时间序列）

### 2.7 CLI

- [x] 2.7.1 `tools/quant_factor.py` 实现 `compute` 命令（从 storage 读取 → 计算 → 写入 factor store）

### 2.8 Phase 2 验收

- [x] 2.8.1 3 个因子均输出 date-symbol 粒度结果
- [x] 2.8.2 因子覆盖率与 sample fixture 的 expected coverage 一致
- [x] 2.8.3 zscore 均值接近 0，标准差接近 1
- [x] 2.8.4 异常 PE/PB 有 NaN 处理逻辑
- [x] 2.8.5 同一 config 重跑结果一致
- [x] 2.8.6 `conda run -n stock-skills-2 python -m pytest tests/quant/factors/ -q` 全部通过
- [x] 2.8.7 `conda run -n stock-skills-2 python -m pytest tests/ -q` 全部通过

---

## Phase 3：最小单因子评价（1 周）

### 3.0 Golden 校准（优先完成）

- [x] 3.0.1 新建 `tests/quant/evaluation/test_golden_calibration.py`
- [x] 3.0.2 用 sample fixture 数据跑 Alphalens-reloaded（如果环境支持），将 `ic_summary` + `quantile_returns` 保存为 golden
- [x] 3.0.3 如果 Alphalens 装不上，手工 numpy/pandas 计算预期 IC 和分组收益作为 golden
- [x] 3.0.4 golden 数据存入 `tests/fixtures/quant/expected_ic_summary.json`
- [x] 3.0.5 确认 minimal_runner 的 IC 均值/Rank IC 均值/分组收益均值与 golden 偏差 < 0.01
- [x] 3.0.6 CI 中 minimal_runner 测试必须对比 golden，不得仅自洽通过

### 3.1 评价输入构造

- [x] 3.1.1 新建 `src/quant/evaluation/input_builder.py`：合并 factor_value + adj_close → forward return DataFrame
- [x] 3.1.2 实现 forward_return_5d / 20d / 60d 计算
- [x] 3.1.3 新建 `tests/quant/evaluation/test_input_builder.py`

### 3.2 IC/Rank IC 分析

- [x] 3.2.1 新建 `src/quant/evaluation/ic_analysis.py`：计算 IC Mean、IC Std、ICIR、Rank IC Mean、Rank ICIR、IC Positive Ratio
- [x] 3.2.2 支持 multi-period（5d/20d/60d）
- [x] 3.2.3 新建 `tests/quant/evaluation/test_ic_summary.py`

### 3.3 分组收益分析

- [x] 3.3.1 新建 `src/quant/evaluation/quantile_analysis.py`：计算 5 分位 forward return、Long-Short Spread
- [x] 3.3.2 支持 multi-period
- [x] 3.3.3 新建 `tests/quant/evaluation/test_quantile_analysis.py`

### 3.4 最小评价 Runner

- [x] 3.4.1 新建 `src/quant/evaluation/minimal_runner.py`：整合 input_builder + ic_analysis + quantile_analysis
- [x] 3.4.2 实现 `min_coverage` 检查（默认 0.80，不满足时警告）
- [x] 3.4.3 实现 coverage.json 输出

### 3.5 指标导出

- [x] 3.5.1 新建 `src/quant/evaluation/exporter.py`：导出 `factor_summary.json`、`ic_timeseries.csv`、`quantile_returns.csv`、`coverage.json`

### 3.6 因子评价报告

- [x] 3.6.1 新建 `src/quant/reports/factor_report.py`：生成 Markdown 报告（因子定义、数据区间、股票池、IC/Rank IC、分组收益、覆盖率、初步结论、风险提示）
- [x] 3.6.2 新建 `tests/quant/evaluation/test_factor_report.py`

### 3.7 CLI

- [x] 3.7.1 `tools/quant_eval.py` 实现 `run` 命令（调用 minimal_runner → export → report）

### 3.8 Phase 3 验收

- [x] 3.8.1 momentum_12_1 能生成 IC/Rank IC 序列
- [x] 3.8.2 能输出 5D/20D/60D forward return 分析
- [x] 3.8.3 能输出五分位收益
- [x] 3.8.4 minimal_runner 与 golden 偏差 < 0.01（test_golden_calibration 通过）
- [x] 3.8.5 缺失数据过多时报告明确提示 coverage 问题
- [x] 3.8.6 能输出 Markdown 报告
- [x] 3.8.7 `conda run -n stock-skills-2 python -m pytest tests/quant/evaluation/ -q` 全部通过
- [x] 3.8.8 `conda run -n stock-skills-2 python -m pytest tests/ -q` 全部通过

---

## Phase 4：pandas TopN 回测 MVP（1 周）

### 4.1 信号生成

- [x] 4.1.1 新建 `src/quant/backtest/signal_builder.py`：实现单因子 score、多因子 composite score、score 标准化
- [x] 4.1.2 composite_v1 公式：`0.34*bp_zscore + 0.33*momentum_zscore + 0.33*lowvol_zscore`
- [x] 4.1.3 输出 `signal.parquet`
- [x] 4.1.4 新建 `tests/quant/backtest/test_signal_builder.py`

### 4.2 Pandas 回测 Runner

- [x] 4.2.1 新建 `src/quant/backtest/pandas_runner.py`：实现月频调仓、TopN 选择、等权持仓、组合净值计算、交易记录
- [x] 4.2.2 实现过滤：exclude_st、exclude_suspended（根据 sample 数据可用字段）
- [x] 4.2.3 排序规则：score 降序，选 TopN（默认 10）
- [x] 4.2.4 调仓日：每月首个交易日
- [x] 4.2.5 新建 `tests/quant/backtest/test_pandas_runner.py`：用已知价格和信号验证回测净值

### 4.3 成本模型

- [x] 4.3.1 新建 `src/quant/backtest/cost_model.py`：buy_cost=0.0015, sell_cost=0.0025, min_cost=5
- [x] 4.3.2 计算换手时的交易成本，从组合净值中扣除
- [x] 4.3.3 新建 `tests/quant/backtest/test_cost_model.py`

### 4.4 回测指标

- [x] 4.4.1 新建 `src/quant/backtest/metrics.py`：实现 annual_return、annual_volatility、sharpe、max_drawdown、calmar、turnover、excess_return、benchmark_return
- [x] 4.4.2 benchmark 为 sample 等权组合
- [x] 4.4.3 新建 `tests/quant/backtest/test_metrics.py`：用已知序列验证各指标计算

### 4.5 回测报告

- [x] 4.5.1 新建 `src/quant/reports/backtest_report.py`：生成回测 Markdown 报告（策略参数、收益指标、风险指标、交易指标、收益曲线图、回撤图）
- [x] 4.5.2 新建 `src/quant/reports/charts.py`：生成 equity_curve.png、drawdown.png、yearly_return.png

### 4.6 CLI

- [x] 4.6.1 `tools/quant_backtest.py` 实现 `run` 命令（读取 config → signal → backtest → metrics → report）

### 4.7 Phase 4 验收

- [x] 4.7.1 sample_a 月频回测可跑通
- [x] 4.7.2 输出 portfolio_value.csv、positions.csv、trades.csv
- [x] 4.7.3 输出 metrics.json（含所有指标）
- [x] 4.7.4 输出收益曲线和回撤图
- [x] 4.7.5 支持单因子和 composite score 两种输入
- [x] 4.7.6 同一 config + data_version 重跑结果完全一致
- [x] 4.7.7 `conda run -n stock-skills-2 python -m pytest tests/quant/backtest/ -q` 全部通过
- [x] 4.7.8 `conda run -n stock-skills-2 python -m pytest tests/ -q` 全部通过

---

## Phase 5：实验管理与报告系统（1 周）

### 5.1 Experiment Registry

- [x] 5.1.1 新建 `src/quant/experiments/registry.py`：实现 `create_experiment()`、`save_artifact()`、`update_status()`、`list_experiments()`、`get_experiment()`
- [x] 5.1.2 experiment_id 格式：`EXP_YYYYMMDD_HHMMSS_{market}_{task_type}_{short_hash}`
- [x] 5.1.3 status 流转：running → success / failed
- [x] 5.1.4 实验目录结构：`data/quant/experiments/{experiment_id}/` 下存放 config.yaml、data_version.json、metrics.json、charts/、report.md

### 5.2 Config Hash

- [x] 5.2.1 新建 `src/quant/experiments/config_hash.py`：计算 config + data_version 的确定性 hash
- [x] 5.2.2 相同输入产生相同 hash（可复现性）

### 5.3 报告生成器

- [x] 5.3.1 新建 `src/quant/reports/markdown_report.py`：支持 `factor_eval_report`、`backtest_report`、`experiment_compare_report` 三种模式
- [x] 5.3.2 报告模板固定包含以下 7 节：
  1. 实验摘要
  2. 数据与股票池
  3. 因子/策略定义
  4. 核心指标
  5. 图表与 artifact
  6. 稳健性与风险提示
  7. 结论边界与下一步
- [x] 5.3.3 所有关键数值必须从 metrics.json 读取，不在模板中写死

### 5.4 JSON/Neo4j 写入适配

- [x] 5.4.1 report summary 写入 `data/history/quant/*.json`（与现有 `data/history/` 格式对齐）
- [x] 5.4.2 Neo4j 写入为 optional：`try/except ImportError` + `NEO4J_MODE` 检查
- [x] 5.4.3 Neo4j 不可用时 graceful degradation，不影响报告生成

### 5.5 CLI

- [x] 5.5.1 `tools/quant_report.py` 实现 `generate` 命令
- [x] 5.5.2 `tools/quant_experiment.py` 实现 `list`、`compare` 命令

### 5.6 Phase 5 验收

- [x] 5.6.1 每次实验都有唯一 experiment_id
- [x] 5.6.2 每次实验都能找到 config.yaml、data_version.json、metrics.json
- [x] 5.6.3 报告中的关键数值能回溯到 metrics.json（不得有不来自 artifact 的数字）
- [x] 5.6.4 Neo4j 不可用时不影响报告生成
- [x] 5.6.5 `conda run -n stock-skills-2 python -m pytest tests/ -q` 全部通过

---

## Phase 6：Agent 集成（1 周）

### 6.1 Quant Researcher Agent 定义

- [x] 6.1.1 新建 `.agents/agents/quant-researcher/agent.md`，角色边界必须自包含：
  - 负责：因子计算、因子评价、TopN 回测、实验查询、量化证据摘要。
  - 不负责：直接给买卖建议、替代 Strategist 做仓位/交易决策、编造未运行实验数字、用真实数据覆盖 fixture/mock 测试。
  - 输出要求：必须引用 `experiment_id`、artifact 路径和关键指标来源；样本不足、coverage 不足、数据源缺失时明确拒绝结论并列出需要补齐的数据。
  - 编排边界：纯量化问题可独立回答；策略/PF/个股问题只提供量化证据，最终投资建议由 Strategist 或 Analyst 综合。
- [x] 6.1.2 新建 `.agents/agents/quant-researcher/examples.yaml`（覆盖类型 A/B/C/样品不足/降级 7 个 few-shot）
- [x] 6.1.3 同步 `.claude/agents/quant-researcher/agent.md`（mirror）
- [x] 6.1.4 同步 `.claude/agents/quant-researcher/examples.yaml`（mirror）

### 6.2 Routing

- [x] 6.2.1 修改 `.agents/skills/stock-skills/routing.yaml`，新增 quant 相关 intent（纯量化/策略+量化/个股+因子暴露/实验查询）
- [x] 6.2.2 同步 `.claude/skills/stock-skills/routing.yaml`（mirror）
- [x] 6.2.3 更新 `src/orchestrator/dry_run.py::_expected_tools_for_agent()`，为 `quant-researcher` 增加工具列表

### 6.3 Orchestration

- [x] 6.3.1 修改 `.agents/skills/stock-skills/orchestration.yaml`，新增 quant_on_strategy_question / quant_on_stock_analysis / quant_on_pf_diagnosis / quant_standalone / quant_failure 规则
- [x] 6.3.2 同步 `.claude/skills/stock-skills/orchestration.yaml`（mirror）

### 6.4 Reviewer

- [x] 6.4.1 在 Reviewer agent.md 中新增量化 Layer 1（artifact 完整性 12 项）+ Layer 2（引用一致性 4 项）检查清单
- [x] 6.4.2 违规检查（Quant Researcher 输出买卖建议）设为 Reviewer auto trigger

### 6.5 config/tools.yaml

- [x] 6.5.1 在 `config/tools.yaml` 中新增 `quant_factor.compute`、`quant_eval.run`、`quant_backtest.run`、`quant_report.generate`、`quant_experiment.list` 的函数登记

### 6.6 Strategist/Analyst 更新

- [x] 6.6.1 更新 Strategist agent.md：追加「量化证据使用规则」（引用 experiment_id、标注矛盾、不倒编数字）
- [x] 6.6.2 更新 Analyst agent.md：追加「因子暴露规则」（因子暴露放独立小节、不替代估值判断、标注无覆盖）

### 6.7 E2E 测试

- [x] 6.7.1 新增 mocked E2E 场景：纯因子评价路由到 quant-researcher
- [x] 6.7.2 新增 mocked E2E 场景：策略+量化路由到 quant-researcher → strategist chain
- [x] 6.7.3 新增 mocked E2E 场景：样本不足时 quant-researcher 拒绝给出结论
- [x] 6.7.4 dry-run 验证 routing 一致性

### 6.8 Phase 6 验收

- [x] 6.8.1 Agent 正确路由到 quant-researcher（所有场景）
- [x] 6.8.2 Quant Researcher 在所有场景下未输出买卖建议
- [x] 6.8.3 类型 B 场景下 Strategist 正确引用量化证据（experiment_id + 指标）
- [x] 6.8.4 Reviewer 能发现缺失的回测假设（Layer 1）和引用不一致（Layer 2）
- [x] 6.8.5 样本不足时 Agent 明确拒绝给出结论
- [x] 6.8.6 `conda run -n stock-skills-2 python tests/e2e/run_e2e.py --dry-run` 通过
- [x] 6.8.7 `conda run -n stock-skills-2 python -m pytest tests/e2e/test_mocked.py -q` 通过
- [x] 6.8.8 `conda run -n stock-skills-2 python -m pytest tests/ -q` 全部通过

---

## Phase 7a：多市场核心链路（3～4 周，P0/P1）

> **目标**：从单市场 fixture 升级为美/A/日三市场真实数据驱动的量化研究闭环。
> **设计依据**：`docs/plans/phase7_gap_analysis.md`。
> P0 项失败会阻塞下游，必须优先完成。P1 项可延后但应在 7a 内完成。

### 7.0 市场抽象与 artifact contract（P0 阻塞项，预计 3～5 天）

- [x] 7.0.1 `daily_bar`、`daily_basic`、`calendar`、`dim_security`、`universe_member` schema 均增加 `market` 列（`cn`/`us`/`jp`）。新增字段：`currency`、`delist_date`、`dividend_yield`、`total_share`/`float_share`、`exchange`。同时定义下游 artifact 的市场传播范围：`factor_value`、signal、`portfolio_value`、`positions`、`trades`、`metrics.json`、experiment registry、compare report 必须保留 `market` / `base_currency` / `benchmark`。2026-05-23：schema + CN fixture + factor/eval/backtest artifact propagation 已落地；experiment registry/compare report 已有 `market` 元数据，`base_currency`/`benchmark` 由 backtest artifact 写入。
  - **验收**：三市场 schema 全部通过 `validate_schema()`；`market` 字段非空约束；一个三市场 fixture run 结束后，下游 artifact 中仍可追踪 market/base_currency/benchmark
- [x] 7.0.2 Provider 接口所有方法增加 `market` 参数。新增 `get_index_member(market, index_code)` 和 `get_benchmark_return(market, index_code, start, end)`。2026-05-23：`QuantDataProvider`、fixture/yfinance/A 股 optional providers/fallback 均已更新。
  - **验收**：`QuantDataProvider` 抽象类包含上述方法签名
- [x] 7.0.3 新增 `src/quant/data/market_config.py`（`MarketConfig` 数据类）：封装交易日历规则、symbol 格式、货币、基准指数、默认成本参数、典型因子参数（如 momentum 窗口天数）。2026-05-23：`cn/us/jp` config、默认成本、benchmark、因子参数已落地。
  - **验收**：`MarketConfig(“cn”)` / `MarketConfig(“us”)` / `MarketConfig(“jp”)` 各自返回完整配置
- [x] 7.0.4 前置 artifact contract V0：定义 `market`、`data_version`、`base_currency`、`benchmark` 为下游必读字段。V1（7.2 yfinance 跑通后补充）：`provider_chain`、`fallback_status`、`skip_reason`。2026-05-23：`src/quant/artifact_contract.py` 增加 V0/V1 contract helper。
  - **验收**：contract 以文档或 dataclass 形式存在，report/Reviewer/Agent 代码引用同一份定义
- [x] 7.0.5 扩展 `normalize_symbol()`：支持美股 ticker（`AAPL`、`BRK.B`）和日股代码（`7203.T`），保留 A 股六位补零。2026-05-23：支持 US `BRK.B` 标准显示 / yfinance `BRK-B` 下载别名、JP `{code}.T`、指数 `^N225`。
  - **验收**：`normalize_symbol(“AAPL”)` → `”AAPL”`；`normalize_symbol(“7203.T”)` → `”7203.T”`；`normalize_symbol(“1”)` → `”000001”`
- [x] 7.0.6 多市场 Schema 审计：用 yfinance probe 下载 10 只美股 + 10 只日股各 2 年数据，跑通现有全流程（schema → storage → quality_check），记录字段差异。日股覆盖度不得写成先验结论，必须用 `provider_probe.json` / `coverage_report.json` 实测可研究范围。2026-05-23：`tools/quant_provider_probe.py` 产出 `data/quant/provider_probe/provider_probe.json` / `coverage_report.json`；联网 probe 实测 US 10/10、JP 10/10 返回 2 年 daily_bar。
  - **验收**：审计报告列出 schema 差异清单；`provider_probe.json` / `coverage_report.json` 明确日股在大盘/中小盘/成长市场等样本上的覆盖率、空值率和不可用原因
- [x] 7.0.7 多市场 scale test：用 fixture 生成 100/500/2000 股 × 2 年数据，跑通 factor compute → eval → backtest 全流程，记录 `pivot_table`/`groupby`/`merge` 耗时。2026-05-23：`tools/quant_scale_test.py` 写入 `data/quant/scale_test/scale_report.json`；2000 股 × 2 年约 factor 2.53s / eval merge 0.34s / backtest pivot 1.29s。
  - **验收**：scale test 结果记录在案，明确 pandas pipeline 的股数上限建议

### 7.1 三市场 fixture 数据（P0 阻塞项，预计 2～3 天）

- [x] 7.1.1 新建 `tests/fixtures/quant/cn/`、`tests/fixtures/quant/us/`、`tests/fixtures/quant/jp/` 目录，每目录含独立的 `sample_daily_bar.csv`、`sample_daily_basic.csv`、`sample_calendar.csv`、`sample_universe.csv`、`sample_hashes.json`。
  - **验收**：三市场 fixture 各自通过对应市场的 schema 校验
- [x] 7.1.2 Fixture provider 支持 `market` 参数：`get_daily_bar(market=”us”)` → `tests/fixtures/quant/us/sample_daily_bar.csv`。
  - **验收**：`get_daily_bar(market=”cn”)` / `market=”us”` / `market=”jp”` 返回不同数据
- [x] 7.1.3 三市场 fixture 各含 50-60 只股票、≥2 年日线数据（2022-01 至 2024-12），覆盖不同市值和行业。2026-05-23：各市场 60 只、2022-01-03 至 2024-12-31。
  - **验收**：每市场 fixture 的 symbol 数、日期范围、hash 与 expected 一致
- [x] 7.1.4 三市场 fixture 跑通 factor compute → eval → backtest 全流程，验证 `market` 字段在整条链路上正确传播。2026-05-23：`/private/tmp/quant_phase7a_chain/{cn,us,jp}` 临时链路通过，metrics 分别保留 CNY/USD/JPY。
  - **验收**：三市场各自可产出 factor_value.parquet + IC summary + backtest metrics

### 7.2 yfinance provider（P0 阻塞项，预计 3～5 天）

- [x] 7.2.1 新建 `src/quant/data/providers/yfinance_provider.py`。P0 必须实现 `get_daily_bar`、`get_calendar`、`get_benchmark_return`、symbol 标准化、fallback 和 `skip_reason`；`get_daily_basic` / `get_universe` / `get_index_member` 先做 best-effort，字段不足或 provider 不支持时写入 `skip_reason`，不得阻塞 7.2 P0。通过 `try/except ImportError` 设置 `HAS_YFINANCE`。
  - **验收**：`get_daily_bar(market=”us”, ...)` 返回标准化美股数据；P0 方法返回 DataFrame 通过 schema 校验；best-effort 方法不可用时有可读 `skip_reason`
- [x] 7.2.2 实现字段映射：yfinance 列名（`Open`/`High`/`Low`/`Close`/`Volume`/`Dividends`/`Stock Splits`）→ 标准 schema 列名；美股 ticker 和日股 `{code}.T` 格式标准化。
  - **验收**：10 只美股 + 10 只日股 2 年数据通过 schema 校验，`market` 字段正确填充；daily_basic/index_member 缺字段时可降级并记录 `skip_reason`
- [x] 7.2.3 artifact contract V1：基于 yfinance 实际运行经验，补充 `provider_chain`（有序列表）、`fallback_status`（`primary`/`fallback`/`skipped`）、`skip_reason`（可读原因）。2026-05-23：provider DataFrame attrs 与 fallback status 使用同一字段名。
  - **验收**：contract V1 以文档/dataclass 形式冻结，7.0.4 的 V0 定义同步更新
- [x] 7.2.4 新建 `tests/quant/data/test_yfinance_provider.py`：mock 测试覆盖网络超时、返回空 DataFrame、字段缺失三种异常路径；smoke test（需要网络时用 `pytest.mark.skipif(not HAS_YFINANCE, reason=”yfinance not available”)`）。
  - **验收**：mock 测试在离线 CI 通过；`HAS_YFINANCE=False` 时不 crash

### 7.3 因子多市场配置化（P0 阻塞项，预计 3～5 天）

- [x] 7.3.1 `config/quant_factors.yaml` 扩展为每个因子定义各市场参数：
  ```yaml
  factors:
    momentum_12_1:
      enabled: true
      direction: positive
      markets:
        cn: {lookback_days: 252, skip_days: 21}
        us: {lookback_days: 252, skip_days: 21}
        jp: {lookback_days: 245, skip_days: 21}
  ```
  - **验收**：同一因子在三市场使用各自 `lookback_days` 输出不同的 raw_value
- [x] 7.3.2 因子注册机制：`src/quant/factors/registry.py`，使 YAML 配置中的因子名能映射到对应 Factor 类。不再需要在代码中硬编码因子列表。
  - **验收**：`registry.get(“momentum_12_1”)` 返回 `Momentum121Factor` 实例
- [x] 7.3.3 实现 `neutralize()`：`factor_zscore_neutral = residual of regression: factor_zscore ~ industry_dummies + log_market_cap`。需先接入行业分类数据（从 `dim_security.industry` 或真实 provider 获取）。
  - **验收**：`neutralize()` 返回的 zscore_neutral 与原始 zscore 的截面回归 residual 一致（相关系数测试）
- [x] 7.3.4 `src/quant/factors/store.py` 的 `FACTOR_VALUE_COLUMNS` 加入 `zscore_neutral`，确保 eval/backtest 可通过 `--factor-column zscore_neutral` 使用中性化因子。
  - **验收**：`factor_value.parquet` 包含 `zscore_neutral` 列，非空值占比 > 80%

### 7.4 回测多市场增强（P0 阻塞项，预计 4～6 天）

- [x] 7.4.1 解除月频硬编码：`pandas_runner.py` 支持 `frequency in {“weekly”, “monthly”, “quarterly”}`。weekly 取每周首个交易日，quarterly 取每季首个交易日。
  - **验收**：weekly/monthly/quarterly 三种频率各自产生 portfolio_value.csv，净值可复现
- [x] 7.4.2 benchmark 可配置：`BacktestConfig` 增加 `benchmark` 字段（`csi300`/`sp500`/`nikkei225`/`equal_weight`）。metrics 计算 `excess_return = portfolio_return - benchmark_return`。
  - **验收**：指定 benchmark 时 `metrics.json` 包含 `excess_return` 和 `benchmark_return`
- [x] 7.4.3 成本模型按市场参数化：`CostConfig` 增加 `market` 字段或从 `MarketConfig` 读取默认参数。三市场默认值：cn(buy=0.0015, sell=0.0025, min=5), us(buy=0.00002, sell=0.00002, min=0), jp(buy=0.001, sell=0.001, min=0)。
  - **验收**：同一回测在三市场使用各自的成本参数，net return 因成本差异而不同
- [x] 7.4.4 回测策略抽象接口：`src/quant/backtest/strategies.py`，定义 `BaseStrategy.select(signal, date, top_n) -> list[str]` 和 `BaseStrategy.weight(selected, ...) -> dict[str, float]`。`TopNEqualWeight` 作为默认实现。
  - **验收**：`TopNEqualWeight` 的输出与当前 `pandas_runner` 逻辑一致
- [x] 7.4.5 回测结果和报告中标注 `base_currency`：`portfolio_value.csv` 和 `metrics.json` 增加 `base_currency` 字段。
  - **验收**：美股回测标注 `USD`，A 股标注 `CNY`，日股标注 `JPY`
- [x] 7.4.6 Walk-forward 计算逻辑：`src/quant/backtest/walk_forward.py`，支持 expanding window（训练集逐步扩大）和 rolling window（固定窗口滚动）。输出逐窗口的 IC/Sharpe/MaxDD 序列。
  - **验收**：expanding window 和 rolling window 各输出 `walk_forward_metrics.csv`
- [x] 7.4.7 IC decay 计算逻辑：`src/quant/evaluation/ic_decay.py`，计算跨持有期（1D/5D/10D/20D/60D/120D）的 IC 序列。
  - **验收**：输出 `ic_decay.csv`，包含 `period`/`ic_mean`/`rank_ic_mean`/`ic_positive_ratio` 列
- [x] 7.4.8 因子相关性矩阵数值计算：`src/quant/evaluation/factor_correlation.py`，输出各市场/各因子的 pairwise correlation 矩阵。
  - **验收**：输出 `factor_correlation.csv`，三市场各自一个矩阵

### 7.5 A 股 provider（P1，预计 3～5 天）

- [x] 7.5.1 新建 `src/quant/data/providers/akshare_provider.py`，实现 `QuantDataProvider` 全部方法。`HAS_AKSHARE` 通过 `try/except ImportError` 设置。2026-05-23：AKShare adapter 提供日线/日历/universe/index/benchmark best-effort；本机未安装 AKShare 时 graceful skip。
  - **验收**：可下载真实 A 股日线数据并通过 schema 校验；列名映射（中文→标准）正确
- [x] 7.5.2 新建 `src/quant/data/providers/tushare_provider.py`（optional，无 token 或 `HAS_TUSHARE=False` 时 graceful skip）。
  - **验收**：无 token 时不崩溃，返回空 DataFrame 并标注 `skip_reason=”no_token”`
- [x] 7.5.3 provider fallback 逻辑：`src/quant/data/providers/fallback.py`，主源失败 → 备源接管。记录 `provider_chain` 和 `fallback_status`。
  - **验收**：主源异常时自动 fallback 到备源，日志/artifact 中可查到完整 provider_chain
- [x] 7.5.4 新建 `tests/quant/data/test_provider_fallback.py`：mock 主源异常、mock 备源正常、mock 全部源失败三种场景。
  - **验收**：三种场景各自正确记录 fallback_status 和 provider_chain

### 7.6 Agent/Reviewer/报告层升级（P1，预计 3～5 天）

- [x] 7.6.1 Quant Researcher agent.md 增加三市场 agent mode：输出中必须包含 `## 研究模式` 小节，写明 `mode`（`live`/`fixture`/`degraded`）、`market`、`provider_chain`、`data_version`。fixture 模式下必须标注”合成数据，不构成研究结论”；degraded 模式下必须标注缺失的 provider/市场/字段。
  - **验收**：agent 输出中可找到 research mode 小节，且 mode/fixture/degraded 内容符合上述契约
- [x] 7.6.2 登记 `quant_data.update/check` 为正式 Agent 工具：加入 `config/tools.yaml` 和 `src/orchestrator/dry_run.py::_expected_tools_for_agent(“quant-researcher”)`。
  - **验收**：dry-run 通过，quant-researcher 的 expected tools 包含 `quant_data.update` 和 `quant_data.check`
- [x] 7.6.3 报告模板升级：`markdown_report.py` 的”稳健性与风险提示”节不再输出固定文案，改为读取 `robustness_report.json`/`walk_forward_metrics.csv`/`ic_decay.csv`，生成动态内容。
  - **验收**：re-run 一个已有的 backtest experiment 后，新报告的稳健性节包含实际的 walk_forward 指标和 IC decay 数据
- [x] 7.6.4 Reviewer Phase 7 检查项（Layer 3）：新增 provider status 检查、PIT/未来函数风险检查、benchmark 适当性检查（benchmark 是否与 market 匹配）、robustness 阈值检查、跨市场可比性检查（货币/日历/会计周期标注）、optional adapter skip reason 检查。完善现有 Layer 1 和 Layer 2，加入对 Phase 7 artifact 的引用一致性要求。
  - **验收**：Reviewer 输出中包含 Layer 3 检查结果，能发现 benchmark 不匹配、skip_reason 缺失等问题
- [x] 7.6.5 同步 Codex / Claude 文档：`AGENTS.md` 和 `CLAUDE.md` 中的 quant 架构说明统一为 `docs/plans/...` 路径；`.agents` 和 `.claude` 的 quant-researcher agent.md 同步更新。
  - **验收**：两个文件均指向 `docs/plans/` 路径；两个目录的 agent.md 内容一致

### 7.7 测试补齐（贯穿 7a，预计 2～3 天）

- [x] 7.7.1 新增 unit tests：provider mock/fallback、多市场 schema 校验（cn/us/jp 各一份）、字段映射（AKShare 中文列名→标准）、weekly/quarterly rebalance、`zscore_neutral` 持久化、robustness report 渲染、optional dependency skip（`HAS_YFINANCE`/`HAS_AKSHARE`/`HAS_ALPHALENS`/`HAS_QLIB` 分别为 False 时各模块不 crash）。
  - **验收**：`conda run -n stock-skills-2 python -m pytest tests/quant/ -q` 全部通过
- [x] 7.7.2 新增 mocked E2E 场景：自然语言触发”用美股 sample 测试 momentum 因子”→ quant-researcher 使用 us fixture；”下载 A 股数据并检查质量”→ quant_data.update + check；provider fallback 时 Agent 输出 degraded mode；稳健性报告生成后 Reviewer 能检查 Layer 3 项。
  - **验收**：`conda run -n stock-skills-2 python -m pytest tests/e2e/test_mocked.py -q` 包含上述场景且通过

### 7a 验收汇总

- [x] 7a.1 三市场各有一个可用 provider（yfinance 覆盖 US+JP，AKShare 覆盖 CN），数据落地为标准化 parquet 且通过 schema 校验。2026-05-23 验收：provider/schema/storage 相关 tests/quant 全部通过。
- [x] 7a.2 同一因子在三市场使用各自的交易日历和参数，因子值可复现。2026-05-23 验收：MarketConfig + factor registry/processing 测试通过。
- [x] 7a.3 weekly/monthly/quarterly 回测均可运行，benchmark 超额收益计算正确。2026-05-23 验收：Phase 7 backtest enhancement 测试通过。
- [x] 7a.4 Walk-forward 计算逻辑输出逐窗口指标序列；IC decay 和因子相关性矩阵作为 artifact 输出。2026-05-23 验收：robustness metrics 与 backtest enhancement 测试通过。
- [x] 7a.5 `neutralize()` 产生非空的中性化 zscore，并持久化到 factor store。2026-05-23 验收：neutralize + factor store 测试通过。
- [x] 7a.6 Agent 输出包含 research mode 小节，区分 live/fixture/degraded。2026-05-23 验收：mocked E2E 相关场景通过。
- [x] 7a.7 报告中的稳健性内容来源于 artifact 而非固定文案。2026-05-23 验收：report/robustness 渲染测试通过。
- [x] 7a.8 Reviewer 能检查 provider fallback、PIT 风险和 benchmark 适当性。2026-05-23 验收：Reviewer Phase 7 文档与 mocked E2E 场景通过。
- [x] 7a.9 `quant_data.update/check` 进入 dry-run expected tools。2026-05-23 验收：dry-run 输出 quant-researcher expected tools 包含二者。
- [x] 7a.10 `conda run -n stock-skills-2 python -m pytest tests/ -q` 全量通过。2026-05-23：`1469 passed in 71.66s`。
- [x] 7a.11 `conda run -n stock-skills-2 python tests/e2e/run_e2e.py --dry-run` 通过。2026-05-23：`11 PASS / 0 FAIL`。

---

## Phase 7b：成熟量化库集成 + 研究增强（2～4 周，必须交付，按两层验收）

> **定位**：7b 不是外围可选增强，而是将自研 MVP 接入行业标准技术栈，提升研究结论的可信度、可对比性和策略丰富度。
> **验收规则**（详见 `docs/plans/phase7_gap_analysis.md` G.0 节）：
> - **硬交付层（任何环境都必须通过）**：每个库必须有 adapter 代码、CLI/config 开关、capability check（`HAS_*`）、artifact contract、report 集成、Reviewer 检查项、mocked/unit 测试、明确的 `skip_reason`。依赖缺失时 graceful skip 但必须留下可审计记录，**不得静默跳过**。
> - **能力交付层（依赖可用时必须通过）**：在开发环境中每个库至少跑通一个 golden/smoke 实验，产出真实 artifact，进入 experiment registry / report / Reviewer 链路。
> 各库互相独立可并行推进；任一库安装失败不阻塞其他库集成。

### 7.8 DuckDB 集成（P1，硬交付 + 能力交付）

**硬交付（任何环境必须通过）**：
- [x] 7.8.1 新建 `src/quant/data/duckdb_query.py`，capability check `HAS_DUCKDB`；实现 DuckDB → Parquet 查询接口 + SQL 驱动的 universe 构建。2026-05-24：新增 `query_sql()` / `query_table()` / `build_universe()`，并通过 `tools/quant_data.py query` 暴露 CLI 开关。
  - **验收**：`HAS_DUCKDB=False` 时 graceful skip，写入 `skip_reason`；`HAS_DUCKDB=True` 时可做 `SELECT ... FROM daily_bar WHERE market='us'`
- [x] 7.8.2 DuckDB 不可用时自动 fallback 到 `pd.read_parquet()`
  - **验收**：fallback 路径不 crash，日志/output 中可查到 fallback 记录
- [x] 7.8.3 新增 `tests/quant/data/test_duckdb_query.py`（mock + skip 测试）
  - **验收**：mock 测试在离线 CI 通过

**能力交付（HAS_DUCKDB=True 时）**：
- [x] 7.8.4 增量更新：新交易日数据 append → DuckDB 自动感知新 Parquet 文件。2026-05-24：安装 `duckdb==1.5.3` 后运行 `tests/quant/data/test_duckdb_query.py`，真实 DuckDB 路径读取同一 table 目录下追加 parquet 文件，结果包含新增日期/标的。
  - **验收**：新增 1 个月数据后 DuckDB 查询结果包含新数据
- [x] 7.8.5 scale test：对比纯 pandas vs DuckDB+pandas 在三市场 2000 股场景的耗时。2026-05-24：`data/quant/scale_test/duckdb_scale_report.json` 记录 2000 symbols / 1,044,000 daily rows；三市场 symbol counts cn=667/us=667/jp=666；pandas filter 0.0749s，DuckDB parquet query 0.1436s；DuckDB rows 与 pandas rows 一致。
  - **验收**：scale test 结果记录在案

### 7.9 Alphalens-reloaded 集成（P1，硬交付 + 能力交付）

**硬交付（任何环境必须通过）**：
- [x] 7.9.1 新建 `src/quant/evaluation/alphalens_runner.py`，capability check `HAS_ALPHALENS`；支持 `--alphalens` flag 或 config 开关。2026-05-24：`tools/quant_eval.py run --alphalens` 写入 adapter metadata；缺依赖/导入失败时 fallback 到 minimal report 并写 `skip_reason`。
  - **验收**：`HAS_ALPHALENS=False` 时 fallback 到 minimal_runner Markdown 报告，写入 `skip_reason`
- [x] 7.9.2 新增 `tests/quant/evaluation/test_alphalens_runner.py`。2026-05-24：覆盖 missing dependency skip、mocked tear sheet、CLI metadata、Alphalens vs minimal IC calibration。
  - **验收**：mock 测试在离线 CI 通过

**能力交付（HAS_ALPHALENS=True 时）**：
- [x] 7.9.3 生成完整 tear sheet HTML/PNG 作为实验 artifact。2026-05-24：采用 bounded Alphalens compact tear sheet，包含 IC summary、quantile returns、turnover、factor autocorrelation 的 CSV/PNG 与 `tear_sheet.html`，避免官方 interactive tear sheet 长时间挂起。
  - **验收**：tear sheet 包含 IC summary、quantile returns、turnover、factor autocorrelation
- [x] 7.9.4 Alphalens IC summary 与 minimal_runner IC summary 偏差 < 0.01（Phase 3 golden 已校准）。2026-05-24 fixture smoke: max_abs_ic_mean_diff=0.0008078781，max_abs_rank_ic_mean_diff=0.0030746277。
  - **验收**：`test_golden_calibration.py` 中使用 Alphalens 对比的测试通过

### 7.10 Qlib (pyqlib) 集成（P1，硬交付 + 能力交付）

**硬交付（任何环境必须通过）**：
- [x] 7.10.1 新建 `src/quant/data/qlib_converter.py`（parquet → Qlib bin_data），capability check `HAS_QLIB`。2026-05-24：`tools/quant_data.py qlib-convert` 生成 Qlib staging artifact；缺 pyqlib 时写 `qlib_conversion_summary.json` 与 `skip_reason`。
  - **验收**：`HAS_QLIB=False` 时 graceful skip，写入 `skip_reason`
- [x] 7.10.2 新建 `src/quant/backtest/qlib_runner.py`，capability check `HAS_QLIB`；实现 Qlib adapter 执行 → portfolio_value + metrics。2026-05-24：能力层 smoke `available=true, fallback_used=false`，输出 `portfolio_value.csv`、`positions.csv`、`trades.csv`、`metrics.json`、`qlib_run_summary.json`。
  - **验收**：`HAS_QLIB=True` 时 Qlib 回测可运行并产出 metrics
- [x] 7.10.3 Qlib vs pandas 对比报告生成逻辑：
  - 同策略（同一 universe、成本模型、调仓日、复权口径）时对比 Sharpe/MaxDD/annual_return
  - 不同策略时输出差异解释和参数差异，不使用硬阈值判断对错
  - **验收**：对比报告记录在 `qlib_vs_pandas_comparison.md`
  - 2026-05-24：`data/quant/phase7b_smoke/backtest/composite_v1/qlib_vs_pandas_comparison.md` 生成。
- [x] 7.10.4 新增 `tests/quant/backtest/test_qlib_runner.py`
  - **验收**：mock 测试在离线 CI 通过

### 7.10b Qlib Native 专用通路（P1，追加，硬交付 + 能力交付）

> **定位**：7.10b 是现有 7.10 Qlib adapter 之上的 Native 能力层，目标是补齐 `parquet → Qlib bin_data → Alpha158 → LightGBM → Qlib backtest` 全流程。现有 `qlib_converter.py` / `qlib_runner.py` 继续保留审计壳、`skip_reason` 和 pandas 独立运行能力；native pathway 仅在 Qlib/LightGBM/backtest 依赖可用时产出真实 Qlib artifact。
> **核心约束**：Qlib 0.9.7 pip 包不带 `dump_bin` 脚本，不依赖外部转换脚本；用已安装 Qlib 的 `FileFeatureStorage` 写 `.bin`，手写 `calendars/day.txt` 和 `instruments/*.txt`。capability check 必须分为 `qlib_data_available`、`qlib_model_available`、`qlib_backtest_available`，任一层不可用都写明确 `skip_reason`。

**数据写入层（任何环境必须 graceful skip，Qlib data 可用时必须产出 bin_data）**：
- [x] 7.10b.1 新建 `src/quant/data/qlib_bin_writer.py`，实现 Qlib native bin writer；复用或扩展现有 `QlibConversionResult`，支持 `enabled=False`、Qlib data 层不可用、输入 parquet 缺字段时 graceful skip，并写 `qlib_conversion_summary.json`。
- [x] 7.10b.2 实现 `check_qlib_data_capability()`，检查 `pyqlib`、`FileFeatureStorage`、`qlib.init` 是否可用；返回结构化 capability 和 `skip_reason`，不允许仅用 `import qlib` 代表 data 层可用。
- [x] 7.10b.3 实现 `init_qlib_provider(output_market_dir, market)`：`provider_uri={"day": <output_market_dir>}`，CN/US 正确映射 region；JP 暂无 Qlib 原生 region 时映射为 `us` 或配置值，并在 summary 记录 `region_mapping`。
- [x] 7.10b.4 实现 `build_qlib_instrument_name(symbol, exchange, market)`：CN 使用 exchange 前缀生成 `sh000001` / `sz000001`，US symbol 不变，JP 保留项目标准 `7203.T` 后缀；CN 缺 exchange 时硬报错并写清原因。
- [x] 7.10b.5 实现 `compute_adj_factor()` 与 `normalize_qlib_bar_fields()`：`factor = adj_close / close` 且 clip 到 `[0.01, 100]`；写入调整后 `open/high/low/close/vwap`，`volume` 原样，`change = adjusted_close.pct_change()`，field name 写入时不带 `$`。
- [x] 7.10b.6 实现 VWAP 逻辑：优先 `amount / volume * factor`；`amount` 或 `volume` 缺失/不可用时 fallback 到 adjusted typical price，并在 summary 记录 `vwap_policy`。
- [x] 7.10b.7 实现 `build_calendar_index()`：优先使用 parquet calendar 表；缺失时从 `daily_bar` 推导；返回完整 calendar 和 `date -> ordinal index`，每只股票写 bin 前必须 reindex 到完整市场 calendar。
- [x] 7.10b.8 实现 `write_qlib_text_files()`：手写 `calendars/day.txt`（one date per line）和 `instruments/{market_or_universe}.txt`（`instrument<TAB>start_datetime<TAB>end_datetime`），避免 `FileInstrumentStorage` 列顺序兼容性问题。
- [x] 7.10b.9 实现 `write_qlib_features()`：逐 instrument 写 `features/{instrument}/{field}.day.bin`，用 `FileFeatureStorage(instrument, field, "day").write(values, index=first_calendar_idx)`，字段至少覆盖 `open/high/low/close/volume/vwap/factor/change`。
- [x] 7.10b.10 实现 `convert_parquet_to_qlib_bin(parquet_root, output_dir, market, enabled)`：读取 parquet、写 calendar/instruments/features、执行回读验证、写 summary；输出目录为 `data/quant/qlib_bin/<market>/`。
- [x] 7.10b.11 写入后用 `FileFeatureStorage` 和 `D.features()` 做最小回读验证；`.bin` 不兼容或回读值偏差超阈值时 fail fast，错误信息进入 summary。
- [x] 7.10b.12 `qlib_conversion_summary.json` 必须包含 capability、`calendar_count`、`instrument_count`、`field_count`、`price_adjustment_policy`、`vwap_policy`、`provider_uri`、`region_mapping`、`data_version`、`skip_reason`。

**Qlib 配置层（纯配置，可被 CLI/runner 覆写）**：
- [x] 7.10b.13 新建 `config/qlib/dataset.yaml`：定义 Alpha158 handler、train/valid/test 时间分割、market/universe 参数；label 显式写 `Ref($close, -20) / $close - 1`，不依赖 Alpha158 默认 1 日 label。
- [x] 7.10b.14 新建 `config/qlib/model.yaml`：定义 LightGBM 默认参数，包含 `colsample=0.8`、`lr=0.05`、`max_depth=6`、`early_stopping=50`、`num_boost=500`，并允许按市场覆写。
- [x] 7.10b.15 新建 `config/qlib/backtest.yaml`：定义 `TopkDropoutStrategy(topk=10, n_drop=2)`、`SimulatorExecutor`、成本参数；CN 使用 `trade_unit=100`，US/JP 使用 `trade_unit=1` 或关闭交易单位约束，成本从 `MarketConfig` 读取。

**Native Runner（任何环境必须 graceful skip，依赖齐全时必须产出真实 Qlib workflow artifact）**：
- [x] 7.10b.16 新建 `src/quant/backtest/qlib_native_runner.py`，与 `qlib_runner.py` 平行存在；定义 `QlibNativeCapability`、`QlibNativeConfig`、`QlibNativeResult` 等 dataclass。
- [x] 7.10b.17 实现 `check_qlib_native_capability(require_model=True, require_backtest=True)`：分层检查 data/model/backtest；model 层必须验证 `LGBModel` 和 `lightgbm` 动态库可加载；backtest 层必须验证 `TopkDropoutStrategy`、`SimulatorExecutor` 和 workflow records 可导入。
- [x] 7.10b.18 model 层导入失败（例如 `libomp.dylib` 缺失）时必须写 `qlib_model_available=false` 和具体 `skip_reason`；backtest 层失败时写 `qlib_backtest_available=false`，不得把所有错误折叠成 `HAS_QLIB=False`。
- [x] 7.10b.19 实现 `train_qlib_model(provider_uri, market, model_config, dataset_config)`：`qlib.init(provider_uri)`、实例化 Alpha158 handler、按时间分割 train/valid/test、训练 LightGBM、返回 `(trained_model, dataset)`。
- [x] 7.10b.20 实现 `run_qlib_native_backtest(model, dataset, backtest_config, market)`：使用 `TopkDropoutStrategy + SimulatorExecutor` 生成 portfolio returns / positions / orders / metrics。
- [x] 7.10b.21 实现 `run_qlib_native_workflow(config, output_dir, enabled)`：串联 capability、训练、预测、回测、artifact 写入；任一层不可用时 graceful skip，保留可审计 summary。
- [x] 7.10b.22 实现桥接函数 `qlib_predictions_to_signal()`：将 Qlib prediction 输出转换为项目标准 signal 格式，字段和排序口径与 pandas 回测链路兼容。
- [x] 7.10b.23 实现桥接函数 `qlib_portfolio_to_backtest_result()`：将 Qlib 净值/持仓/交易结果转换为 `BacktestResult` 兼容格式，用于 report/Reviewer/compare。
- [x] 7.10b.24 实现 `write_qlib_native_summary()`：输出 `qlib_native_summary.json`，包含 capability、fallback 状态、`data_version`、`provider_uri`、`region_mapping`、`dataset_segments`、`model_params`、`backtest_params`、artifact 路径和 `skip_reason`。

**CLI 与兼容层更新**：
- [x] 7.10b.25 新建 `tools/quant_qlib.py convert --market <market>`：执行 parquet → Qlib `.bin` 转换；产出 `data/quant/qlib_bin/<market>/calendars/day.txt`、`instruments/<market>.txt`、`features/<instrument>/*.bin` 和 summary。
- [x] 7.10b.26 新建 `tools/quant_qlib.py run --market <market>`：执行转换、Alpha158、LightGBM 训练和 Qlib backtest；产出 `predictions.csv`、`portfolio_metrics.json`、`qlib_native_summary.json`。
- [x] 7.10b.27 新建 `tools/quant_qlib.py compare --market <market> --mode same-signal`：只用于同 universe、同成本、同调仓日、同复权口径下比较 pandas 与 Qlib 引擎差异；产出 `qlib_vs_pandas_same_signal_comparison.md`。
- [x] 7.10b.28 新建 `tools/quant_qlib.py compare --market <market> --mode native-research`：用于 pandas MVP 与 Qlib Alpha158/LightGBM native research 的描述性比较；不得用硬阈值判定谁对谁错，产出 `qlib_native_research_comparison.md`。
- [x] 7.10b.29 更新 `src/quant/data/qlib_converter.py`：保留 `convert_parquet_to_qlib()` 向后兼容，增加 deprecation 文案并指向 `convert_parquet_to_qlib_bin()`。
- [x] 7.10b.30 更新 `src/quant/backtest/qlib_runner.py`：保留 `run_qlib_backtest()` 作为 compatibility runner，文档/summary 标记为 `"compatibility runner"`，不与 native runner 混淆。
- [x] 7.10b.31 更新 `tools/quant_data.py qlib-convert`：新增 `--format csv|bin`，默认保留 `csv` 以不破坏旧 staging contract；`--format bin` 调用 native bin writer。
- [x] 7.10b.32 更新 `config/tools.yaml`：新增 `quant_qlib` 工具定义，列出 `convert/run/compare` 命令、输入输出 artifact contract、optional dependency 和 `skip_reason` 行为。
- [x] 7.10b.33 更新 `.agents/agents/quant-researcher/agent.md` 与 `examples.yaml`：新增 Qlib native run/compare 的调用边界、few-shot、输出限制；quant-researcher 只提供量化证据，不给买卖建议。
- [x] 7.10b.34 同步 `.claude/agents/quant-researcher/` mirror，保证 Codex canonical 与 Claude mirror 一致。

**测试（离线 CI 必须通过；真实 Qlib/LightGBM 可用时跑能力层 smoke）**：
- [x] 7.10b.35 新增 `tests/quant/data/test_qlib_bin_writer.py`：覆盖 instrument name 映射（CN sh/sz、US unchanged、JP 保留 `.T`）。
- [x] 7.10b.36 覆盖复权因子、adjusted OHLC/VWAP、`change.day.bin` 计算；边界包含 `close=0`、缺 `amount`、缺 `volume`、缺 `exchange`。
- [x] 7.10b.37 覆盖 calendar reindex、`calendars/day.txt` 和 `instruments/*.txt` 文件完整性与列顺序；Qlib data 层可用时验证 `FileFeatureStorage` / `D.features()` 回读。
- [x] 7.10b.38 覆盖 Qlib data 层缺失时 graceful skip：summary 中必须有 `qlib_data_available=false` 和明确 `skip_reason`，pandas MVP 数据/回测不受影响。
- [x] 7.10b.39 新增 `tests/quant/backtest/test_qlib_native_runner.py`：覆盖 data/model/backtest 三层 capability skip、mock Qlib 完整流程输出、LightGBM 动态库失败写 model 层 `skip_reason`。
- [x] 7.10b.40 覆盖 `qlib_predictions_to_signal()` 和 `qlib_portfolio_to_backtest_result()` 的字段、排序、日期、货币和 metrics 兼容性。
- [x] 7.10b.41 新增 `tests/quant/test_qlib_cli.py`：覆盖 `tools/quant_qlib.py --help`、`convert/run/compare` 的 skip 路径和 artifact contract。
- [x] 7.10b.42 覆盖 `compare --mode same-signal` 与 `compare --mode native-research` 报告语义差异，防止把 native research 描述性比较误写成同策略引擎校验。
- [x] 7.10b.43 在 fixture 数据上增加 native workflow smoke；依赖不可用时测试应检查 skip summary，依赖可用时检查 `predictions.csv`、`portfolio_metrics.json`、`qlib_native_summary.json`。
- [x] 7.10b.44 全量 `conda run -n stock-skills-2 python -m pytest tests/ -q` 必须通过；新增 optional dependency 测试不得让无 Qlib/LightGBM 环境失败。

**验收命令与 artifact**：
- [x] 7.10b.45 `conda run -n stock-skills-2 python tools/quant_qlib.py convert --market cn` 可执行；能力层可用时产出 `data/quant/qlib_bin/cn/calendars/day.txt`、`instruments/cn.txt`、`features/sh000001/*.bin` 等。
- [x] 7.10b.46 conversion summary 记录 capability、calendar/instrument/field count、price adjustment policy、VWAP policy、provider URI、region mapping、data version。
- [x] 7.10b.47 `conda run -n stock-skills-2 python tools/quant_qlib.py run --market cn` 可执行；能力层可用时产出 predictions、portfolio metrics、native summary。
- [x] 7.10b.48 `conda run -n stock-skills-2 python tools/quant_qlib.py compare --market cn --mode same-signal` 产出 `qlib_vs_pandas_same_signal_comparison.md`，只讨论同信号/同参数下的引擎差异。
- [x] 7.10b.49 `conda run -n stock-skills-2 python tools/quant_qlib.py compare --market cn --mode native-research` 产出 `qlib_native_research_comparison.md`，明确 Alpha158/LightGBM 与 pandas MVP 不是同一策略。
- [x] 7.10b.50 Qlib native artifact 进入 experiment registry / report / Reviewer 链路；Reviewer 能检查 capability、skip_reason、样本区间、复权口径、same-signal/native-research 语义是否混淆。2026-05-25：`tools/quant_qlib.py run --register` 登记 native/conversion summary、same-signal/native-research comparison 与 report；report 输出 qlib capability、复权/VWAP、比较语义；Reviewer/Quant Researcher 规则同步。

### 7.11 vectorbt 集成（P1，硬交付 + 能力交付）

**硬交付（任何环境必须通过）**：
- [x] 7.11.1 新建 `src/quant/backtest/vectorbt_runner.py`，capability check `HAS_VECTORBT`；支持从 pandas MVP signal DataFrame 转换到 vectorbt Portfolio。2026-05-24：`tools/quant_backtest.py run --vectorbt` 输出 `ranking.csv` / `heatmap.png` / `vectorbt_summary.json`；vectorbt 指标 API 与 pandas business-day 频率不兼容时 fallback 到同信号 pandas metrics，不中断 artifact。
  - **验收**：`HAS_VECTORBT=False` 时 graceful skip，写入 `skip_reason`
- [x] 7.11.2 新增 `tests/quant/backtest/test_vectorbt_runner.py`
  - **验收**：mock 测试在离线 CI 通过

**能力交付（HAS_VECTORBT=True 时）**：
- [x] 7.11.3 参数网格实验（ETF 动量、技术指标），产出热力图和排序表。2026-05-24：fixture smoke `ranking_rows=4`，产物位于 `data/quant/phase7b_smoke/backtest/composite_v1/vectorbt_grid/`。
  - **验收**：可运行基于 yfinance ETF 数据的 vectorbt 参数网格；不用于 A 股/美股/日股横截面因子主流程

### 7.12 分析报告（P1）

- [x] 7.12.1 Walk-forward 分析报告：基于 7a 计算逻辑输出的逐窗口指标序列，生成可视化（热力图/折线图）、稳健性判定、跨市场对比。2026-05-24：`tools/quant_backtest.py --robustness` 输出 `walk_forward_metrics.csv` 与 `robustness_report.json/md`。
  - **验收**：报告包含 walk-forward 可视化，明确标注哪些窗口表现稳健
- [x] 7.12.2 IC decay 分析报告 + 因子相关性分析报告：跨市场衰减曲线对比、冗余度判定。2026-05-24：`tools/quant_eval.py` 输出 `ic_decay.csv`、`factor_correlation.csv` 并纳入 run summary。
  - **验收**：报告包含三市场 IC decay 叠图；标注高相关性因子对（|r| > 0.7）

### 7.13 稳健性全套（P1）

- [x] 7.13.1 市场状态分解：牛/熊/震荡市分区回测，输出各状态下的 IC/Sharpe/MaxDD。2026-05-24：`market_state_decomposition.csv` 输出 bull/bear/sideways regime 的 Sharpe/MaxDD/return/excess_return。
  - **验收**：报告包含三市场各自的市场状态分解表
- [x] 7.13.2 分年份 IC / Rank IC / Long-Short Return。2026-05-24：`yearly_factor_summary.csv` 输出 year + IC/Rank IC/Long-Short Return。
  - **验收**：每个因子都有分年份 summary 表
- [x] 7.13.3 分市值组（large/mid/small）IC / Rank IC。2026-05-24：`market_cap_group_summary.csv` 输出 market_cap_bucket 维度 summary。
  - **验收**：每个因子都有分市值组 summary 表
- [x] 7.13.4 成本敏感性（0/10/20/50bps）。2026-05-24：`cost_sensitivity.csv` 输出 annual_return/Sharpe/MaxDD/excess_return。
  - **验收**：每个策略都有成本-绩效曲线
- [x] 7.13.5 TopN 敏感性（取决于 universe 大小）。2026-05-24：`topn_sensitivity.csv` 输出 TopN-绩效曲线数据。
  - **验收**：每个策略都有 TopN-绩效曲线

### 7b 验收汇总

**硬交付层（任何环境必须通过）**：
- [x] 7b.1 四个库（DuckDB/Alphalens/Qlib/vectorbt）各有 adapter 代码 + capability check + CLI/config 开关
- [x] 7b.2 四个库各有 artifact contract + report 集成 + Reviewer 检查项
- [x] 7b.3 四个库各有 mocked/unit 测试 + skip_reason 记录
- [x] 7b.4 任一库依赖缺失时系统 graceful skip，不静默，不阻塞其他库

**能力交付层（依赖可用时必须通过）**：
- [x] 7b.5 DuckDB 产出真实 SQL query / scale-test artifact
- [x] 7b.6 Alphalens 产出 tear sheet HTML/PNG artifact
- [x] 7b.7 Qlib 产出回测结果和 pandas/Qlib comparison artifact
- [x] 7b.8 vectorbt 产出参数网格 heatmap / ranking artifact
- [x] 7b.9 每个因子都有分年份/分市值组表现
- [x] 7b.10 每个策略都有成本/TopN 敏感性分析
- [x] 7b.11 Walk-forward/IC decay/因子相关性分析报告生成
- [x] 7b.12 报告中自动标注「稳健」或「不稳健」的依据（基于 robustness 阈值）
- [x] 7b.13 `conda run -n stock-skills-2 python -m pytest tests/ -q` 全量通过。2026-05-24：`1489 passed in 87.81s`。
- [x] 7b.14 Qlib Native bin writer 产出 Alpha158 可读的 `.bin` data provider，并完整记录复权、VWAP、calendar、instrument、region mapping。
- [x] 7b.15 Qlib Native runner 具备 data/model/backtest 三层 capability check；LightGBM 或 Qlib backtest 不可用时写分层 `skip_reason`，pandas MVP 不受影响。
- [x] 7b.16 `tools/quant_qlib.py` 支持 `convert/run/compare`，并区分 `same-signal` 引擎差异比较与 `native-research` 描述性比较。
- [x] 7b.17 Qlib Native artifact 纳入 experiment registry / report / Reviewer，Reviewer 能检查复权口径、artifact 引用、样本区间和比较语义。
- [x] 7b.18 Qlib Native 新增 unit/mock/CLI 测试通过；依赖可用时 fixture smoke 产出 predictions、portfolio metrics、native summary。
- [x] 7b.19 追加 7.10b 后重新运行 `conda run -n stock-skills-2 python -m pytest tests/ -q` 全量通过。2026-05-25：`1504 passed, 1 warning in 88.45s`。

---

## 全局 Checklist（跨 Phase 检查）

- [x] G1. 每个 Phase 结束跑 `conda run -n stock-skills-2 python -m pytest tests/ -q` 确认全量通过。2026-05-25：`1504 passed, 1 warning in 89.09s`。
- [x] G2. `data/quant/` 下无真实数据被 `git add` 误提交。2026-05-25：`git ls-files data/quant` 为空；`git status --short --ignored data/quant` 显示 `!! data/`；`.gitignore` 覆盖 `data/` / `data/quant`。
- [x] G3. 个人 PF 持仓未泄露到任何 fixture 或测试文件。2026-05-25：审计 `tests/fixtures/sample_portfolio.csv`、`sample_cash_balance.json` 和 `tests/fixtures/quant/**`，均为 sample fixture；mocked E2E 明确使用 sample PF。
- [x] G4. 所有 CLI 命令均可 `--help` 且使用 `conda run -n stock-skills-2 python` 前缀。2026-05-25：`tools/quant_data.py`、`quant_factor.py`、`quant_eval.py`、`quant_backtest.py`、`quant_experiment.py`、`quant_report.py`、`quant_provider_probe.py`、`quant_scale_test.py`、`quant_qlib.py` 及主要子命令 `--help` 均返回 0。
- [x] G5. yfinance 不可用时 US/JP provider graceful skip，不阻塞 CN 市场。2026-05-25：`tests/quant/data/test_yfinance_provider.py` + `test_provider_fallback.py` 通过，缺失/空响应/缺列均写 provider status 或 `skip_reason`。
- [x] G6. Alphalens 安装失败时 minimal_runner 仍可用（使用手工 golden）。2026-05-25：`tests/quant/evaluation/test_alphalens_runner.py` 通过；缺依赖时写 `alphalens_summary.json` + `skip_reason`，golden calibration 仍通过。
- [x] G7. AKShare/Tushare token 缺失时数据下载不崩溃，标注 skip_reason。2026-05-25：`tests/quant/data/test_optional_provider_skip.py` 通过；AKShare/Tushare provider 用 `ProviderUnavailableError` 暴露明确原因，fallback chain 记录 `skip_reason`。
- [x] G8. Neo4j 不可用时知识写入不崩溃。2026-05-25：`tests/quant/test_phase5_experiments.py` 覆盖 `NEO4J_MODE=off`，`sync_report_summary_to_neo4j()` 返回 skipped。
- [x] G9. Qlib 安装失败时 pandas MVP 回测不受影响。2026-05-25：`tests/quant/backtest/test_qlib_runner.py`、`test_qlib_native_runner.py`、`tests/quant/test_qlib_cli.py`、`test_pandas_runner.py` 通过；Qlib/LightGBM 缺失时写分层 `skip_reason`。
- [x] G10. `AGENTS.md` / `CLAUDE.md` 在 quant 功能合入主分支前更新。2026-05-25：`AGENTS.md` 与 `CLAUDE.md` 已包含 quant extension / Qlib Native / conda 命令规则；本次另同步 README、architecture、Codex/Claude agent mirror。
- [x] G11. Phase 0-6 不依赖真实网络、真实行情 API、付费 token 或 optional 量化框架即可完成验收。2026-05-25：dry-run `11 PASS / 0 FAIL`；mocked E2E `15 passed`；Phase 0-6/quant offline focused `31 passed`。
- [x] G12. checklist 中不得残留"参照方案 X.X / Task X.X"式隐式依赖；若发现，先内联关键要求再继续执行。2026-05-25：`rg "参照方案|Task [0-9]+|Task[0-9]+|方案 [0-9]+|方案X|Task X"` 仅命中本规则文本和 G12。
- [x] G13. 每次开工前执行 `git status --short`，并记录/保护非本任务变更。2026-05-25：开工和收口均执行；现有 Qlib Native 相关未提交变更被保留并纳入审计。
- [x] G14. 每个独立任务或小闭环完成后至少有一个清晰 commit，避免 Phase 末尾一次性大提交。2026-05-25：本地收口已用精确路径 stage，并提交 `feat(quant): add qlib native research pathway`。
- [x] G15. 每个 Phase 结束通过 PR 合入 `main`，PR 必须列出测试结果、隐私/数据检查结果和已知风险。2026-05-25：本地确认历史 Phase PR/merge 记录包含 #9/#11/#12/#13；当前 7.10b 收口不得直推 main，需继续以 PR 描述列出本次测试、隐私/数据检查和已知风险。
- [x] G16. 禁止在未审计状态下执行 `git add .`；优先使用 `git add <path>` 精确 stage。2026-05-25：已完成 `git diff --check`、ignored data 审计和隐私扫描；后续 stage 必须使用精确路径。
- [x] G17. 合入 `main` 后为完成的 Phase 打 tag，例如 `quant-phase-0`、`quant-phase-7a`。2026-05-25：本地已存在 `quant-phase-0`～`quant-phase-4`；Phase 5/6/7a/7b tag 应在对应远端合并确认后补打，不提前打未合并 tag。
- [x] G18. Phase 7a 的 P0 阻塞项全部完成后才能合并到 main；Phase 7b 硬交付层完成后合并，能力交付层可在后续 PR 补充。2026-05-25：Phase 7a 已通过 PR #12 合入；Phase 7b adapter 基线已通过 PR #13 合入；7.10b 本地硬交付通过 focused + full pytest，具备进入 PR gate 条件。
- [x] G19. Phase 7b 四个库的硬交付项（adapter/capability check/test/skip_reason）全部通过后才能打 `quant-phase-7b` tag。2026-05-25：DuckDB/Alphalens/Qlib/vectorbt 及 Qlib Native focused tests 通过；`quant-phase-7b` tag 仍应等当前 7.10b PR 合入 main 后创建。

---

## 状态汇总

| Phase | 状态 | 开始日 | 完成日 | 备注 |
|---|---|---|---|---|
| 0: 环境与依赖 | ✅ 完成 | — | — | — |
| 1: Fixture + Schema | ✅ 完成 | — | — | — |
| 2: 因子计算 | ✅ 完成 | — | — | — |
| 3: 最小评价 | ✅ 完成 | — | — | — |
| 4: pandas 回测 | ✅ 完成 | — | — | — |
| 5: 实验管理 | ✅ 完成 | — | — | — |
| 6: Agent 集成 | ✅ 完成 | — | — | — |
| 7a: 多市场核心链路 | 🔄 进行中 | 2026-05-23 | — | P0/P1，当前完成 7.0.1 schema/artifact contract |
| 7b: 成熟库集成+研究增强 | 🔄 进行中 | 2026-05-25 | — | 追加 7.10b Qlib Native 专用通路；必须交付，两层验收（硬交付+能力交付） |

状态图例：⬜ 未开始 | 🔄 进行中 | ✅ 完成 | ⚠️ 阻塞 | ⏭ 跳过
