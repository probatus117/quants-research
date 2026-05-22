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
5. **增强可降级范围**：Phase 7。真实数据 provider、DuckDB、Alphalens、Qlib、行业/市值中性化、多市场和 vectorbt 均为 optional enhancement；失败时不得阻塞 Phase 0-6 MVP。
6. **optional dependency 规则**：所有 optional 包必须通过 `try/except ImportError` 或运行时 capability check graceful degradation。缺失时输出明确原因和替代路径。
7. **Phase 完成规则**：每个 Phase 结束更新顶部状态、勾选完成项，并运行该 Phase 指定测试；Phase 结束必须跑全量 pytest。
8. **版本控制规则**：实装过程中必须使用 Git/GitHub 工作流。提交代码前先检查隐私数据和本地产物，禁止未经审计的 `git add .`。

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

**增强路线**：Phase 7 的真实数据 provider、DuckDB、Alphalens、Qlib、行业/市值中性化、多市场、vectorbt 都是增强层。它们可以让系统更强，但任何一个失败都不能破坏 MVP。实现时优先 graceful skip、mock 测试和明确阻塞原因。

## Git/GitHub 工作流（Agent 必读）

**固定远端仓库**：自 2026-05-22 起，本量化扩展的 GitHub 远端统一使用 `probatus117/quants-research`（`https://github.com/probatus117/quants-research.git`）。后续 Codex/Agent 在执行 push、PR、issue、review、tag 或远端协作时，除非用户明确改目标仓库，均必须面向该仓库操作。

**工具边界**：本地 `git` 是代码变更的事实来源，用于 diff、stage、commit、branch、tag。GitHub 插件用于远端协作：创建 repo、issue、milestone、PR、读取 review/checks、追加评论。不要用 GitHub 插件替代本地 `git status` / `git diff` 审计。

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

**Phase 完成流程**：每个 Phase 结束必须更新 checklist 状态，运行该 Phase 指定测试和全量 `conda run -n stock-skills-2 python -m pytest tests/ -q`。通过后 push 分支到 GitHub，并用 GitHub 插件创建 PR。PR 描述必须包含：完成的 checklist 项、测试命令与结果、数据/隐私检查结果、已知风险、是否涉及 optional dependency。

**Review / Merge / Tag**：PR review 反馈在同一分支修复；不要在共享分支使用 `git reset --hard`。合入 `main` 后为阶段打 tag，例如 `quant-phase-0`, `quant-phase-1`。Phase 7 optional enhancement 可以单独 PR，不得混入 MVP 修复。

## CURRENT STATUS ⬇ (Agent 先读这里)

| 项目 | 状态 |
|---|---|
| **当前 Phase** | Phase 1：Fixture + 数据 Schema MVP |
| **目标 GitHub 仓库** | `probatus117/quants-research` |
| **第一个未完成** | 1.1.1 选定 50～100 只 A 股 sample |
| **已完成** | 29 / ~240 |
| **阻塞项** | 无 |
| **上次 pytest** | 2026-05-22：`1384 passed in 8.93s` |

> **Agent 操作**：从当前 Phase 的未完成条目开始执行。完成一项勾一项。遇到阻塞更新上方状态。Phase 结束跑 pytest。

**使用方式**：每完成一项，将 `[ ]` 改为 `[x]`。遇到阻塞，在行末标注 `⚠️ 阻塞：<原因>`。每个 Phase 结束后跑一次 `pytest` 确认不破坏现有测试。

---

## Phase 0：项目准备与依赖整理（2～3 天）

### 0.0 Git/GitHub 初始化

