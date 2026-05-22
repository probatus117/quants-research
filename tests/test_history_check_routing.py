"""Tests for History Check routing flag (KIK-740)."""

from pathlib import Path

import yaml


ROUTING_PATH = Path(__file__).resolve().parent.parent / ".claude/skills/stock-skills/routing.yaml"
SKILL_PATH = Path(__file__).resolve().parent.parent / ".claude/skills/stock-skills/SKILL.md"
ORCHESTRATION_PATH = Path(__file__).resolve().parent.parent / ".claude/skills/stock-skills/orchestration.yaml"


def _load_routing():
    with ROUTING_PATH.open() as f:
        return yaml.safe_load(f)


def test_routing_yaml_loads():
    """routing.yaml is valid YAML and has examples."""
    data = _load_routing()
    assert "examples" in data
    assert isinstance(data["examples"], list)
    assert len(data["examples"]) > 0


def test_history_check_added_to_sell_decisions():
    """卖出/止损/止盈 decisions have history_check: true."""
    data = _load_routing()
    sell_intents = ["这只股票该卖吗？", "应该止损吗？", "应该止盈吗？"]
    found = {i: False for i in sell_intents}
    for ex in data["examples"]:
        if ex.get("intent") in sell_intents:
            assert ex.get("history_check") is True, f"history_check missing on {ex.get('intent')}"
            found[ex["intent"]] = True
    assert all(found.values()), f"Some sell-decision intents missing: {found}"


def test_history_check_added_to_replacement():
    """调仓/PF 改善类 intent have history_check: true."""
    data = _load_routing()
    targets = ["给我调仓建议", "想改善 PF", "用计划模式", "确认风险后找替代标的"]
    found = {i: False for i in targets}
    for ex in data["examples"]:
        if ex.get("intent") in targets:
            assert ex.get("history_check") is True, f"history_check missing on {ex.get('intent')}"
            found[ex["intent"]] = True
    assert all(found.values()), f"Some replacement intents missing: {found}"


def test_history_check_NOT_on_info_queries():
    """Info queries do not get history_check."""
    data = _load_routing()
    info_intents = ["VIX 是多少？", "PF 还好吗？", "丰田怎么样？", "看一下待办", "早上好", "早盘摘要"]
    for ex in data["examples"]:
        if ex.get("intent") in info_intents:
            assert ex.get("history_check") is not True, (
                f"history_check should NOT be on info query: {ex.get('intent')}"
            )


def test_history_check_NOT_on_routine():
    """routine-* modes do not get history_check."""
    data = _load_routing()
    for ex in data["examples"]:
        mode = ex.get("mode", "")
        if mode.startswith("routine-") or mode == "morning-summary":
            assert ex.get("history_check") is not True, (
                f"history_check should NOT be on routine: {ex.get('intent')}"
            )


def test_skill_md_documents_history_check():
    """SKILL.md documents the History Check section."""
    text = SKILL_PATH.read_text()
    assert "## History Check" in text
    assert "KIK-740" in text
    assert "4LLM" in text or "4 LLM" in text


def test_skill_md_documents_graceful_degradation():
    """SKILL.md documents graceful degradation."""
    text = SKILL_PATH.read_text()
    assert "graceful degradation" in text.lower() or "未设置" in text
    assert any(k in text for k in ["OPENAI_API_KEY", "GEMINI_API_KEY", "XAI_API_KEY"])


def test_skill_md_documents_required_dual_view():
    """SKILL.md requires both successful/failed examples and counterevidence."""
    text = SKILL_PATH.read_text()
    assert "成功" in text and "失败" in text
    assert "反证" in text


def test_skill_md_differentiates_from_deepthink():
    """SKILL.md differentiates History Check from DeepThink."""
    text = SKILL_PATH.read_text()
    history_section_start = text.find("## History Check")
    history_section_end = text.find("## Reviewer 启动方针", history_section_start)
    section = text[history_section_start:history_section_end]
    assert "DeepThink" in section
    assert "自动" in section
    assert "多轮" in section or "多 Agent" in section


def test_orchestration_yaml_has_history_check():
    """orchestration.yaml has history_check auto-trigger definition."""
    with ORCHESTRATION_PATH.open() as f:
        data = yaml.safe_load(f)
    assert "history_check" in data
    hc = data["history_check"]
    assert "trigger" in hc
    assert "llm_layout" in hc
    assert "skip_conditions" in hc
    assert "cost_guardrail" in hc


def test_orchestration_history_check_triggers():
    """history_check trigger includes decision keywords and routing_flag."""
    with ORCHESTRATION_PATH.open() as f:
        data = yaml.safe_load(f)
    triggers = data["history_check"]["trigger"]
    flag_triggers = [t for t in triggers if "routing_flag" in t]
    assert len(flag_triggers) >= 1
    keyword_triggers = [t for t in triggers if "keyword_detect" in t]
    assert len(keyword_triggers) >= 1
    keywords = keyword_triggers[0]["keyword_detect"]
    for must in ["卖出", "止损", "换仓"]:
        assert must in keywords, f"keyword '{must}' missing"


def test_orchestration_history_check_llm_layout():
    """llm_layout defines Claude required + three optional LLMs."""
    with ORCHESTRATION_PATH.open() as f:
        data = yaml.safe_load(f)
    layout = data["history_check"]["llm_layout"]
    llms = {item["llm"]: item for item in layout}
    assert set(llms.keys()) == {"claude", "gpt", "gemini", "grok"}
    assert llms["claude"].get("required") is True
    for llm_name in ["gpt", "gemini", "grok"]:
        assert "env_key" in llms[llm_name]


def test_orchestration_history_check_skip_conditions():
    """routine_mode and morning_summary skip conditions are configured."""
    with ORCHESTRATION_PATH.open() as f:
        data = yaml.safe_load(f)
    skip = data["history_check"]["skip_conditions"]
    contexts = [s.get("context") for s in skip if "context" in s]
    assert "routine_mode" in contexts
    assert "morning_summary" in contexts
    assert "history_check_already_executed" in contexts


def test_skill_md_documents_data_insufficient_fallback():
    """SKILL.md documents fallback when data is insufficient."""
    text = SKILL_PATH.read_text()
    assert "数据不足" in text
    assert "无足够案例" in text or "推测" in text
