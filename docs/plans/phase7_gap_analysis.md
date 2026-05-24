# Phase 7 计划文档不足点分析（多市场视角）

> 分析日期：2026-05-23
> 分析范围：三份计划文档（extension_plan / implementation_plan / implementation_checklist） 的 Phase 7 部分 vs 当前 Phase 6 完成后的项目现状
> 目标市场：**美股 + A 股 + 日股**（三市场同等优先级，非 A 股为主）

---

## 0. 核心结论

当前 `src/quant/` 量化研究链路（Phase 6 完成后）**完全不具备多市场能力**。它从数据 schema、Provider 接口、因子参数、回测引擎到报告模板，主要围绕合成 `sample_a` 数据和 A 股式 symbol / universe / 交易日假设构建；这不等于已经具备真实 A 股能力。三份计划文档的 Phase 7 将多市场放在 7.7 作为"可选扩展"，与用户真实目标（美/A/日三市场）严重错位。

**Phase 7 必须从"A 股优先 + 多市场可选"翻转为"多市场一等公民 + 单市场降级"才能支撑用户的真实研究需求。**

---

## 当前实现基线（Phase 6 完成后）

- **数据是纯合成的**：60 只假股票，假行业，假市值分组，随机价格序列。没有真实 ST、停牌、退市、复权事件。
- **量化链路的市场概念完全缺失**：`daily_bar` schema 没有 `market` 字段、Provider 接口没有 `market` 参数、因子参数硬编码了单一交易日假设（252 日窗口）、回测只认 `sample_a` 一个 universe。
- **`neutralize()` 是空函数**：`src/quant/factors/processing.py:38-45` 直接 `return df[value_column].copy()`。
- **回测只支持月频**：`pandas_runner.py:52` 硬编码 `if frequency != "monthly": raise ValueError`。
- **Provider 层只有 fixture**：没有真实数据源，更没有跨市场 provider。
- **Config 文件几乎为空**：`quant_factors.yaml` 仅 9 行，只列了 3 个因子名。
- **`zscore_neutral` 已计算但未持久化**：`store.py` 的 `FACTOR_VALUE_COLUMNS` 没包含该字段。

---

## 一、架构层面：缺少市场抽象层

### 1.1 整个量化链路没有 `market` 概念

当前数据流中 `market` 字段只在 experiment registry 的 ID 字符串中出现，`daily_bar`/`daily_basic` schema 没有 `market` 列，Provider 接口没有 `market` 参数。三市场数据一旦进入系统，无法区分来源。

**直接后果**：美/A/日三市场的行情不能放在同一个 parquet 目录下——它们有不同的交易日历、不同的 symbol 格式（AAPL / 000001.SZ / 7203.T）、不同的货币单位。没有 `market` 字段就无法做 cross-market join 或过滤。

### 1.2 交易日历是单市场的

`calendar` schema 只有一个 `(date, is_open)` 结构，没有 `market` 列。美国的感恩节/独立日、日本的山之日/天皇诞生日、中国的春节/国庆——三套休市日完全不同。当前 `quality_check.py` 的 `_check_dates_are_open()` 对所有数据使用同一个日历，三市场数据混在一起时会误报或漏报。

### 1.3 Symbol 格式没有跨市场规范

`schema.py:220` 的 `normalize_symbol()` 只处理 A 股六位数字补零（`000001`、`600000`）。美股的 ticker（`AAPL`、`BRK.B`）和日股的证券代码（`7203.T`、`9984.T`）格式完全不同。Provider 层没有 symbol 标准化映射，数据落地后可能出现同一股票在不同 provider 中 symbol 不一致的问题。

### 1.4 三份文档都把"市场"当成 Phase 7 末端的可选扩展

方案文档在 4.1 说"A 股为主，日本/美股为辅"，实现计划把多市场放在 P2，checklist 放在 7.7。但如果三市场是用户的真实目标，市场抽象必须在 Phase 7 的第一个任务完成——它决定了 schema、provider、因子参数、回测配置和报告模板的设计方式。

---

## 二、数据层面：Schema 与 Provider 的多市场断层

### 2.1 Schema 缺少多市场必要字段

对照三市场的实际数据需求，当前 schema 至少缺失：

