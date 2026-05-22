"""Tests for KIK-745 sample fixture + workflow safety."""

import csv
import json
import os
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PORTFOLIO = REPO_ROOT / "tests/fixtures/sample_portfolio.csv"
SAMPLE_CASH = REPO_ROOT / "tests/fixtures/sample_cash_balance.json"
SETUP_SCRIPT = REPO_ROOT / "scripts/setup_worktree.sh"
WORKFLOW_MD = REPO_ROOT / ".claude/rules/workflow.md"
GITIGNORE = REPO_ROOT / ".gitignore"


# ---------------------------------------------------------------------------
# 1. sample fixture exists + structure
# ---------------------------------------------------------------------------


def test_sample_portfolio_exists():
    assert SAMPLE_PORTFOLIO.is_file()


def test_sample_portfolio_has_required_columns():
    with SAMPLE_PORTFOLIO.open() as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) >= 5, "sample portfolio should have >= 5 rows"
    required = {"symbol", "shares", "cost_price", "cost_currency", "role"}
    assert required.issubset(set(reader.fieldnames or [])), (
        f"missing columns. expected {required}, got {reader.fieldnames}"
    )


def test_sample_portfolio_loads_via_load_portfolio():
    """src.data.portfolio_io.load_portfolio can read the sample."""
    from src.data.portfolio_io import load_portfolio
    positions = load_portfolio(str(SAMPLE_PORTFOLIO))
    assert len(positions) >= 5
    symbols = [p["symbol"] for p in positions]
    # Generic test symbols are included.
    assert any(s in ("AAPL", "MSFT", "7203.T") for s in symbols)


def test_sample_cash_balance_exists():
    assert SAMPLE_CASH.is_file()


def test_sample_cash_balance_is_hierarchical_kik742():
    """KIK-742 的階層形式SSoT 準拠和."""
    data = json.loads(SAMPLE_CASH.read_text())
    assert "total_jpy" in data
    assert "breakdown" in data
    assert isinstance(data["breakdown"], dict)
    # USD/JPY  amount key持
    for cur, entry in data["breakdown"].items():
        assert isinstance(entry, dict), f"breakdown.{cur} must be dict"
        assert "amount" in entry, f"breakdown.{cur} must have 'amount' key"


# ---------------------------------------------------------------------------
# 2. setup_worktree.sh
# ---------------------------------------------------------------------------


def test_setup_worktree_script_exists():
    assert SETUP_SCRIPT.is_file()


def test_setup_worktree_script_is_executable():
    assert os.access(SETUP_SCRIPT, os.X_OK), "setup_worktree.sh must be executable"


def test_setup_worktree_script_does_not_copy_personal_data():
    """個人 PF 文件（~/stock-skills/data/portfolio.csv）到的参照無和."""
    text = SETUP_SCRIPT.read_text()
    # 個人PFpath到的cp模式禁止
    assert "stock-skills/data/portfolio.csv" not in text or "sample" in text
    # sample_portfolio.csv 使和
    assert "sample_portfolio.csv" in text
    assert "sample_cash_balance.json" in text


# ---------------------------------------------------------------------------
# 3. workflow.md fix
# ---------------------------------------------------------------------------


def test_workflow_md_no_personal_pf_copy_instruction():
    """workflow.md does not contain personal PF copy instructions."""
    text = WORKFLOW_MD.read_text()
    bad_pattern = "cp ~/stock-skills/data/portfolio.csv"
    assert bad_pattern not in text, (
        f"workflow.md still contains personal PF copy pattern: {bad_pattern!r}"
    )


def test_workflow_md_mentions_sample_fixture():
    """workflow.md mentions sample fixture usage."""
    text = WORKFLOW_MD.read_text()
    assert "sample_portfolio.csv" in text
    assert "setup_worktree.sh" in text


def test_workflow_md_warns_against_personal_pf_copy():
    """workflow.md warns against copying personal PF data."""
    text = WORKFLOW_MD.read_text()
    assert "禁止" in text
    assert "泄漏" in text or "误" in text


# ---------------------------------------------------------------------------
# 4. .gitignore white列表
# ---------------------------------------------------------------------------


def test_gitignore_whitelists_sample_portfolio():
    text = GITIGNORE.read_text()
    assert "!tests/fixtures/sample_portfolio.csv" in text


def test_gitignore_whitelists_sample_cash_balance():
    text = GITIGNORE.read_text()
    assert "!tests/fixtures/sample_cash_balance.json" in text
