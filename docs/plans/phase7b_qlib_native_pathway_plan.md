# Qlib Native 专用通路实现计划

## 背景

当前项目有完整的数据管线（yfinance/AKShare → parquet）和自研 pandas 回测链路，但 Qlib 集成只做到了 CSV staging 和套壳 runner，无法使用 Qlib 的 Alpha158 因子库、LightGBM 模型训练和原生回测引擎。

目标：补齐 Qlib 专用通路，实现 `parquet → Qlib bin_data → Alpha158 → LightGBM → Qlib backtest` 全流程。

定位：这是现有 Phase 7.10 Qlib adapter 的 **7.10b Native 能力层**，不替代现有硬交付层。现有 `qlib_converter.py` / `qlib_runner.py` 继续保留审计壳、`skip_reason` 和 pandas 独立运行能力；native pathway 在 Qlib/LightGBM/Backtest 依赖可用时产出真实 Qlib artifact。

## 核心问题

Qlib 0.9.7 pip 包不带 `dump_bin` 脚本（只在 GitHub 源码仓库有），因此不能依赖外部转换脚本。实现策略：

1. 用 Qlib 已安装的 `FileFeatureStorage` 写 features `.bin` 文件。
2. `calendars/day.txt` 和 `instruments/*.txt` 手动写标准文本，避免 `FileInstrumentStorage` 在 Qlib 0.9.7 下写出列顺序不兼容的问题。
3. capability check 必须分层：`qlib_data_available`、`qlib_model_available`、`qlib_backtest_available`。`pyqlib` 可 import 不代表 LightGBM 或 Qlib backtest 能运行，任一层失败都要写明确 `skip_reason`。

## 需要处理的差异

| 环节 | 现有代码 | Qlib 要求 | 转换逻辑 |
|---|---|---|---|
| 数据格式 | Parquet | `.bin` 二进制 (float32 LE) | 自定义 bin writer |
| A股 symbol | `000001` | `sh000001` | exchange 列映射前缀 |
| 日股 symbol | `7203.T` | Qlib 可读取字符串 | 保留 `.T`，不剥后缀，避免和项目 schema/universe/report 不一致 |
| 复权 | pandas 用 `adj_close` | Qlib Alpha/label 直接读 `$close` | 写入调整后 OHLC/VWAP/close；同时写 `$factor = adj_close / close` |
| VWAP | `amount` (成交额) | `$vwap` | vwap = amount / volume |
| 涨跌幅 | pandas 可直接算收益 | Qlib Exchange 默认需要 `$change` | 写 `change.day.bin = adjusted_close.pct_change()` |
| calendar | parquet 可能缺停牌行 | Qlib feature index 按 calendar ordinal | 每只股票 reindex 到完整市场 calendar 后写 bin |
| instruments | 项目 universe | Qlib `instrument\tstart\tend` | 手动写 `instruments/{market_or_universe}.txt` |
| 因子 | 3 个自研因子类 | Alpha158 (158 个表达式) | 不需要对接，直接用 Qlib handler |
| 回测 | pandas TopN 等权 | TopkDropoutStrategy + Executor | 两条独立通路并行；比较报告区分同信号和 native research |

## 实施步骤

### Step 1: Bin Data Writer — `src/quant/data/qlib_bin_writer.py` (新文件)

直接调用 Qlib 的 `FileFeatureStorage` 写出标准 `.bin` 文件；calendar/instrument 文本手动写。

核心函数:

```
check_qlib_data_capability() → QlibCapability
  检查 pyqlib、FileFeatureStorage、qlib.init 是否可用

init_qlib_provider(output_market_dir, market) → None
  qlib.init(provider_uri={"day": str(output_market_dir)}, region=<cn/us>, expression_cache=None, dataset_cache=None)
  JP 暂无 Qlib REG_JP，默认 region="us"，并在 summary 记录 region_mapping

build_qlib_instrument_name(symbol, exchange, market) → str
  CN: '000001' + 'SH' → 'sh000001', '000001' + 'SZ' → 'sz000001'
  US: 'AAPL' → 'AAPL' 不变
  JP: '7203.T' → '7203.T'，保留项目标准 symbol

compute_adj_factor(daily_bar) → pd.Series
  adj_factor = adj_close / close，clip 到 [0.01, 100]

normalize_qlib_bar_fields(daily_bar) → pd.DataFrame
  factor = adj_close / close
  close = adj_close
  open/high/low = raw open/high/low * factor
  vwap = amount / volume * factor；amount/volume 缺失时用 adjusted typical price
  change = adjusted close pct_change by instrument
  field names 写入时不带 '$': open, high, low, close, volume, vwap, factor, change

build_calendar_index(calendar, daily_bar, market) → dict
  优先使用 parquet calendar 表；缺失时从 daily_bar 日期推导
  返回完整 calendar 和 date -> ordinal index

write_qlib_text_files(calendar, instruments, output_market_dir, market_or_universe) → dict
  calendars/day.txt: one date per line
  instruments/{market_or_universe}.txt: instrument<TAB>start_datetime<TAB>end_datetime

write_qlib_features(daily_bar, calendar, instruments, market, output_market_dir) → dict
  逐 instrument reindex 到完整 calendar 后写 features/{instrument}/{field}.day.bin
  使用 FileFeatureStorage(instrument, field, "day").write(values, index=first_calendar_idx)

convert_parquet_to_qlib_bin(parquet_root, output_dir, market, enabled) → QlibConversionResult
  全流程：读 parquet → 写 calendar.txt → 写 instruments.txt → 写 features .bin → 验证
  复用现有 QlibConversionResult dataclass
  Qlib data 层不可用时 graceful skip + skip_reason
```