| 缺失字段 | 需要原因 | 影响市场 |
|---|---|---|
| `market` | 区分同一 parquet 中不同市场的数据 | 全部 |
| `currency` | 回测净值需要统一计价货币 | 全部 |
| `delist_date` | 处理退市股，避免幸存者偏差 | 全部 |
| `dividend_yield` | 美股/日股股息率是重要估值指标 | US, JP |
| `total_share` / `float_share` | 市值中性化和流动性过滤 | 全部 |
| `exchange`（在 daily_bar 中） | 区分 NYSE/NASDAQ vs TSE vs SH/SZ | 全部 |
| `is_st` / `is_delisted` | 美股无 ST 概念但有 OTC/破产 | US |

### 2.2 Fixture Provider 只能返回单市场假数据

`fixture_provider.py` 硬编码了 `sample_daily_bar.csv` 等文件名，没有任何 `market` 参数。即使新增了 US/JP fixture 文件，也没有办法通过 `get_daily_bar(market="us")` 区分读取。

### 2.3 方案文档定义的 11 张标准表与当前实现差距过大

方案 6.1 列出了 `financial_statement`、`financial_indicator`、`index_member`、`industry_classification`、`suspension_limit` 等表；当前 schema 虽定义了 `universe_member`，但 fixture provider / `quant_data.py` 实际落地的核心表仍是 `daily_bar`、`daily_basic`、`dim_security`、`calendar`，没有真正的数据管线覆盖上述扩展表。这些表对跨市场因子研究至关重要——例如没有 `index_member` 就无法用沪深 300/S&P 500/日经 225 作为回测 benchmark。

### 2.4 缺少 PIT（Point-in-Time）数据策略

方案 16.1 提到 PIT 是风险点但 Phase 7 没有对应任务。三市场中 PIT 问题的表现形式不同：
- **A 股**：财报公告日与报告期截止日通常间隔 1-4 个月
- **美股**：SEC 申报截止日（10-K 60-90 天，10-Q 40-45 天）与季度末有明显延迟
- **日股**：财报周期与会计年度（3 月止）与中日美不同

pandas MVP 侧完全没有公告日过滤逻辑，如果直接用 `daily_basic.pe_ttm` 于调仓日，所有市场都存在未来函数。

### 2.5 缺少数据更新/修正的版本管理

方案和实现计划提到 DuckDB"增量更新"，但未讨论数据修正时（上市公司更正财报、除权除息调整、股票代码变更）实验如何追溯其使用的确切数据版本。跨市场场景下这个问题更严重——不同市场的休市日、复权方式和数据发布节奏各不相同。

---

## 三、因子层面：参数与处理假设全部 A 股硬编码

### 3.1 因子参数对各市场不同

| 因子 | 当前硬编码 | A 股 | 美股 | 日股 |
|---|---|---|---|---|
| `momentum_12_1` | 252 日窗口 | ~250 交易日/年 | ~252 交易日/年 | ~245 交易日/年 |
| `lowvol_60d` | 60 日窗口 | 约一个季度 | 同上 | 同上 |
| 月频调仓 | 每月首个交易日 | 适用 | 适用 | 适用 |
| 周频/季频调仓 | **不支持** | — | — | — |

当前 `momentum.py` 的 `shift(21)` 和 `shift(252)` 是固定交易日偏移，没有按市场交易日历做自适应。同一个因子在三市场需要不同的参数，但因子类（`Momentum121Factor`）没有任何 `market` 感知能力。

### 3.2 `neutralize()` 是空函数

`processing.py:38-45` 的行业/市值中性化直接返回原始值。三市场各自有不同的行业分类体系（申万/GICS/东证行业分类），中性化必须先解决行业分类数据接入问题。

### 3.3 缺少因子库扩展机制

方案第 8 节列出了 12 个因子，但当前因子硬编码在独立 `.py` 文件中。`config/quant_factors.yaml` 只是一个名字列表（9 行），代码完全不读取它。每增加一个因子都要同时改 config + 新建 `.py` + 手动注册。

对于三市场，有些因子是通用的（momentum, lowvol, bp），有些是市场特有的（A 股的 ST 过滤、美股的 dividend yield、日股的 cross-shareholding 调整）。没有一个 YAML 驱动的因子注册机制，市场特有因子的维护成本会乘 3。

### 3.4 缺少因子相关性/冗余度分析

三个 MVP 因子之间的 pairwise correlation 从未被检查。跨市场场景下，同一对因子的相关性可能在 A 股低、在美股高——这直接影响 composite score 的权重设计和策略的跨市场可移植性。

---

## 四、回测层面：引擎假设全部基于 A 股

### 4.1 回测只支持月频