- [x] 0.0.1 执行 `git status --short`。如果返回 `fatal: not a git repository`，执行 `git init -b main` 初始化本地仓库；如果已经是 repo，只记录当前分支和未提交变更。
- [x] 0.0.2 审计 `.gitignore`：确认 `.env`、真实 API key、个人 PF/现金文件、真实行情产物、`data/quant/**` 本地产物不会被提交；审计前不得执行 `git add .`。
- [x] 0.0.3 创建 baseline commit：只在确认无隐私数据和本地产物会被提交后，提交当前项目基线，commit message 建议 `chore: baseline project before quant extension`。
- [x] 0.0.4 使用 GitHub 插件或 GitHub CLI 创建远端 repo（建议 private），添加 `origin` 并 push `main`。远端固定为 `probatus117/quants-research`，本地 `origin` 已配置为 `https://github.com/probatus117/quants-research.git`；`main` 和 `quant/phase-0-setup` 已 push。
- [x] 0.0.5 在 GitHub 创建 Milestones/Issues：Phase 0-6 作为 MVP milestone，Phase 7 作为 optional enhancement；每个 Phase 至少一个 issue，issue 描述链接本 checklist。已创建 `MVP Phase 0-6`、`Optional Phase 7` milestones，并创建 Phase 0-7 issues。
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

- [ ] 1.1.1 选定 50～100 只 A 股 sample（覆盖不同市值/行业），生成 `tests/fixtures/quant/sample_universe.csv`
- [ ] 1.1.2 下载 sample 股票的日线数据（2022-01-01 至 2024-12-31），生成 `tests/fixtures/quant/sample_daily_bar.csv`
- [ ] 1.1.3 下载/整理 sample 股票的 daily_basic（PE/PB/市值等），生成 `tests/fixtures/quant/sample_daily_basic.csv`
- [ ] 1.1.4 准备 sample 交易日历，生成 `tests/fixtures/quant/sample_calendar.csv`
- [ ] 1.1.5 确认 fixture 数据不包含个人 PF 真实持仓

### 1.2 Schema

- [ ] 1.2.1 新建 `src/quant/data/schema.py`：定义 `daily_bar`、`daily_basic`、`dim_security`、`calendar`、`universe_member` 标准字段和 dtypes
- [ ] 1.2.2 实现 schema 校验函数：检查必需字段、dtypes、日期格式、OHLC 合法性
- [ ] 1.2.3 新建 `tests/quant/data/test_schema.py`：验证 sample fixture 通过 schema 校验

### 1.3 Fixture Provider

- [ ] 1.3.1 新建 `src/quant/data/providers/base.py`：定义 Provider 抽象接口（`get_daily_bar()`, `get_daily_basic()`, `get_calendar()`, `get_universe()`）
- [ ] 1.3.2 新建 `src/quant/data/providers/fixture_provider.py`：从 `tests/fixtures/quant/` 读取数据，返回标准化 DataFrame
- [ ] 1.3.3 fixture_provider 不访问网络（可在 CI/离线环境运行）
- [ ] 1.3.4 新建 `tests/quant/data/test_fixture_provider.py`：验证返回格式、row count、date range、hash

### 1.4 Storage

- [ ] 1.4.1 新建 `src/quant/data/storage.py`：实现 `write_parquet()` 和 `read_parquet()`（先不用 DuckDB）
- [ ] 1.4.2 写入路径为 `data/quant/parquet/{table_name}/`
- [ ] 1.4.3 新建 `tests/quant/data/test_storage.py`：round-trip 读写验证

### 1.5 数据质量检查

- [ ] 1.5.1 新建 `src/quant/data/quality_check.py`：实现 OHLC 合法性、成交量非负、日期交易日校验、连续缺失天数、adj_close 跳变、股票池数量异常、fixture hash 一致性
- [ ] 1.5.2 新建 `tests/quant/data/test_quality_check.py`：用正常/异常 fixture 验证各检查项

### 1.6 CLI

- [ ] 1.6.1 `tools/quant_data.py` 实现 `update --source fixture` 命令（从 fixture 读取 → 写入 parquet）
- [ ] 1.6.2 `tools/quant_data.py` 实现 `check` 命令（运行 quality_check）
- [ ] 1.6.3 生成 `data/quant/data_version.json`（含 update_time、source、start/end_date、row_count、hash）

### 1.7 Phase 1 验收

