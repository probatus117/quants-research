"""Tests for session-start auto-invoke hard gate (KIK-741)."""

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
ROUTING_PATH = REPO_ROOT / ".claude/skills/stock-skills/routing.yaml"
SKILL_PATH = REPO_ROOT / ".claude/skills/stock-skills/SKILL.md"


def _load_routing():
    with ROUTING_PATH.open() as f:
        return yaml.safe_load(f)


def test_skill_description_mentions_session_start_keywords():
    """SKILL.md frontmatter description includes session-start keywords."""
    text = SKILL_PATH.read_text()
    frontmatter_end = text.find("---", 3)
    frontmatter = text[:frontmatter_end]
    assert "description:" in frontmatter
    desc_line = [l for l in frontmatter.splitlines() if l.startswith("description:")][0]
    for keyword in ["早上好", "早盘", "现状", "PF"]:
        assert keyword in desc_line, f"keyword '{keyword}' missing from SKILL.md description"


def test_skill_description_mentions_reconcile_hard_gate():
    """SKILL.md frontmatter mentions reconcile_session_state hard gate."""
    text = SKILL_PATH.read_text()
    frontmatter_end = text.find("---", 3)
    frontmatter = text[:frontmatter_end]
    desc_line = [l for l in frontmatter.splitlines() if l.startswith("description:")][0]
    assert "reconcile_session_state" in desc_line or "hard gate" in desc_line


def test_routing_morning_summary_has_pf_state_required():
    """All morning-summary entries have pf_state_required: true."""
    data = _load_routing()
    found = []
    for ex in data["examples"]:
        if ex.get("mode") == "morning-summary":
            assert ex.get("pf_state_required") is True, (
                f"pf_state_required missing on {ex.get('intent')}"
            )
            found.append(ex["intent"])
    assert len(found) >= 2, f"Expected ≥2 morning-summary entries, got {found}"


def test_routing_routine_daily_has_pf_state_required():
    """All routine-daily entries have pf_state_required: true."""
    data = _load_routing()
    found = []
    for ex in data["examples"]:
        if ex.get("mode") == "routine-daily":
            assert ex.get("pf_state_required") is True, (
                f"pf_state_required missing on {ex.get('intent')}"
            )
            found.append(ex["intent"])
    assert len(found) >= 3, f"Expected ≥3 routine-daily entries, got {found}"


def test_routing_routine_weekly_has_pf_state_required():
    """All routine-weekly entries have pf_state_required: true."""
    data = _load_routing()
    found = []
    for ex in data["examples"]:
        if ex.get("mode") == "routine-weekly":
            assert ex.get("pf_state_required") is True, (
                f"pf_state_required missing on {ex.get('intent')}"
            )
            found.append(ex["intent"])
    assert len(found) >= 3, f"Expected ≥3 routine-weekly entries, got {found}"


def test_routing_pf_health_check_has_pf_state_required():
    """PF / health check / stress-test entries have pf_state_required: true."""
    data = _load_routing()
    targets = ["PF 还好吗？", "做压力测试"]
    found = {i: False for i in targets}
    for ex in data["examples"]:
        if ex.get("intent") in targets:
            assert ex.get("pf_state_required") is True, (
                f"pf_state_required missing on {ex.get('intent')}"
            )
            found[ex["intent"]] = True
    assert all(found.values()), f"Some PF/HC intents missing: {found}"


def test_routing_strategist_pf_decisions_have_pf_state_required():
    """Investment decision entries have pf_state_required: true."""
    data = _load_routing()
    targets = [
            "给我调仓建议",
            "想改善 PF",
            "用计划模式",
            "这只股票该卖吗？",
            "应该止损吗？",
            "应该止盈吗？",
            "确认风险后找替代标的",
    ]
    found = {i: False for i in targets}
    for ex in data["examples"]:
        if ex.get("intent") in targets:
            assert ex.get("pf_state_required") is True, (
                f"pf_state_required missing on {ex.get('intent')}"
            )
            found[ex["intent"]] = True
    assert all(found.values()), f"Some strategist/PF-decision intents missing: {found}"


def test_routing_pf_state_NOT_on_pure_info_queries():
    """Pure info queries do not get pf_state_required."""
    data = _load_routing()
    info_intents = ["VIX 是多少？", "丰田怎么样？", "告诉我最新新闻", "研究一下半导体行业"]
    for ex in data["examples"]:
        if ex.get("intent") in info_intents:
            assert ex.get("pf_state_required") is not True, (
                f"pf_state_required should NOT be on info query: {ex.get('intent')}"
            )


def test_routing_yaml_pf_state_field_documented_in_header_comment():
    """routing.yaml header documents pf_state_required."""
    text = ROUTING_PATH.read_text()
    header_end = text.find("agents:")
    header = text[:header_end]
    assert "pf_state_required" in header, "pf_state_required field not documented in header comment"
    assert "KIK-741" in header, "KIK-741 reference missing in header comment"


def test_skill_md_session_start_section_intact():
    """SKILL.md keeps the Session Start State Reconcile section."""
    text = SKILL_PATH.read_text()
    assert "## Session Start State Reconcile" in text
    assert "reconcile_session_state" in text
    assert "pf_state_required" in text


def test_morning_intent_includes_extended_keywords():
    """Extended morning keywords are registered."""
    data = _load_routing()
    intents = [ex.get("intent") for ex in data["examples"]]
    assert "今天的状况" in intents
    assert "现状如何？" in intents