`pandas_runner.py:52` 硬编码了 `if frequency != "monthly": raise ValueError`。Phase 7 需要支持 weekly/monthly/quarterly 三种调仓频率以适应三市场的不同研究需求（美股周频策略更常见，日股季频与财报周期对齐）。

### 4.2 缺少可配置 benchmark

当前 benchmark 是 sample 等权组合。三市场各自需要不同的 benchmark：
- A 股：沪深 300 / 中证 500
- 美股：S&P 500
- 日股：日经 225 / TOPIX

当前 Provider 接口没有 `get_index_member()` 或 `get_benchmark_return()` 方法，回测只能对比等权基准，无法计算真实超额收益。

### 4.3 缺少回测策略抽象接口

`pandas_runner.py` 只能做 TopN 等权。行业中性、TopK-Dropout、增强指数等策略变体没有可插拔的策略接口（如 `BaseStrategy.select()` / `BaseStrategy.weight()`）。

### 4.4 成本模型没有区分市场

当前成本模型（买入 15bps、卖出 25bps、最低 5 元）是 A 股假设。三市场的实际成本差异显著：
- A 股：印花税 5bps（卖出）、佣金 ~2.5bps、最低 5 元
- 美股：SEC 费 ~0.002%、佣金可忽略、无最低限制
- 日股：交易税 ~0.1%、佣金 ~0.1-0.3%

同一个回测在三市场应该使用三套成本参数。

### 4.5 缺少货币处理

回测净值当前以"元"为单位，没有货币标识。三市场回测如果都以 local currency 表示，Sharpe/MaxDD 这类基于收益率的指标仍可在谨慎前提下比较，但净值、收益金额、组合贡献、统一报告和跨市场合并组合都不能直接比较。需要一个 `base_currency` 参数和对应的汇率换算（至少在报告层面）。

---

## 五、Agent 与工具层面：Quant Researcher 停留在 Phase 6 契约

### 5.1 `quant_data` 没有正式 Agent 工具入口

`config/tools.yaml` 已登记 `quant_factor`、`quant_eval`、`quant_backtest`、`quant_report`、`quant_experiment`，但没有登记 `quant_data.update/check`。Quant Researcher 无法通过自然语言触发数据更新、质量检查和 provider 选择。三市场数据管理只能靠人工 CLI 命令，不进入 Agent 工作流。

### 5.2 Agent 契约仍以 fixture/mock/offline 为主

`.agents/agents/quant-researcher/agent.md` 第 2 步判断流程写的是"`fixture/mock/offline` 优先，真实 provider 仅作为 Phase 7 optional enhancement"。如果三市场研究是目标，Agent 必须能区分和输出三种模式：

- **真实数据研究**：引用 `data_version` + `provider_chain` + 市场
- **fixture 研究**：明确标注"合成数据，不构成研究结论"
- **降级研究**：标注缺失了哪些 provider、哪些市场、哪些字段

当前 agent.md 没有"市场"概念，所有输出示例都隐含是 A 股。

### 5.3 报告层不能承载多市场 artifact

`src/quant/reports/markdown_report.py` 的 7 节模板中，"稳健性与风险提示"节是固定文案，不读取 provider status、fallback 记录、robustness matrix、walk-forward 结果、benchmark 对比等 Phase 7 artifact。"数据与股票池"节不显示市场信息。跨市场对比报告 (`render_compare_report`) 只列出指标，不标注各实验的市场、货币和 benchmark。

### 5.4 Reviewer 只覆盖 Phase 6 的检查范围

Reviewer 的量化 Layer 1（12 项 artifact 完整性）和 Layer 2（4 项引用一致性）只针对 fixture 环境下的 factor_eval 和 backtest。Phase 7 新增的 provider fallback、PIT/未来函数风险、稳健性阈值（分年份/分市值/分市场）、benchmark 适当性、optional adapter 降级原因——全部没有对应检查项。

### 5.5 `CLAUDE.md` 与 `AGENTS.md` 不同步

`AGENTS.md` 已更新为仓库内 `docs/plans/...` 路径，但 `CLAUDE.md` 仍指向 `~/Downloads/...` 旧路径，且缺少部分 quant 架构说明。

---

## 六、测试层面：Phase 7 缺少防回归护栏

### 6.1 现有测试只覆盖 fixture/单市场路径