- [ ] 1.7.1 不联网也能跑通所有 Phase 1 测试
- [ ] 1.7.2 daily_bar 字段标准化完成，fixture row count / date range 与预期一致
- [ ] 1.7.3 数据质量检查能输出可读报告
- [ ] 1.7.4 不读取个人 PF，不需要 API key
- [ ] 1.7.5 `conda run -n stock-skills-2 python -m pytest tests/quant/data/ -q` 全部通过
- [ ] 1.7.6 `conda run -n stock-skills-2 python -m pytest tests/ -q` 全部通过

---

## Phase 2：因子计算 MVP（1 周）

### 2.1 因子基类

- [ ] 2.1.1 新建 `src/quant/factors/base.py`：定义 `FactorConfig`、`FactorResult`、`BaseFactor.compute()`、`BaseFactor.validate_input()`、`BaseFactor.save()`
- [ ] 2.1.2 新建 `tests/quant/factors/test_base.py`：验证基类接口

### 2.2 Value 因子

- [ ] 2.2.1 新建 `src/quant/factors/value.py`：实现 `value_bp = 1 / PB`
- [ ] 2.2.2 PB <= 0 → NaN 处理
- [ ] 2.2.3 新建 `tests/quant/factors/test_value.py`：验证计算正确性、NaN 处理、边界值（PB=0, PB<0, PB 缺失）

### 2.3 Momentum 因子

- [ ] 2.3.1 新建 `src/quant/factors/momentum.py`：实现 `momentum_12_1 = adj_close[t-21] / adj_close[t-252] - 1`
- [ ] 2.3.2 处理上市不足 252 日的股票（应设 NaN 或标记 coverage_flag）
- [ ] 2.3.3 新建 `tests/quant/factors/test_momentum.py`：用已知价格序列验证计算、停牌/缺失处理、边界值

### 2.4 Low Volatility 因子

- [ ] 2.4.1 新建 `src/quant/factors/low_volatility.py`：实现 `lowvol_60d = - std(daily_return, 60)`
- [ ] 2.4.2 处理上市不足 60 日的股票
- [ ] 2.4.3 新建 `tests/quant/factors/test_lowvol.py`：验证方向（低波=高分）、波动率计算正确性

### 2.5 因子后处理

- [ ] 2.5.1 新建 `src/quant/factors/processing.py`：实现 winsorize（MAD, n=3）、zscore、rank percentile
- [ ] 2.5.2 行业/市值中性化暂不做（Phase 7），但 processing pipeline 预留接口
- [ ] 2.5.3 新建 `tests/quant/factors/test_processing.py`：验证 winsorize 极值处理、zscore 均值≈0 标准差≈1、percentile 范围

### 2.6 Factor Store

- [ ] 2.6.1 实现 factor_value.parquet 写入（date/symbol/factor_name/raw_value/winsorized_value/zscore/percentile/direction/universe）
- [ ] 2.6.2 生成因子覆盖率报告（每个因子每个日期的有效 symbol 数 / universe 总数）
- [ ] 2.6.3 生成因子分布图（直方图、按日期的时间序列）

### 2.7 CLI

- [ ] 2.7.1 `tools/quant_factor.py` 实现 `compute` 命令（从 storage 读取 → 计算 → 写入 factor store）

### 2.8 Phase 2 验收

- [ ] 2.8.1 3 个因子均输出 date-symbol 粒度结果
- [ ] 2.8.2 因子覆盖率与 sample fixture 的 expected coverage 一致
- [ ] 2.8.3 zscore 均值接近 0，标准差接近 1
- [ ] 2.8.4 异常 PE/PB 有 NaN 处理逻辑
- [ ] 2.8.5 同一 config 重跑结果一致
- [ ] 2.8.6 `conda run -n stock-skills-2 python -m pytest tests/quant/factors/ -q` 全部通过
- [ ] 2.8.7 `conda run -n stock-skills-2 python -m pytest tests/ -q` 全部通过

---

## Phase 3：最小单因子评价（1 周）

### 3.0 Golden 校准（优先完成）

