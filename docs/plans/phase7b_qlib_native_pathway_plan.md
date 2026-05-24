# Qlib 专用通路实现计划

## 背景

当前项目有完整的数据管线（yfinance/AKShare → parquet）和自研 pandas 回测链路，但 Qlib 集成只做到了 CSV staging 和套壳 runner，无法使用 Qlib 的 Alpha158 因子库、LightGBM 模型训练和原生回测引擎。

目标：补齐 Qlib 专用通路，实现 `parquet → Qlib bin_data → Alpha158 → LightGBM → Qlib backtest` 全流程。

## 核心问题

Qlib 0.9.7 pip 包不带 `dump_bin` 脚本（只在 GitHub 源码仓库有），因此不能依赖外部转换脚本，必须用 Qlib 已安装的 `FileFeatureStorage` 直接写 `.bin` 二进制文件。

## 需要处理的差异

| 环节 | 现有代码 | Qlib 要求 | 转换逻辑 |
|---|---|---|---|
| 数据格式 | Parquet | `.bin` 二进制 (float32 LE) | 自定义 bin writer |
| A股 symbol | `000001` | `sh000001` | exchange 列映射前缀 |
| 复权 | `adj_close` | `$factor` (复权因子) | factor = adj_close / close |
| VWAP | `amount` (成交额) | `$vwap` | vwap = amount / volume |
| 因子 | 3 个自研因子类 | Alpha158 (158 个表达式) | 不需要对接，直接用 Qlib handler |
| 回测 | pandas TopN 等权 | TopkDropoutStrategy + Executor | 两条独立通路并行 |

## 实施步骤

### Step 1: Bin Data Writer — `src/quant/data/qlib_bin_writer.py` (新文件)

直接调用 Qlib 的 `FileFeatureStorage` / `FileCalendarStorage` / `FileInstrumentStorage` 写出标准 `.bin` 文件。

核心函数:

```
build_qlib_instrument_name(symbol, exchange, market) → str
  CN: '000001' + 'SH' → 'sh000001', '000001' + 'SZ' → 'sz000001'
  US: 'AAPL' → 'AAPL' 不变
  JP: '7203' → '7203' 不变（不加 .T）

compute_adj_factor(daily_bar) → pd.Series
  adj_factor = adj_close / close，clip 到 [0.01, 100]

write_qlib_features(daily_bar, calendar, instruments, market, output_dir) → dict
  逐 instrument 写出 features/{instrument}/{field}.day.bin
  field: $open, $high, $low, $close, $volume, $vwap, $factor
  VWAP = amount / volume；amount 缺失时用 (high+low+close)/3 近似

convert_parquet_to_qlib_bin(parquet_root, output_dir, market, enabled) → QlibConversionResult
  全流程：读 parquet → 写 calendar.txt → 写 instruments.txt → 写 features .bin → 验证
  复用现有 QlibConversionResult dataclass
  Qlib 不可用时 graceful skip + skip_reason
```

### Step 2: Qlib 配置文件 — `config/qlib/` (新目录)

三个 YAML 配置文件，定义 Qlib 的 handler / model / backtest 参数，按市场可覆写：

- `config/qlib/dataset.yaml` — Alpha158 handler 配置，label 定义 (20 日前瞻收益)，train/valid/test 时间分割
- `config/qlib/model.yaml` — LightGBM 参数（默认 colsample=0.8, lr=0.05, max_depth=6, early_stopping=50, num_boost=500）
- `config/qlib/backtest.yaml` — TopkDropoutStrategy (topk=10, n_drop=2) + SimulatorExecutor，成本按市场从 MarketConfig 读取

### Step 3: Qlib Native Runner — `src/quant/backtest/qlib_native_runner.py` (新文件)

真正使用 Qlib 引擎的 runner，与 `qlib_runner.py`（套壳）平行存在：

```
QlibNativeConfig  — 配置 dataclass (market, top_n, n_drop, initial_capital)
QlibNativeResult  — 结果 dataclass (predictions, portfolio_metrics, ic_summary, artifacts)

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
  Qlib 不可用时 graceful skip
```