`tests/quant`、mocked E2E、dry-run 能验证 fixture provider → 因子 → 评价 → 月频回测 → report → routing 的稳定性，但完全不覆盖：
- 多市场数据加载（不同 calendar/symbol/货币）
- Provider fallback（主源失败 → 备源接管）
- 字段映射（中文列名 → 标准 schema）
- weekly/quarterly rebalance
- `zscore_neutral` store
- walk-forward / robustness report
- Phase 7 Reviewer 检查项
- optional adapter skip（Alphalens/Qlib 缺失时不崩溃）

### 6.2 Mock 的真实性不足

Checklist 7.1.4 只要求"provider 可 mock"，没有要求 mock 模拟真实 provider 的返回格式（AKShare 中文列名、Tushare 字段缺失、yfinance 美股 ticker 格式）、异常情况（网络超时、API 限流、返回空 DataFrame）。CI 通过的代码可能在真实三市场数据上直接崩溃。

---

## 七、文档层面：三份计划文档的 Phase 7 共性问题

### 7.1 任务粒度严重不均

Phase 7 在 2~4 周内要塞进：4 个 provider、DuckDB、Alphalens、Qlib、行业中性化、5 种敏感性分析、多市场、vectorbt。对比 Phase 2（仅 3 个因子排 1 周），工作量至少是 5-8 倍。在三市场目标下，还要叠加跨市场因子可比性、货币处理、benchmark 接入——实际工作量更大。

### 7.2 缺少依赖拓扑排序

```text
市场抽象（schema/provider接口改造）
  ──→ 真实数据 Provider（需要 market 参数）
    ──→ 行业中性化（需要真实行业分类 + 各市场行业体系映射）
      ──→ 稳健性分析（依赖中性化因子）
  ──→ Benchmark 接入（需要 index_member 数据）
    ──→ 超额收益计算（依赖 benchmark）
  ──→ 多市场因子参数校准（需要各市场交易日历）
```

文档没有给出可并行 vs 必须串行的划分。

### 7.3 "可降级"规则与 Phase 7 目标自相矛盾

Checklist 第 5 条说"Phase 7 失败时不得阻塞 Phase 0-6 MVP"。但如果三市场研究是核心目标，真实数据 provider、市场抽象和 benchmark 接入不应该全部是"可降级"的。需要区分 **Phase 7a（三市场核心链路）** 和 **Phase 7b（成熟库与研究增强链路）**。

### 7.4 Phase 7 子任务完全没有验收标准

Checklist 的 Phase 0-6 条目都有明确验证条件（"不联网也能跑通"、"与 golden 偏差 < 0.01"）。Phase 7 的条目全是 `[ ] 7.x.x 新建 xxx.py`，没有一条写了"什么情况算通过"。

### 7.5 缺少 Phase 7 的 E2E 测试条目

Phase 6 有 mocked E2E 场景。Phase 7 至少需要：provider fallback 集成测试、多市场数据加载 smoke test、跨市场对比报告生成测试、optional dependency graceful degradation 测试。

---

## 八、三份文档都未覆盖的关键缺口

### 8.1 缺少 Walk-Forward 分析

Walk-forward validation 是量化研究中最核心的过拟合检测手段之一。方案文档提了一次但未展开，实现计划放在 P3，checklist 完全没有。三市场各自的样本外表现验证必须依赖 walk-forward。

### 8.2 缺少因子衰减（IC Decay）分析

当前 IC 分析只在特定持有期（5D/20D/60D）上做点估计，缺少 IC 随持有期变化的衰减曲线。这直接关系调仓频率的选择，且三市场各自的衰减速度可能不同。

### 8.3 缺少市场状态分解

回测未区分牛/熊/震荡市。三市场在不同时期的牛熊节奏不同（A 股 2015 牛市 vs 美股 2020 牛市 vs 日股 2013 安倍经济学行情），因子在各个市场状态下的表现分解是跨市场因子评估的核心。

### 8.4 缺少起始日期敏感性分析

回测起始日期前后偏移 1-3 个月，结果是否稳定？三市场各自的时间序列长度不同（美股数据最长、A 股次之、日股介于中间），起始日期敏感性测试应该对各市场分别执行。

### 8.5 缺少复权口径一致性校验

不同 provider 的复权方式不同：AKShare 后复权、Tushare 前/后复权可选、yfinance 默认调整收盘价。三市场多 provider 场景下，如果复权口径不一致，因子值（尤其是 momentum）会完全不同。Phase 7 checklist 没有任何对应验证项。

### 8.6 缺少因子存储的版本管理