- [ ] 3.0.1 新建 `tests/quant/evaluation/test_golden_calibration.py`
- [ ] 3.0.2 用 sample fixture 数据跑 Alphalens-reloaded（如果环境支持），将 `ic_summary` + `quantile_returns` 保存为 golden
- [ ] 3.0.3 如果 Alphalens 装不上，手工 numpy/pandas 计算预期 IC 和分组收益作为 golden
- [ ] 3.0.4 golden 数据存入 `tests/fixtures/quant/expected_ic_summary.json`
- [ ] 3.0.5 确认 minimal_runner 的 IC 均值/Rank IC 均值/分组收益均值与 golden 偏差 < 0.01
- [ ] 3.0.6 CI 中 minimal_runner 测试必须对比 golden，不得仅自洽通过

### 3.1 评价输入构造

- [ ] 3.1.1 新建 `src/quant/evaluation/input_builder.py`：合并 factor_value + adj_close → forward return DataFrame
- [ ] 3.1.2 实现 forward_return_5d / 20d / 60d 计算
- [ ] 3.1.3 新建 `tests/quant/evaluation/test_input_builder.py`

### 3.2 IC/Rank IC 分析

- [ ] 3.2.1 新建 `src/quant/evaluation/ic_analysis.py`：计算 IC Mean、IC Std、ICIR、Rank IC Mean、Rank ICIR、IC Positive Ratio
- [ ] 3.2.2 支持 multi-period（5d/20d/60d）
- [ ] 3.2.3 新建 `tests/quant/evaluation/test_ic_summary.py`

### 3.3 分组收益分析

- [ ] 3.3.1 新建 `src/quant/evaluation/quantile_analysis.py`：计算 5 分位 forward return、Long-Short Spread
- [ ] 3.3.2 支持 multi-period
- [ ] 3.3.3 新建 `tests/quant/evaluation/test_quantile_analysis.py`

### 3.4 最小评价 Runner

- [ ] 3.4.1 新建 `src/quant/evaluation/minimal_runner.py`：整合 input_builder + ic_analysis + quantile_analysis
- [ ] 3.4.2 实现 `min_coverage` 检查（默认 0.80，不满足时警告）
- [ ] 3.4.3 实现 coverage.json 输出

### 3.5 指标导出

- [ ] 3.5.1 新建 `src/quant/evaluation/exporter.py`：导出 `factor_summary.json`、`ic_timeseries.csv`、`quantile_returns.csv`、`coverage.json`

### 3.6 因子评价报告

- [ ] 3.6.1 新建 `src/quant/reports/factor_report.py`：生成 Markdown 报告（因子定义、数据区间、股票池、IC/Rank IC、分组收益、覆盖率、初步结论、风险提示）
- [ ] 3.6.2 新建 `tests/quant/evaluation/test_factor_report.py`

### 3.7 CLI

- [ ] 3.7.1 `tools/quant_eval.py` 实现 `run` 命令（调用 minimal_runner → export → report）

### 3.8 Phase 3 验收

- [ ] 3.8.1 momentum_12_1 能生成 IC/Rank IC 序列
- [ ] 3.8.2 能输出 5D/20D/60D forward return 分析
- [ ] 3.8.3 能输出五分位收益
- [ ] 3.8.4 minimal_runner 与 golden 偏差 < 0.01（test_golden_calibration 通过）
- [ ] 3.8.5 缺失数据过多时报告明确提示 coverage 问题
- [ ] 3.8.6 能输出 Markdown 报告
- [ ] 3.8.7 `conda run -n stock-skills-2 python -m pytest tests/quant/evaluation/ -q` 全部通过
- [ ] 3.8.8 `conda run -n stock-skills-2 python -m pytest tests/ -q` 全部通过

---

## Phase 4：pandas TopN 回测 MVP（1 周）

### 4.1 信号生成

- [ ] 4.1.1 新建 `src/quant/backtest/signal_builder.py`：实现单因子 score、多因子 composite score、score 标准化
- [ ] 4.1.2 composite_v1 公式：`0.34*bp_zscore + 0.33*momentum_zscore + 0.33*lowvol_zscore`
- [ ] 4.1.3 输出 `signal.parquet`
- [ ] 4.1.4 新建 `tests/quant/backtest/test_signal_builder.py`

