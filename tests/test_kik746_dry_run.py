"""Tests for KIK-746 dry-run orchestrator."""

import os
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# 1. verify_routing
# ---------------------------------------------------------------------------


def test_verify_routing_known_intent():
    from src.orchestrator import verify_routing
    r = verify_routing("有什么好股票？")
    assert r.passed
    assert "screener" in r.agents
    # 预期工具中包含 screen_stocks。
    assert any("screen" in t for t in r.expected_tools)


def test_verify_routing_chain_intent():
    from src.orchestrator import verify_routing
    r = verify_routing("这只股票该卖吗？")
    assert r.passed
    # 链式执行: risk-assessor → health-checker → strategist
    assert len(r.agents) >= 2
    assert "strategist" in r.agents


def test_verify_routing_unknown_intent_fails():
    from src.orchestrator import verify_routing
    r = verify_routing("！！！")
    assert not r.passed
    assert any("no matching" in e for e in r.errors)


def test_verify_routing_returns_header_for_chain():
    from src.orchestrator import verify_routing
    r = verify_routing("这只股票该卖吗？")
    # routing.yaml 中写有 header。
    assert r.header is not None and "→" in r.header


def test_verify_routing_no_llm_calls(monkeypatch):
    """删除全部 LLM API key 后 dry-run 仍可运行（证明没有调用 API）。"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)

    from src.orchestrator import verify_routing
    r = verify_routing("有什么好股票？")
    assert r.passed  # 通过 = 未调用 LLM/Web


def test_verify_routing_action_direct():
    """action: direct pattern 也能正确处理。"""
    from src.orchestrator import verify_routing
    r = verify_routing("记一下")
    assert r.passed
    # action flag 会被设置。
    assert r.flags.get("action") == "direct"


# ---------------------------------------------------------------------------
# 2. verify_routing_yaml_integrity
# ---------------------------------------------------------------------------


def test_routing_yaml_integrity_passes_currently():
    """当前 routing.yaml 没有重复或缺失项，应通过校验。"""
    from src.orchestrator import verify_routing_yaml_integrity
    report = verify_routing_yaml_integrity()
    assert report["passed"], (
        f"routing.yaml integrity FAILED: {report['errors']}"
    )


def test_routing_yaml_integrity_detects_intent_dup(tmp_path):
    """故意加入重复 intent 时应失败。"""
    from src.orchestrator import verify_routing_yaml_integrity

    bad = tmp_path / "routing.yaml"
    bad.write_text(yaml.safe_dump({
        "agents": {
            "screener": {"role": "test", "triggers": []},
        },
        "examples": [
            {"intent": "test_intent", "agent": "screener"},
            {"intent": "test_intent", "agent": "screener"},  # 重复
        ],
    }))
    report = verify_routing_yaml_integrity(routing_path=bad)
    assert not report["passed"]
    assert any("duplicate" in e for e in report["errors"])


def test_routing_yaml_integrity_detects_missing_agent(tmp_path):
    """引用不存在的 agent 时应失败。"""
    from src.orchestrator import verify_routing_yaml_integrity

    bad = tmp_path / "routing.yaml"
    bad.write_text(yaml.safe_dump({
        "agents": {},
        "examples": [
            {"intent": "test", "agent": "nonexistent-agent-xyz"},
        ],
    }))
    report = verify_routing_yaml_integrity(routing_path=bad)
    assert not report["passed"]
    assert any("nonexistent-agent-xyz" in e for e in report["errors"])


# ---------------------------------------------------------------------------
# 3. run_e2e.py --dry-run CLI
# ---------------------------------------------------------------------------


def test_run_e2e_dry_run_cli(monkeypatch):
    """run_e2e.py --dry-run 可以 import 并执行。"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)

    import sys
    sys.path.insert(0, str(REPO_ROOT))
    # 直接 import 并调用函数。
    from tests.e2e.run_e2e import run_dry_run
    success = run_dry_run()
    assert success, "dry-run must pass with current routing.yaml"