当前 `factor_value.parquet` 不追踪是用哪个版本的数据、哪个版本的因子代码计算的。三市场增量更新后，同一 experiment 引用的因子值和新数据会不一致。

---

## 九、改进建议

### A. 架构重构（Phase 7 启动前必做）

1. **在 schema 层引入 `market` 字段**：`daily_bar`、`daily_basic`、`calendar` 均增加 `market` 列（`cn`/`us`/`jp`）。这是三市场一切下游功能的前提。

2. **让 `market` 贯穿中间 artifact 与报告层**：不能只改原始行情表。`factor_value`、signal、`portfolio_value`、`positions`、`trades`、`metrics.json`、experiment registry、`render_compare_report` 的对比表都必须保留 `market` / `base_currency` / `benchmark`，否则数据进入 eval/backtest/report 后仍会丢失市场语义。

3. **改造 Provider 接口**：所有方法（`get_daily_bar`、`get_daily_basic`、`get_calendar`、`get_universe`）增加 `market` 参数。新增 `get_index_member()` 和 `get_benchmark_return()` 方法。

4. **新增 `MarketConfig` 数据类**：定义每个市场的交易日历规则、symbol 格式、货币、基准指数、默认成本参数、典型因子参数（如 momentum 窗口天数）。

5. **前置 Phase 7 artifact contract**：先定义所有下游必须读取的标准 artifact 字段。Provider、report、Reviewer 和 Agent 都围绕同一契约实现，避免先做 provider 后返工报告链路。由于 contract 中部分字段（如 `fallback_status`、`skip_reason`）的合法取值依赖 provider 的实际失败模式，建议分两层逐步固化：

   - **V0（Phase 7.0 定义，不依赖任何 provider）**：`market`、`data_version`、`base_currency`、`benchmark`
   - **V1（Phase 7.2 yfinance 跑通后补充）**：`provider_chain`、`fallback_status`、`skip_reason`

6. **扩展 `normalize_symbol()`**：支持美股 ticker（`AAPL`）和日股代码（`7203.T`）的标准化。

### B. 数据层（Phase 7a 核心）

7. **Phase 7.0：多市场 Schema 审计与外部数据假设验证**：用 yfinance probe 下载 10 只美股 + 10 只日股各 2 年数据，记录 schema 差异、字段缺失、覆盖率、空值率和 symbol/calendar/currency 差异，再扩展所有表的字段定义。日股覆盖度不要写成先验结论，而应在 Phase 7.0 产出 `provider_probe.json` / `coverage_report.json` 这类可审计 artifact，明确 yfinance 日股在大盘股、中小盘、创业板/成长市场上的真实可研究范围。

8. **三市场 fixture 各自独立，并前置到真实 provider 之前**：`tests/fixtures/quant/cn/`、`tests/fixtures/quant/us/`、`tests/fixtures/quant/jp/`，每个目录有独立的 `sample_daily_bar.csv`、`sample_calendar.csv` 等。Phase 7 的 schema、storage、factor、backtest、report 改造必须先能在三市场 fixture 上离线跑通。

9. **Phase 7 mocked E2E 前置**：在真实 provider 完整接入前，先增加自然语言触发三市场 fixture 研究、provider fallback、跨市场 compare report、optional adapter skip 的 mocked E2E，避免 Phase 7 关键路径只靠人工命令或真实网络验证。

10. **yfinance provider 优先实现**：目标市场仍是美股 + A 股 + 日股同等优先；实施顺序上可先用已有依赖 yfinance 打通 US/JP 两个真实市场，再接 CN provider。这样能最快验证多市场 schema、symbol、currency 和 calendar 设计是否成立。

11. **AKShare/Tushare provider 放到第二优先**：A 股 provider 在 yfinance 跑通之后再做，可以复用已稳定的多市场 schema 和接口。

12. **加入 PIT 公告日过滤**：财务和估值相关表至少增加 `period_end`、`announce_date`、`effective_date`、`source_updated_at` 字段。回测时过滤 `announce_date > trade_date` 或 `effective_date > trade_date` 的记录，并在 `data_version` 中记录 provider 修正时间。

13. **Phase 7.0 加入数据量预期与性能实测**：当前 fixture 是 60 股 × 782 日 ≈ 4.7 万行。三市场真实数据预期量级（仅 daily_bar）：A 股 ~5000 股、美股 ~6000 股、日股 ~4000 股，各 5-10 年历史，总量可达千万行级别。Phase 7a 每市场几百只股的 parquet 用 pandas 仍可处理，但应在 7.0 做 scale test（100/500/2000 股），记录 `pivot_table`/`groupby`/`merge` 的耗时、峰值内存和输出行数。DuckDB 是否进入关键路径应基于这个 artifact 判断，而不是只凭预期瓶颈判断。