### 4.2 Pandas 回测 Runner

- [ ] 4.2.1 新建 `src/quant/backtest/pandas_runner.py`：实现月频调仓、TopN 选择、等权持仓、组合净值计算、交易记录
- [ ] 4.2.2 实现过滤：exclude_st、exclude_suspended（根据 sample 数据可用字段）
- [ ] 4.2.3 排序规则：score 降序，选 TopN（默认 10）
- [ ] 4.2.4 调仓日：每月首个交易日
- [ ] 4.2.5 新建 `tests/quant/backtest/test_pandas_runner.py`：用已知价格和信号验证回测净值

### 4.3 成本模型

- [ ] 4.3.1 新建 `src/quant/backtest/cost_model.py`：buy_cost=0.0015, sell_cost=0.0025, min_cost=5
- [ ] 4.3.2 计算换手时的交易成本，从组合净值中扣除
- [ ] 4.3.3 新建 `tests/quant/backtest/test_cost_model.py`

### 4.4 回测指标

- [ ] 4.4.1 新建 `src/quant/backtest/metrics.py`：实现 annual_return、annual_volatility、sharpe、max_drawdown、calmar、turnover、excess_return、benchmark_return
- [ ] 4.4.2 benchmark 为 sample 等权组合
- [ ] 4.4.3 新建 `tests/quant/backtest/test_metrics.py`：用已知序列验证各指标计算

### 4.5 回测报告

- [ ] 4.5.1 新建 `src/quant/reports/backtest_report.py`：生成回测 Markdown 报告（策略参数、收益指标、风险指标、交易指标、收益曲线图、回撤图）
- [ ] 4.5.2 新建 `src/quant/reports/charts.py`：生成 equity_curve.png、drawdown.png、yearly_return.png

### 4.6 CLI

- [ ] 4.6.1 `tools/quant_backtest.py` 实现 `run` 命令（读取 config → signal → backtest → metrics → report）

### 4.7 Phase 4 验收

- [ ] 4.7.1 sample_a 月频回测可跑通
- [ ] 4.7.2 输出 portfolio_value.csv、positions.csv、trades.csv
- [ ] 4.7.3 输出 metrics.json（含所有指标）
- [ ] 4.7.4 输出收益曲线和回撤图
- [ ] 4.7.5 支持单因子和 composite score 两种输入
- [ ] 4.7.6 同一 config + data_version 重跑结果完全一致
- [ ] 4.7.7 `conda run -n stock-skills-2 python -m pytest tests/quant/backtest/ -q` 全部通过
- [ ] 4.7.8 `conda run -n stock-skills-2 python -m pytest tests/ -q` 全部通过

---

## Phase 5：实验管理与报告系统（1 周）

### 5.1 Experiment Registry

- [ ] 5.1.1 新建 `src/quant/experiments/registry.py`：实现 `create_experiment()`、`save_artifact()`、`update_status()`、`list_experiments()`、`get_experiment()`
- [ ] 5.1.2 experiment_id 格式：`EXP_YYYYMMDD_HHMMSS_{market}_{task_type}_{short_hash}`
- [ ] 5.1.3 status 流转：running → success / failed
- [ ] 5.1.4 实验目录结构：`data/quant/experiments/{experiment_id}/` 下存放 config.yaml、data_version.json、metrics.json、charts/、report.md

### 5.2 Config Hash

- [ ] 5.2.1 新建 `src/quant/experiments/config_hash.py`：计算 config + data_version 的确定性 hash
- [ ] 5.2.2 相同输入产生相同 hash（可复现性）

### 5.3 报告生成器

- [ ] 5.3.1 新建 `src/quant/reports/markdown_report.py`：支持 `factor_eval_report`、`backtest_report`、`experiment_compare_report` 三种模式
- [ ] 5.3.2 报告模板固定包含以下 7 节：
  1. 实验摘要
  2. 数据与股票池
  3. 因子/策略定义
  4. 核心指标
  5. 图表与 artifact
  6. 稳健性与风险提示
  7. 结论边界与下一步