写入目录建议：

```text
data/quant/qlib_bin/<market>/
  calendars/day.txt
  instruments/<market_or_universe>.txt
  features/<instrument>/<field>.day.bin
  qlib_conversion_summary.json
```

### Step 2: Qlib 配置文件 — `config/qlib/` (新目录)

三个 YAML 配置文件，定义 Qlib 的 handler / model / backtest 参数，按市场可覆写：

- `config/qlib/dataset.yaml` — Alpha158 handler 配置，label 定义、train/valid/test 时间分割。默认 label 建议显式写 `Ref($close, -20) / $close - 1`，不要依赖 Alpha158 默认 1 日 label。
- `config/qlib/model.yaml` — LightGBM 参数（默认 colsample=0.8, lr=0.05, max_depth=6, early_stopping=50, num_boost=500）
- `config/qlib/backtest.yaml` — TopkDropoutStrategy (topk=10, n_drop=2) + SimulatorExecutor，成本按市场从 MarketConfig 读取；CN 使用 `trade_unit=100`，US/JP 使用 `trade_unit=1` 或关闭交易单位约束。

### Step 3: Qlib Native Runner — `src/quant/backtest/qlib_native_runner.py` (新文件)

真正使用 Qlib 引擎的 runner，与 `qlib_runner.py`（套壳）平行存在：

```
QlibNativeCapability — 分层 capability (data/model/backtest available + skip_reason)
QlibNativeConfig     — 配置 dataclass (market, universe, top_n, n_drop, initial_capital, provider_uri)
QlibNativeResult     — 结果 dataclass (available, fallback_used, skip_reason, predictions, portfolio_metrics, ic_summary, artifacts)

check_qlib_native_capability(require_model=True, require_backtest=True) → QlibNativeCapability
  data: import qlib + storage 可用
  model: import LGBModel 且 lightgbm 动态库可加载
  backtest: import TopkDropoutStrategy + SimulatorExecutor + workflow records 可用

train_qlib_model(provider_uri, market, model_config, dataset_config) → (model, dataset)
  1. qlib.init(provider_uri)
  2. 实例化 Alpha158 handler
  3. 分割 train/valid/test
  4. 训练 LightGBM
  5. 返回 (trained_model, dataset_handler)

run_qlib_native_backtest(model, dataset, backtest_config, market) → portfolio_returns
  TopkDropoutStrategy + SimulatorExecutor

run_qlib_native_workflow(config, output_dir, enabled) → QlibNativeResult
  主入口，串联以上步骤
  任一 capability 层不可用时 graceful skip，并记录具体层级 skip_reason
```

同时包含结果桥接逻辑（不需要单独 bridge 文件）：
- `qlib_predictions_to_signal()` — Qlib 输出 → 标准 signal 格式
- `qlib_portfolio_to_backtest_result()` — Qlib 净值 → BacktestResult 兼容格式
- `write_qlib_native_summary()` — 写 `qlib_native_summary.json`，包含 capability、data_version、provider_uri、region_mapping、dataset_segments、model_params、backtest_params

### Step 4: CLI — `tools/quant_qlib.py` (新文件)

独立的 Qlib CLI，保持与 pandas backtest CLI 解耦：

```bash
# 转换数据为 Qlib .bin 格式
conda run -n stock-skills-2 python tools/quant_qlib.py convert --market cn

# 完整工作流（转换 + 训练 + 回测）
conda run -n stock-skills-2 python tools/quant_qlib.py run --market cn

# pandas vs Qlib 同信号/同参数对比：用于验证引擎差异
conda run -n stock-skills-2 python tools/quant_qlib.py compare --market cn --mode same-signal

# pandas MVP vs Qlib native research 对比：不同策略，只做描述性比较
conda run -n stock-skills-2 python tools/quant_qlib.py compare --market cn --mode native-research
```

### Step 5: 更新现有文件