### C. 因子层（Phase 7a 核心）

14. **因子参数按市场配置化**：`config/quant_factors.yaml` 中为每个因子定义各市场的参数（如 momentum 的 `lookback_days` 在 cn=252, us=252, jp=245）。

15. **让 YAML 配置真正驱动因子计算**：当前因子定义硬编码在 `.py` 文件中，config 形同虚设。需要因子注册机制使 YAML 配置与代码联动。

16. **实现 `neutralize()`**：先做单市场的行业中性化，再做跨市场的中性化对比。

17. **优先实现 `zscore_neutral` 的持久化**：`store.py` 中 `FACTOR_VALUE_COLUMNS` 加入 `zscore_neutral`，使 eval 和 backtest 都能通过 `--factor-column zscore_neutral` 直接使用。

### D. 回测层（Phase 7a 核心）

18. **解除月频硬编码**：支持 weekly/monthly/quarterly 三种调仓频率。

19. **benchmark 可配置**：回测 config 增加 `benchmark` 字段（`csi300`/`sp500`/`nikkei225`/`equal_weight`），metrics 计算超额收益。

20. **成本模型按市场参数化**：`CostConfig` 增加 `market` 字段，各市场使用各自的默认成本参数。

21. **设计回测策略抽象接口**：`BaseStrategy` 抽象类，TopN 等权 / 行业中性 / TopK-Dropout 作为实现。

22. **加入货币标识**：回测结果和报告中标注 `base_currency`。

### E. Agent / Reviewer / 报告层（Phase 7a 后半）

23. **Quant Researcher 增加三市场 agent mode**：区分 `真实数据研究` / `fixture 研究` / `降级研究`，输出中写明 market、provider_chain、data_version。

24. **登记 `quant_data.update/check` 为正式 Agent 工具**：加入 `config/tools.yaml` 和 `dry_run.py` 的 expected tools。

25. **报告模板升级**：`markdown_report.py` 的"稳健性与风险提示"节读取真实的 robustness artifact（分年份/分市值/分市场/Walk-forward/IC decay），不再输出固定文案。

26. **Reviewer Phase 7 检查项**：新增 provider status、PIT/未来函数风险、benchmark 适当性、robustness 阈值、跨市场可比性（货币/日历/会计周期）、optional adapter skip reason 检查。

27. **同步 Codex / Claude 文档**：更新 `AGENTS.md`、`CLAUDE.md` 中的 quant 架构说明和计划文档路径，确保 `.agents` 和 `.claude` 的 agent 定义一致。

### F. 测试层（贯穿 Phase 7）

28. **新增 Phase 7 单元测试**：provider mock/fallback、多市场 schema 校验、字段映射、weekly/quarterly rebalance、`zscore_neutral` 持久化、robustness report 渲染、optional dependency skip。

29. **新增 Phase 7 mocked E2E**：自然语言触发三市场数据研究、provider fallback 场景、稳健性报告生成、跨市场对比、Reviewer Phase 7 检查。

### G. Phase 7b：成熟量化库集成（必须交付，按两层验收）

> **定位修正**：三份原始计划文档将 DuckDB/Alphalens/Qlib/vectorbt 全部标记为"P2 可选"。但去掉这些成熟库后，系统长期只能用自研最小工具链跑朴素回测——这在研究可信度、策略多样性和数据规模上都有硬天花板。7b 不是"外围增强"，而是**将自研 MVP 接入行业标准技术栈，提升研究结论的可信度、可对比性和策略丰富度**。

#### G.0 Phase 7b 验收口径：目标必须交付，环境能力可降级但不可静默

这里的"必须交付"不等于要求每个外部库在所有 CI/本地环境中无条件安装成功，而是分两层验收：

- **硬交付层（任何环境都必须通过）**：每个库都要有 adapter、CLI/config 开关、capability check、artifact contract、report 读入、Reviewer 检查项、mocked/unit 测试和明确的 `skip_reason`。依赖缺失时可以 graceful skip，但必须留下可审计记录，不能静默跳过。
- **能力交付层（依赖可用时必须通过）**：在开发环境或明确标记的 integration 环境中，每个库至少跑通一个 golden/smoke 实验，产出真实 artifact，并进入 experiment registry / report / Reviewer 检查链路。若库安装或平台兼容性失败，必须记录失败类型、环境信息和替代路径。