- [ ] 5.3.3 所有关键数值必须从 metrics.json 读取，不在模板中写死

### 5.4 JSON/Neo4j 写入适配

- [ ] 5.4.1 report summary 写入 `data/history/quant/*.json`（与现有 `data/history/` 格式对齐）
- [ ] 5.4.2 Neo4j 写入为 optional：`try/except ImportError` + `NEO4J_MODE` 检查
- [ ] 5.4.3 Neo4j 不可用时 graceful degradation，不影响报告生成

### 5.5 CLI

- [ ] 5.5.1 `tools/quant_report.py` 实现 `generate` 命令
- [ ] 5.5.2 `tools/quant_experiment.py` 实现 `list`、`compare` 命令

### 5.6 Phase 5 验收

- [ ] 5.6.1 每次实验都有唯一 experiment_id
- [ ] 5.6.2 每次实验都能找到 config.yaml、data_version.json、metrics.json
- [ ] 5.6.3 报告中的关键数值能回溯到 metrics.json（不得有不来自 artifact 的数字）
- [ ] 5.6.4 Neo4j 不可用时不影响报告生成
- [ ] 5.6.5 `conda run -n stock-skills-2 python -m pytest tests/ -q` 全部通过

---

## Phase 6：Agent 集成（1 周）

### 6.1 Quant Researcher Agent 定义

- [ ] 6.1.1 新建 `.agents/agents/quant-researcher/agent.md`，角色边界必须自包含：
  - 负责：因子计算、因子评价、TopN 回测、实验查询、量化证据摘要。
  - 不负责：直接给买卖建议、替代 Strategist 做仓位/交易决策、编造未运行实验数字、用真实数据覆盖 fixture/mock 测试。
  - 输出要求：必须引用 `experiment_id`、artifact 路径和关键指标来源；样本不足、coverage 不足、数据源缺失时明确拒绝结论并列出需要补齐的数据。
  - 编排边界：纯量化问题可独立回答；策略/PF/个股问题只提供量化证据，最终投资建议由 Strategist 或 Analyst 综合。
- [ ] 6.1.2 新建 `.agents/agents/quant-researcher/examples.yaml`（覆盖类型 A/B/C/样品不足/降级 7 个 few-shot）
- [ ] 6.1.3 同步 `.claude/agents/quant-researcher/agent.md`（mirror）
- [ ] 6.1.4 同步 `.claude/agents/quant-researcher/examples.yaml`（mirror）

### 6.2 Routing

- [ ] 6.2.1 修改 `.agents/skills/stock-skills/routing.yaml`，新增 quant 相关 intent（纯量化/策略+量化/个股+因子暴露/实验查询）
- [ ] 6.2.2 同步 `.claude/skills/stock-skills/routing.yaml`（mirror）
- [ ] 6.2.3 更新 `src/orchestrator/dry_run.py::_expected_tools_for_agent()`，为 `quant-researcher` 增加工具列表

### 6.3 Orchestration

- [ ] 6.3.1 修改 `.agents/skills/stock-skills/orchestration.yaml`，新增 quant_on_strategy_question / quant_on_stock_analysis / quant_on_pf_diagnosis / quant_standalone / quant_failure 规则
- [ ] 6.3.2 同步 `.claude/skills/stock-skills/orchestration.yaml`（mirror）

### 6.4 Reviewer

- [ ] 6.4.1 在 Reviewer agent.md 中新增量化 Layer 1（artifact 完整性 12 项）+ Layer 2（引用一致性 4 项）检查清单
- [ ] 6.4.2 违规检查（Quant Researcher 输出买卖建议）设为 Reviewer auto trigger

### 6.5 config/tools.yaml

- [ ] 6.5.1 在 `config/tools.yaml` 中新增 `quant_factor.compute`、`quant_eval.run`、`quant_backtest.run`、`quant_report.generate`、`quant_experiment.list` 的函数登记