同时包含结果桥接逻辑（不需要单独 bridge 文件）：
- `qlib_predictions_to_signal()` — Qlib 输出 → 标准 signal 格式
- `qlib_portfolio_to_backtest_result()` — Qlib 净值 → BacktestResult 兼容格式

### Step 4: CLI — `tools/quant_qlib.py` (新文件)

独立的 Qlib CLI，保持与 pandas backtest CLI 解耦：

```bash
# 转换数据为 Qlib .bin 格式
conda run -n stock-skills-2 python tools/quant_qlib.py convert --market cn

# 完整工作流（转换 + 训练 + 回测）
conda run -n stock-skills-2 python tools/quant_qlib.py run --market cn

# pandas vs Qlib 对比
conda run -n stock-skills-2 python tools/quant_qlib.py compare --market cn
```

### Step 5: 更新现有文件

- `qlib_converter.py` — `convert_parquet_to_qlib()` 保留（向后兼容），加 deprecation 指向新函数
- `qlib_runner.py` — `run_qlib_backtest()` 保留（pandas 对比路径），标记为 "compatibility runner"
- `tools/quant_data.py` `qlib-convert` — 指向新 bin writer
- `config/tools.yaml` — 新增 `quant_qlib` 工具定义
- `.agents/agents/quant-researcher/agent.md` — 新增 qlib-run 命令和 few-shot
- `.claude/agents/quant-researcher/` — mirror 同步

### Step 6: 测试

- `tests/quant/data/test_qlib_bin_writer.py` — instrument name 映射、复权因子计算、bin 写入+回读验证、calendar/instruments 文件完整性、Qlib 缺失时 graceful skip
- `tests/quant/backtest/test_qlib_native_runner.py` — 工作流 skip 测试、mock Qlib 的完整流程输出验证、signal/portfolio 格式转换
- `tests/quant/test_qlib_cli.py` — CLI help 输出、convert/run 的 skip 路径

## 实施顺序

1. **qlib_bin_writer.py** — 先确保数据能被 Qlib 读取（独立可测试）
2. **bin writer 测试** — 验证 .bin 文件能通过 Qlib load 校验
3. **config/qlib/*.yaml** — 纯配置，无依赖
4. **qlib_native_runner.py** — 依赖 step 1/3
5. **tools/quant_qlib.py** — 依赖 step 1/4
6. **runner + CLI 测试**
7. **更新现有文件**（qlib_converter, qlib_runner, agent, tools.yaml）
8. **全量 pytest** — 1489 现有测试必须保持通过

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| Qlib API 兼容性 | 所有 Qlib 调用通过 `check_qlib_capability()` + `try/except`，不可用时 graceful skip |
| .bin 格式不兼容 | 写入后立即用 `FileFeatureStorage` 回读验证，不匹配则报错 |
| VWAP 缺少 | daily_bar 有 `amount` 列，用 amount/volume 计算 VWAP |
| exchange 列缺失 | CN 市场缺失 exchange 时硬报错（无法确定 sh/sz 前缀） |
| LightGBM 过拟合 | 训练/验证/测试严格按时间分割，不 shuffle |

## 验证

```bash
# 1. 数据转换
conda run -n stock-skills-2 python tools/quant_qlib.py convert --market cn
# 应产出 data/quant/qlib_bin/cn/calendars/day.txt, instruments/cn.txt, features/sh000001/*.bin 等

# 2. 全量测试通过
conda run -n stock-skills-2 python -m pytest tests/ -q
# 目标：所有新增测试 + 1489 现有测试通过

# 3. 在 fixture 数据上跑完整 Qlib 工作流
conda run -n stock-skills-2 python tools/quant_qlib.py run --market cn
# 应产出 predictions.csv, portfolio_metrics.json, qlib_native_summary.json

# 4. Qlib vs pandas 对比
conda run -n stock-skills-2 python tools/quant_qlib.py compare --market cn
# 应产出 qlib_vs_pandas_comparison.md
```