因此，7b 的目标仍是**成熟库活用必须实现**；降级只解决"环境不可用时系统不崩"的问题，不应变成"库集成可以不做"的借口。

#### G.1 DuckDB：从 pandas 内存瓶颈到 SQL 驱动的大规模数据查询

**为什么必须做**：Phase 7a 的 scale test（100/500/2000 股）需要验证一个关键假设——当三市场各几千只股票、10 年级别日线数据加载到 pandas 时，`pivot_table`/`groupby`/`merge` 会在哪个规模开始接近内存或耗时上限。DuckDB 提供零拷贝 Parquet 查询、列式聚合和跨表 SQL join，使因子计算前的数据准备（时间序列过滤、横截面拼接、行业分类关联）不再完全受 pandas 单机内存限制。它不是"替代 pandas"，而是"在 pandas 之前做数据削减和关联"，计算后的 DataFrame 仍然交给 pandas 因子引擎。

**集成要点**：
- DuckDB 直接查询 `data/quant/parquet/` 下的分区 Parquet 文件，不额外维护数据副本
- 实现增量更新：新交易日数据 append → DuckDB 自动感知新 Parquet 文件
- SQL 驱动的 universe 构建：`SELECT symbol FROM daily_bar WHERE market='us' AND date BETWEEN ... AND avg(volume) > ...`
- DuckDB 不可用时自动 fallback 到 `pd.read_parquet()`，并写入 `skip_reason` / fallback artifact

#### G.2 Alphalens-reloaded：从自研最小评价到行业标准 tear sheet

**为什么必须做**：当前 `minimal_runner` 输出 IC 均值、分组收益和 coverage——这是有用但最小化的评价。Alphalens-reloaded 是量化因子的行业标准分析工具，其 tear sheet 包含 IC 衰减曲线、分位数收益热力图、换手率分析、因子自相关、事件研究——这些是因子研究论文和业界报告中约定俗成的可视化语言。没有 Alphalens tear sheet，研究成果无法与外部研究直接对比，也无法让 Reviewer 按行业惯例审核因子质量。

**Phase 3 golden 校准已经证明**：minimal_runner 的 IC 和分组收益输出与 Alphalens 一致（偏差 < 0.01）。7b 需要的是将 Alphalens 作为正式分析出口——输入 factor_value + forward_returns，输出完整 tear sheet HTML/PNG，作为实验 artifact 的一部分。

**集成要点**：
- `alphalens_runner.py`：`get_clean_factor_and_forward_returns()` → `create_full_tear_sheet()`
- 支持通过 `--alphalens` flag 或 config 开关触发
- 不可用时（`HAS_ALPHALENS=False`）fallback 到 minimal_runner 的 Markdown 报告，并写入 `skip_reason` / fallback artifact

#### G.3 Qlib (pyqlib)：从朴素 TopN 等权到工业级策略与组合管理

**为什么必须做**：当前 pandas 回测只能做 TopN 等权，调仓逻辑约 200 行代码。Qlib 提供：
- **策略库**：TopkDropoutStrategy、EnhancedIndexingStrategy、WeightStrategyBase 等已实现策略
- **风险模型**：协方差估计、因子模型、风险预算
- **组合优化**：均值-方差、风险平价、最大分散度
- **实验管理**：Qlib Recorder 自动记录参数、指标和模型 artifact
- **PIT 数据库**：Qlib 原生支持 point-in-time 数据组织，这是未来解决未来函数问题的关键基础设施

这些能力如果从零自研，每一项都需要数周到数月。Qlib 不是替代 pandas MVP，而是提供一条"标准答案"作为校准基准。只有在同一策略、同一 universe、同一成本模型、同一调仓日和同一复权口径下，pandas 与 Qlib 的结果才适合做数值一致性校验；如果比较的是 pandas TopN 等权与 Qlib TopkDropoutStrategy，则应输出差异解释，而不是用硬阈值判断对错。

**集成要点**：
- `qlib_converter.py`：`data/quant/parquet/` → Qlib `bin_data/` 格式
- `qlib_runner.py`：加载 Qlib config → 执行策略 → 输出 portfolio_value + metrics
- Qlib vs pandas 对比报告：同策略同参数时评估 Sharpe/MaxDD/annual_return 偏差；不同策略时输出差异解释、参数差异和不可比项
- 不可用（`HAS_QLIB=False`）时自动跳过，pandas MVP 独立工作，并写入 `skip_reason` / fallback artifact