### 6.6 Strategist/Analyst 更新

- [ ] 6.6.1 更新 Strategist agent.md：追加「量化证据使用规则」（引用 experiment_id、标注矛盾、不倒编数字）
- [ ] 6.6.2 更新 Analyst agent.md：追加「因子暴露规则」（因子暴露放独立小节、不替代估值判断、标注无覆盖）

### 6.7 E2E 测试

- [ ] 6.7.1 新增 mocked E2E 场景：纯因子评价路由到 quant-researcher
- [ ] 6.7.2 新增 mocked E2E 场景：策略+量化路由到 quant-researcher → strategist chain
- [ ] 6.7.3 新增 mocked E2E 场景：样本不足时 quant-researcher 拒绝给出结论
- [ ] 6.7.4 dry-run 验证 routing 一致性

### 6.8 Phase 6 验收

- [ ] 6.8.1 Agent 正确路由到 quant-researcher（所有场景）
- [ ] 6.8.2 Quant Researcher 在所有场景下未输出买卖建议
- [ ] 6.8.3 类型 B 场景下 Strategist 正确引用量化证据（experiment_id + 指标）
- [ ] 6.8.4 Reviewer 能发现缺失的回测假设（Layer 1）和引用不一致（Layer 2）
- [ ] 6.8.5 样本不足时 Agent 明确拒绝给出结论
- [ ] 6.8.6 `conda run -n stock-skills-2 python tests/e2e/run_e2e.py --dry-run` 通过
- [ ] 6.8.7 `conda run -n stock-skills-2 python -m pytest tests/e2e/test_mocked.py -q` 通过
- [ ] 6.8.8 `conda run -n stock-skills-2 python -m pytest tests/ -q` 全部通过

---

## Phase 7：稳健性、扩展与增强（2～4 周，可选 / 不阻塞 MVP）

> Phase 7 是 optional enhancement。任一外部依赖、真实数据源、token、安装兼容性或数据质量问题失败时，必须 graceful skip 或标记阻塞原因，但不得影响 Phase 0-6 的 MVP 验收。

### 7.1 真实数据 Provider

- [ ] 7.1.1 新建 `src/quant/data/providers/akshare_provider.py`（实现 Provider 抽象接口）
- [ ] 7.1.2 新建 `src/quant/data/providers/baostock_provider.py`
- [ ] 7.1.3 新建 `src/quant/data/providers/tushare_provider.py`（无 token 时 graceful skip）
- [ ] 7.1.4 provider 可 mock（用于 CI 测试）
- [ ] 7.1.5 provider fallback 逻辑：主源失败 → 备源
- [ ] 7.1.6 新建 `tests/quant/data/test_provider_mock.py`

### 7.2 DuckDB 数据仓库

- [ ] 7.2.1 新建 `data/quant/quant.duckdb`
- [ ] 7.2.2 实现增量更新和 schema migration
- [ ] 7.2.3 实现 DuckDB → Parquet 查询接口

### 7.3 Alphalens Adapter

- [ ] 7.3.1 新建 `src/quant/evaluation/alphalens_runner.py`（optional dependency check）
- [ ] 7.3.2 生成 tear_sheet.html/png
- [ ] 7.3.3 对比 Alphalens 输出与 minimal_runner 输出（验证一致性）

### 7.4 Qlib Adapter

- [ ] 7.4.1 新建 `src/quant/data/qlib_converter.py`
- [ ] 7.4.2 新建 `src/quant/backtest/qlib_runner.py`（optional dependency check）
- [ ] 7.4.3 Qlib artifact 与 pandas artifact 对比验证

### 7.5 行业/市值中性化

- [ ] 7.5.1 实现 `factor_zscore_neutral = residual of regression: factor_zscore ~ industry_dummies + log_market_cap`
- [ ] 7.5.2 行业分类数据接入

### 7.6 稳健性分析

