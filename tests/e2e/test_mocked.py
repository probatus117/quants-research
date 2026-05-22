"""Mocked E2E tests (KIK-747).

将 LLM API / Yahoo Finance / Grok 全部 stub 化，以确定性方式验证
agent.md / examples.yaml / orchestrator 的行为。

使用方针:
- agent.md / examples.yaml / routing.yaml 使用真实文件
- 只 stub 外部 I/O（tools/llm.py, tools/grok.py, tools/yahoo_finance.py）
- 不触碰个人 PF（使用 tests/fixtures/sample_portfolio.csv，KIK-745）
- 全部场景 10 秒以内完成，且在 API key 全部删除的环境中也应通过
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_PORTFOLIO = REPO_ROOT / "tests/fixtures/sample_portfolio.csv"
SAMPLE_CASH = REPO_ROOT / "tests/fixtures/sample_cash_balance.json"
STOCK_INFO_FIXTURE = REPO_ROOT / "tests/fixtures/stock_info.json"
STOCK_DETAIL_FIXTURE = REPO_ROOT / "tests/fixtures/stock_detail.json"


# ---------------------------------------------------------------------------
# Mock fixtures (autouse for this module)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mocked_e2e_env(monkeypatch, tmp_path):
    """Stub LLM / Yahoo Finance / Grok and disable real API keys.

    既有的 `_block_external_io` (conftest.py) 已处理 Neo4j/TEI/Grok，
    这里额外 stub LLM 和 Yahoo Finance。
    """
    # 1) 删除 API keys（物理阻断真实调用的最后防线）
    for k in ("OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)

    # 2) LLM stub
    def _stub_call_llm(provider, model, prompt, **kwargs):
        return f"[mock:{provider}] {prompt[:50]}... → 建议关注: 7203.T (PER 10.5)"

    monkeypatch.setattr("tools.llm.call_llm", _stub_call_llm)

    # 3) Yahoo Finance stub: 从 fixtures 返回
    stock_info = json.loads(STOCK_INFO_FIXTURE.read_text())
    stock_detail = json.loads(STOCK_DETAIL_FIXTURE.read_text())

    def _stub_get_stock_info(symbol):
        d = dict(stock_info)
        d["symbol"] = symbol
        return d

    def _stub_get_stock_detail(symbol):
        d = dict(stock_detail)
        d["symbol"] = symbol
        return d

    def _stub_screen_stocks(query=None, max_results=10):
        return [
            {"symbol": "7203.T", "shortName": "Toyota Motor",
             "trailingPE": 10.5, "exchange": "JPX"},
            {"symbol": "6758.T", "shortName": "Sony Group",
             "trailingPE": 18.2, "exchange": "JPX"},
        ][:max_results]

    def _stub_get_price_history(symbol, period="3mo"):
        import pandas as pd
        # 简化的上升趋势序列
        prices = [2500 + i * 5 for i in range(60)]
        return pd.DataFrame({
            "Open": prices,
            "High": [p + 10 for p in prices],
            "Low": [p - 10 for p in prices],
            "Close": prices,
            "Volume": [1_000_000] * 60,
        })

    def _stub_get_macro_indicators():
        return {"VIX": 18.5, "USDJPY": 159.0, "BTC": 95000}

    monkeypatch.setattr("tools.yahoo_finance.get_stock_info", _stub_get_stock_info)
    monkeypatch.setattr("tools.yahoo_finance.get_stock_detail", _stub_get_stock_detail)
    monkeypatch.setattr("tools.yahoo_finance.screen_stocks", _stub_screen_stocks)
    monkeypatch.setattr("tools.yahoo_finance.get_price_history", _stub_get_price_history)
    monkeypatch.setattr("tools.yahoo_finance.get_macro_indicators", _stub_get_macro_indicators)

    # 4) Grok stub
    def _stub_search_market(query):
        return {
            "summary": f"[mock] {query} 市场状态: 中性",
            "macro_factors": ["利率维持不变", "VIX 18.5"],
            "sentiment": {"score": 0.0, "summary": "neutral"},
        }

    def _stub_search_x_sentiment(symbol, name):
        return {
            "score": 0.3,
            "summary": f"[mock] {symbol} sentiment: 偏强",
            "positive": ["EPS 增长"],
            "negative": ["PER 偏高"],
        }

    monkeypatch.setattr("tools.grok.search_market", _stub_search_market, raising=False)
    monkeypatch.setattr("tools.grok.search_x_sentiment", _stub_search_x_sentiment, raising=False)

    # 5) 将 sample fixtures 复制到 data/（应对 agent 直接读取 data/ 的情况）
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "portfolio.csv").write_text(SAMPLE_PORTFOLIO.read_text())
    (data_dir / "cash_balance.json").write_text(SAMPLE_CASH.read_text())
    monkeypatch.setenv("STOCK_SKILLS_DATA_DIR", str(data_dir))


# ---------------------------------------------------------------------------
# Scenario tests (按场景验证行为)
# ---------------------------------------------------------------------------


def test_scenario_screener_routing():
    """e2e_001: 中文选股请求 -> screener，并返回预期工具。"""
    from src.orchestrator import verify_routing
    r = verify_routing("有什么好股票？")
    assert r.passed
    assert r.agents == ["screener"]
    assert any("screen" in t for t in r.expected_tools)


def test_scenario_screener_yahoo_call_returns_mocked_data():
    """screener 调用的 screen_stocks 应返回 mock 响应。"""
    from tools.yahoo_finance import screen_stocks
    result = screen_stocks(max_results=5)
    assert isinstance(result, list)
    assert len(result) >= 1
    assert result[0]["symbol"] == "7203.T"


def test_scenario_analyst_routing_and_data():
    """e2e_002: 中文丰田分析请求 -> analyst + stock_info。"""
    from src.orchestrator import verify_routing
    from tools.yahoo_finance import get_stock_info, get_stock_detail

    r = verify_routing("丰田怎么样？")
    assert r.passed
    assert r.agents == ["analyst"]

    info = get_stock_info("7203.T")
    detail = get_stock_detail("7203.T")
    assert info["symbol"] == "7203.T"
    # 包含 PER 等主要指标（经由 fixture）
    assert "per" in info or "trailingPE" in info


def test_scenario_health_checker_uses_sample_portfolio():
    """e2e_003: PF 确认类请求应读取 sample_portfolio。"""
    from src.data.portfolio_io import load_portfolio
    positions = load_portfolio(str(SAMPLE_PORTFOLIO))
    assert len(positions) >= 5
    symbols = [p["symbol"] for p in positions]
    assert "AAPL" in symbols  # sample fixture 中的标的
    # 不包含个人 PF 标的
    assert all(s not in symbols for s in ("9856.T",))  # 9856.T 不在 sample 中


def test_scenario_researcher_grok_returns_mock():
    """e2e_004: researcher 的 grok 调用应返回 mock 响应。"""
    from tools.grok import search_market

    result = search_market("中国用户关注的日本股票市场")
    assert "[mock]" in result["summary"]
    assert "sentiment" in result


def test_scenario_strategist_chain_routing():
    """e2e_006: 中文 PF 改善请求会路由到链式执行（HC→strategist）。"""
    from src.orchestrator import verify_routing
    r = verify_routing("我想改善PF")
    assert r.passed
    assert "health-checker" in r.agents
    assert "strategist" in r.agents
    # history_check flag 会被设置（KIK-740）
    assert r.flags.get("history_check") is True


def test_scenario_sell_decision_with_history_check():
    """e2e_007: 中文卖出判断请求会带 history_check + review。"""
    from src.orchestrator import verify_routing
    r = verify_routing("这只股票该卖吗？")
    assert r.passed
    assert r.flags.get("history_check") is True
    assert r.flags.get("review") is True
    # 3 agent 链式执行（risk-assessor → HC → strategist）
    assert len(r.agents) == 3


# ---------------------------------------------------------------------------
# Smoke tests (用于 CI sanity check 的快速通过测试)
# ---------------------------------------------------------------------------


def test_no_api_keys_present():
    """确认 API keys 已删除（验证 fixture 生效）。"""
    for k in ("OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY"):
        assert os.environ.get(k) is None, f"{k} should be removed by fixture"


def test_llm_stub_returns_mock_string():
    """tools.llm.call_llm 应返回 stub 响应。"""
    from tools.llm import call_llm
    result = call_llm("gpt", "gpt-5.5", "测试 prompt")
    assert "[mock:gpt]" in result