#### G.4 vectorbt：从手工单策略回测到参数网格与快速实验

**为什么必须做**：当前每次回测运行一组参数，要跑成本敏感性（0/10/20/50bps × Top10/20/30/50 × weekly/monthly/quarterly = 60 种组合）需要手动循环或脚本。vectorbt 专为向量化参数扫描设计，可以在数秒内跑完数百组参数组合，输出热力图和排序表。它特别适合 ETF 动量策略、技术指标信号和少量资产组合实验——这些场景参数空间大、单次回测轻，手动遍历不可行。

**集成要点**：
- 用于 ETF/少量资产实验，不替代 A 股/美股/日股横截面因子主流程
- 可从 pandas MVP 的 signal DataFrame 直接转换到 vectorbt Portfolio
- 不可用（`HAS_VECTORBT=False`）时 graceful skip，并写入 `skip_reason` / fallback artifact

#### G.5 四库的协同价值

单独看，每个库解决一个点状问题。组合使用的协同效应是：

```text
DuckDB 削减数据 → pandas 因子引擎 → Alphalens 标准评价
                                    → Qlib 高级策略 + 风险模型
                                    → vectorbt 参数网格快速扫描
                                         ↓
                              所有 artifact 汇入 experiment registry
                              Reviewer 对比 pandas/Qlib/Alphalens 三方结论
```

这是从"一个自研回测脚本"到"可审计、可对比、可扩展的量化研究工作站"的升级。7a 保证了"能做"，7b 保证了"做得可信、做得全面"。

### H. 其他研究增强（Phase 7b）

30. **Walk-forward 分析报告**（7b）：基于 7a 计算逻辑输出的逐窗口指标序列，生成可视化（热力图/折线图）、稳健性判定、跨市场对比。

31. **因子相关性 + IC Decay 分析报告**（7b）：基于 7a 计算逻辑输出的相关性矩阵和衰减序列，生成可视化、冗余度判定、跨市场差异解读。

32. **市场状态分解**：牛/熊/震荡市分区回测，输出各状态下的 IC/Sharpe/MaxDD。

33. **稳健性全套**：分年份、分市值组、成本敏感性（0/10/20/50bps）、TopN 敏感性（取决于 universe 大小）。

---

## 十、建议执行顺序

```text
=== Phase 7a：多市场核心链路（P0/P1，必须交付）===

Phase 7.0  市场抽象 + artifact contract V0 + schema/coverage/scale probe + 三市场 fixture scaffold [P0 阻塞项]
Phase 7.1  三市场 fixture 数据 + mocked E2E + 下游 market 传播                         [P0 阻塞项]
Phase 7.2  yfinance provider（美股 + 日股）→ artifact contract V1                     [P0 阻塞项]
Phase 7.3  因子参数按市场配置化 + neutralize() + zscore_neutral 持久化                  [P0 阻塞项]
Phase 7.4  回测多频率支持 + benchmark + 成本按市场参数化 + Walk-forward/IC decay 计算逻辑 [P0 阻塞项]
Phase 7.5  AKShare/Tushare provider（A 股）+ provider fallback                         [P1]
Phase 7.6  Agent mode 升级 + 报告模板升级 + Reviewer 升级 + 文档同步                    [P1]
Phase 7.7  测试补齐（unit + mocked E2E）                                              [贯穿]

=== Phase 7b：成熟量化库集成 + 研究增强（必须交付）===
各库互相独立，可并行推进；adapter/report/Reviewer/skip 测试是硬交付，依赖可用时必须跑出真实 artifact；任一库安装失败时 graceful skip 并记录 skip_reason，不阻塞其他库集成。

Phase 7.8  DuckDB 集成：大规模数据查询 + 增量更新 + SQL universe 构建              [P1]
Phase 7.9  Alphalens-reloaded 集成：标准 tear sheet + 与 minimal_runner 交叉验证    [P1]
Phase 7.10 Qlib 集成：高级策略 + 风险模型 + 组合优化 + 与 pandas MVP 对比            [P1]
Phase 7.11 vectorbt 集成：参数网格 + ETF/技术信号快速实验                           [P1]
Phase 7.12 分析报告：Walk-forward + IC decay + 因子相关性 可视化与跨市场对比          [P1]
Phase 7.13 稳健性全套：市场状态分解 + 分年份/分市值/成本敏感性/TopN 敏感性            [P1]
```