- [ ] 7.6.1 分年份 IC / Rank IC / Long-Short Return
- [ ] 7.6.2 分市值组（large/mid/small）IC / Rank IC
- [ ] 7.6.3 成本敏感性（0bps/10bps/20bps/50bps）
- [ ] 7.6.4 TopN 敏感性（Top10/Top20/Top30，取决于 sample 大小）
- [ ] 7.6.5 调仓频率敏感性（weekly/monthly/quarterly）

### 7.7 多市场扩展

- [ ] 7.7.1 日本股 yfinance provider
- [ ] 7.7.2 美股 yfinance provider
- [ ] 7.7.3 海外数据仅做价格类因子；财务因子需额外验证

### 7.8 vectorbt 补充

- [ ] 7.8.1 vectorbt 参数网格实验（ETF 动量、技术指标）
- [ ] 7.8.2 不用于 A 股主流程

### 7.9 Phase 7 验收

- [ ] 7.9.1 每个因子都有分年份表现
- [ ] 7.9.2 每个因子都有分市值组表现
- [ ] 7.9.3 每个策略都有成本敏感性分析
- [ ] 7.9.4 每个策略都有 TopN/调仓频率敏感性分析
- [ ] 7.9.5 报告中自动标注「稳健」或「不稳健」的依据
- [ ] 7.9.6 `conda run -n stock-skills-2 python -m pytest tests/ -q` 全部通过

---

## 全局 Checklist（跨 Phase 检查）

- [ ] G1. 每个 Phase 结束跑 `conda run -n stock-skills-2 python -m pytest tests/ -q` 确认全量通过
- [ ] G2. `data/quant/` 下无真实数据被 `git add` 误提交
- [ ] G3. 个人 PF 持仓未泄露到任何 fixture 或测试文件
- [ ] G4. 所有 CLI 命令均可 `--help` 且使用 `conda run -n stock-skills-2 python` 前缀
- [ ] G5. Qlib 安装失败时 P0~P4 功能不受影响
- [ ] G6. Alphalens 安装失败时 P0~P4 功能不受影响（使用手工 golden）
- [ ] G7. Tushare token 缺失时数据下载不崩溃
- [ ] G8. Neo4j 不可用时知识写入不崩溃
- [ ] G9. `docs/quant_architecture.md` 在 MVP 交付前完成
- [ ] G10. `AGENTS.md` / `CLAUDE.md` 在 quant 功能合入主分支前更新
- [ ] G11. Phase 0-6 不依赖真实网络、真实行情 API、付费 token 或 optional 量化框架即可完成验收
- [ ] G12. checklist 中不得残留“参照方案 X.X / Task X.X”式隐式依赖；若发现，先内联关键要求再继续执行
- [ ] G13. 每次开工前执行 `git status --short`，并记录/保护非本任务变更
- [ ] G14. 每个独立任务或小闭环完成后至少有一个清晰 commit，避免 Phase 末尾一次性大提交
- [ ] G15. 每个 Phase 结束通过 PR 合入 `main`，PR 必须列出测试结果、隐私/数据检查结果和已知风险
- [ ] G16. 禁止在未审计状态下执行 `git add .`；优先使用 `git add <path>` 精确 stage
- [ ] G17. 合入 `main` 后为完成的 Phase 打 tag，例如 `quant-phase-0`

---

## 状态汇总

| Phase | 状态 | 开始日 | 完成日 | 备注 |
|---|---|---|---|---|
| 0: 环境与依赖 | ⬜ 未开始 | — | — | — |
| 1: Fixture + Schema | ⬜ 未开始 | — | — | — |
| 2: 因子计算 | ⬜ 未开始 | — | — | — |
| 3: 最小评价 | ⬜ 未开始 | — | — | — |
| 4: pandas 回测 | ⬜ 未开始 | — | — | — |
| 5: 实验管理 | ⬜ 未开始 | — | — | — |
| 6: Agent 集成 | ⬜ 未开始 | — | — | — |
| 7: 增强与扩展 | ⬜ 未开始 | — | — | — |

状态图例：⬜ 未开始 | 🔄 进行中 | ✅ 完成 | ⚠️ 阻塞 | ⏭ 跳过
