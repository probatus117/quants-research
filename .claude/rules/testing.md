---
paths:
  - "tests/**/*.py"
  - "tests/conftest.py"
  - "tests/fixtures/**"
---

# 测试开发规则

## 测试执行

```bash
# 单元测试(无需 API key / 网络)
conda run -n stock-skills-2 python -m pytest tests/ -q
conda run -n stock-skills-2 python -m pytest tests/core/test_ticker_utils.py -v
conda run -n stock-skills-2 python -m pytest tests/ -k "test_note"

# Dry-run: 验证 routing.yaml 与 agent 定义一致性(< 1 秒，无需 API key)KIK-746
conda run -n stock-skills-2 python tests/e2e/run_e2e.py --dry-run

# Mock E2E: pytest fixture stub tools 层(< 1 秒，无需 API key)KIK-747
conda run -n stock-skills-2 python -m pytest tests/e2e/test_mocked.py -q

# 真实 API E2E(用真实 API 验证 agent 行为，需需要 API key)
conda run -n stock-skills-2 python tests/e2e/run_e2e.py
conda run -n stock-skills-2 python tests/e2e/run_e2e.py e2e_001
```

## Worktree 设置(KIK-745)

开发用 worktree 使用专用 helper script 创建，不需要带入个人 PF:

```bash
bash scripts/setup_worktree.sh KIK-NNN feature-name
# -> 展开到 ~/stock-skills-kikNNN，并把 tests/fixtures/sample_portfolio.csv
#    复制为 data/portfolio.csv。不需要触碰个人 PF 的真实 symbol 和数量。
```

禁止执行 `cp ~/stock-skills/data/portfolio.csv`。误提交会泄露个人 PF，因此必须使用 `tests/fixtures/sample_portfolio.csv`(通用测试 symbol)。

## 测试结构

- `tests/core/`: core logic 单元测试(ticker_utils 等)
- `tests/data/`: 数据层测试(yahoo_client, grok_client, graph_store, note_manager 等)
- `tests/e2e/`: E2E agent 测试
- `tests/e2e/run_e2e.py`: 真实 API scenario runner；`--dry-run` 可无 API 验证
- `tests/e2e/test_mocked.py`: 基于 pytest fixture stub 的 mock E2E(KIK-747)
- `tests/e2e/test_scenarios.yaml`: scenario 定义
- `tests/conftest.py`: 共通 fixtures；`_block_external_io` autouse 自动 mock Neo4j / TEI / Grok
- `tests/fixtures/`: JSON/CSV 测试数据
- `stock_info.json` / `stock_detail.json`: 基于 Toyota 7203.T
- `sample_portfolio.csv` / `sample_cash_balance.json`: KIK-745 worktree 用

## Mock 方法

### autouse 自动 mock (`_block_external_io`)

- Neo4j: `_get_mode()` -> "off"，`is_available()` -> False
- TEI: `embedding_client.is_available()` -> False
- Grok: 删除 `XAI_API_KEY`
- reset mode cache(KIK-743)

### Mock E2E 的 stub 对象(test_mocked.py, KIK-747)

- `tools.llm.call_llm` -> 固定字符串响应
- `tools.yahoo_finance.get_stock_info / get_stock_detail / screen_stocks / get_price_history / get_macro_indicators` -> 从 `tests/fixtures/*.json` 返回
- `tools.grok.search_market / search_x_sentiment` -> 固定 dict
- 删除所有 API key(OPENAI/GEMINI/ANTHROPIC/XAI)

### sample fixture 使用

```python
SAMPLE_PORTFOLIO = REPO_ROOT / "tests/fixtures/sample_portfolio.csv"
positions = load_portfolio(str(SAMPLE_PORTFOLIO))  # 不读取个人 PF
```

## 编写测试注意点

- 每个测试必须可独立运行，且不依赖外部 API
- yahoo_client 调用必须 mock
- 测试数据优先复用 `tests/fixtures/`
- 新模块需要添加对应测试文件
- 新 agent 需要在 `tests/e2e/test_mocked.py` 添加 scenario(KIK-747)
- 修改 routing.yaml 后，用 `tests/test_kik746_dry_run.py::test_routing_yaml_integrity_passes_currently` 验证