- `qlib_converter.py` — `convert_parquet_to_qlib()` 保留（向后兼容），加 deprecation 指向新函数
- `qlib_runner.py` — `run_qlib_backtest()` 保留（pandas 对比路径），标记为 "compatibility runner"
- `tools/quant_data.py` `qlib-convert` — 暂不直接破坏旧 staging contract；新增 `--format csv|bin`，默认先保留 `csv`，native 稳定后再切 `bin`
- `config/tools.yaml` — 新增 `quant_qlib` 工具定义
- `.agents/agents/quant-researcher/agent.md` — 新增 qlib-run 命令和 few-shot
- `.claude/agents/quant-researcher/` — mirror 同步

### Step 6: 测试

- `tests/quant/data/test_qlib_bin_writer.py`
  - instrument name 映射：CN sh/sz、US unchanged、JP 保留 `.T`
  - 复权因子与 adjusted OHLC/VWAP 计算
  - `change.day.bin` 计算
  - calendar reindex 后 bin 写入+Qlib `D.features()` 回读验证
  - `calendars/day.txt` 和 `instruments/*.txt` 文件完整性与列顺序
  - Qlib data 层缺失时 graceful skip
- `tests/quant/backtest/test_qlib_native_runner.py`
  - data/model/backtest 三层 capability skip 测试
  - mock Qlib 完整流程输出验证
  - LightGBM import 动态库失败时写 model 层 `skip_reason`
  - signal/portfolio 格式转换
- `tests/quant/test_qlib_cli.py`
  - CLI help 输出
  - convert/run/compare 的 skip 路径
  - `compare --mode same-signal` 与 `compare --mode native-research` 报告语义不同

## 实施顺序

1. **qlib_bin_writer.py** — 先确保数据能被 Qlib 读取（独立可测试）
2. **bin writer 测试** — 验证 .bin 文件能通过 Qlib load 校验
3. **config/qlib/*.yaml** — 纯配置，无依赖
4. **qlib_native_runner.py** — 依赖 step 1/3
5. **tools/quant_qlib.py** — 依赖 step 1/4
6. **runner + CLI 测试**
7. **更新现有文件**（qlib_converter, qlib_runner, tools/quant_data.py, agent, tools.yaml）
8. **全量 pytest** — 1489 现有测试必须保持通过

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| Qlib API 兼容性 | 所有 Qlib 调用通过分层 capability + `try/except`，不可用时 graceful skip |
| LightGBM 动态库缺失 | `check_qlib_native_capability()` 单独捕获 model 层错误，例如 `libomp.dylib` 缺失 |
| .bin 格式不兼容 | 写入后立即用 `FileFeatureStorage` 和 `D.features()` 回读验证，不匹配则报错 |
| instruments 列顺序不兼容 | 不用 `FileInstrumentStorage` 写文件，手动写 `instrument\tstart\tend` |
| VWAP 缺少 | daily_bar 有 `amount` 列，用 amount/volume 计算 VWAP；缺失时用 adjusted typical price |
| exchange 列缺失 | CN 市场缺失 exchange 时硬报错（无法确定 sh/sz 前缀） |
| JP region 不被 Qlib 原生支持 | 保留 `.T` symbol，region 映射为 `us` 或 custom config，并在 summary 明确标记 |
| 复权口径不一致 | 写 adjusted OHLC/VWAP/close，同时保留 `$factor`；比较报告记录 price_adjustment_policy |
| 同策略/不同策略混淆 | `compare --mode same-signal` 才允许引擎差异判断；native research 只做描述性比较 |
| LightGBM 过拟合 | 训练/验证/测试严格按时间分割，不 shuffle |

## 验证

```bash
# 1. 数据转换
conda run -n stock-skills-2 python tools/quant_qlib.py convert --market cn
# 应产出 data/quant/qlib_bin/cn/calendars/day.txt, instruments/cn.txt, features/sh000001/*.bin 等
# summary 中记录 capability、calendar_count、instrument_count、field_count、price_adjustment_policy

# 2. 全量测试通过
conda run -n stock-skills-2 python -m pytest tests/ -q
# 目标：所有新增测试 + 1489 现有测试通过

# 3. 在 fixture 数据上跑完整 Qlib 工作流
conda run -n stock-skills-2 python tools/quant_qlib.py run --market cn
# 应产出 predictions.csv, portfolio_metrics.json, qlib_native_summary.json

# 4. Qlib vs pandas 同信号对比
conda run -n stock-skills-2 python tools/quant_qlib.py compare --market cn --mode same-signal
# 应产出 qlib_vs_pandas_same_signal_comparison.md

# 5. Qlib native research 描述性对比
conda run -n stock-skills-2 python tools/quant_qlib.py compare --market cn --mode native-research
# 应产出 qlib_native_research_comparison.md
```
