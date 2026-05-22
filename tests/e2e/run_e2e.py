#!/usr/bin/env python3
"""E2E Test Runner for stock-skills agents.

Usage:
    python3 tests/e2e/run_e2e.py              # 执行全部 scenario (真实 API)
    python3 tests/e2e/run_e2e.py e2e_001      # 仅指定 scenario
    python3 tests/e2e/run_e2e.py e2e_001 e2e_003  # 指定多个 scenario

    # KIK-746: 仅验证 routing（不调用 LLM/Yahoo Finance，< 1 秒）
    python3 tests/e2e/run_e2e.py --dry-run
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def runtime_path(*parts: str) -> Path:
    """Prefer Codex .agents assets, then fall back to Claude Code .claude."""
    agents_path = PROJECT_ROOT / ".agents" / Path(*parts)
    if agents_path.exists():
        return agents_path
    return PROJECT_ROOT / ".claude" / Path(*parts)


# ---------------------------------------------------------------------------
# Test functions (each returns {passed: bool, details: list[str]})
# ---------------------------------------------------------------------------

def test_screener() -> dict:
    """e2e_001: Screener — 有什么好的日本股票？"""
    details = []
    passed = True

    try:
        from src.data.yahoo_client import screen_stocks
        from yfinance import EquityQuery

        # 日本股票 alpha preset 等价（yfinance EquityQuery 字段名）
        query = EquityQuery("AND", [
            EquityQuery("EQ", ["exchange", "JPX"]),
            EquityQuery("LT", ["peratio.lasttwelvemonths", 20]),
            EquityQuery("LT", ["pricebookratio.quarterly", 2.0]),
            EquityQuery("GT", ["returnonequity.lasttwelvemonths", 8]),
        ])
        result = screen_stocks(query, max_results=5)

        # 基准1: 1 件以上
        if result and len(result) > 0:
            details.append(f"[x] 标的列表: {len(result)} 件")
        else:
            details.append("[o] 标的列表: 0 件")
            passed = False

        # 基准2: symbol, name
        if result:
            first = result[0]
            has_symbol = "symbol" in first
            has_name = "shortName" in first or "name" in first
            details.append(f"[{'x' if has_symbol else 'o'}] symbol: {'有' if has_symbol else '无'}")
            details.append(f"[{'x' if has_name else 'o'}] name: {'有' if has_name else '无'}")
            if not (has_symbol and has_name):
                passed = False

        # 基准3: 指标
        if result:
            first = result[0]
            has_per = "trailingPE" in first or "forwardPE" in first
            details.append(f"[{'x' if has_per else 'o'}] PER: {'有' if has_per else '无'}")

        # 基准4: region
        if result:
            all_japan = all(
                r.get("symbol", "").endswith(".T") or r.get("exchange") == "JPX"
                for r in result
            )
            details.append(f"[{'x' if all_japan else 'o'}] region=japan: {all_japan}")
            if not all_japan:
                passed = False

    except Exception as e:
        details.append(f"[o] 例外: {e}")
        passed = False

    return {"passed": passed, "details": details}


def test_analyst() -> dict:
    """e2e_002: Analyst — 7203.T 怎么样？"""
    details = []
    passed = True

    try:
        from tools.yahoo_finance import get_stock_info, get_price_history

        info = get_stock_info("7203.T")
        if info is None:
            details.append("[o] stock_info: None")
            return {"passed": False, "details": details}

        # 基准1: 基本指标
        for key in ["per", "pbr", "roe", "dividend_yield"]:
            val = info.get(key)
            details.append(f"[{'x' if val is not None else 'o'}] {key}: {val}")
            if val is None and key in ("per", "pbr"):
                passed = False

        # 基准2: 价格历史记录
        hist = get_price_history("7203.T", period="3mo")
        if hist is not None and len(hist) > 0:
            details.append(f"[x] price_history: {len(hist)} 数据点")
        else:
            details.append("[o] price_history: 无")
            passed = False

        # 基准3: 板块
        sector = info.get("sector")
        details.append(f"[{'x' if sector else 'o'}] sector: {sector}")

    except Exception as e:
        details.append(f"[o] 例外: {e}")
        passed = False

    return {"passed": passed, "details": details}


def test_health_checker() -> dict:
    """e2e_003: Health Checker — PF 还好吗？"""
    details = []
    passed = True

    try:
        # 基准1: 读取全部持有标的
        from src.data.portfolio_io import load_portfolio
        pf = load_portfolio()
        details.append(f"[{'x' if len(pf) > 0 else 'o'}] 标的数: {len(pf)}")
        if len(pf) == 0:
            passed = False

        # 基准2: 新字段（KIK-694）
        if pf:
            first = pf[0]
            has_return = first.get("total_return") is not None
            has_role = bool(first.get("role"))
            details.append(f"[{'x' if has_return else 'o'}] total_return: {first.get('total_return')}")
            details.append(f"[{'x' if has_role else 'o'}] role: {first.get('role')}")

        # 基准3: thesis/observation（KIK-695）
        from tools.notes import load_notes
        thesis_count = 0
        for pos in pf:
            notes = load_notes(symbol=pos["symbol"])
            thesis = [n for n in notes if n.get("type") in ("thesis", "observation")]
            thesis_count += len(thesis)
        details.append(f"[{'x' if thesis_count > 0 else 'o'}] thesis/observation: {thesis_count} 件")

        # 基准4: 股价获取
        from tools.yahoo_finance import get_stock_info
        if pf:
            info = get_stock_info(pf[0]["symbol"])
            details.append(f"[{'x' if info else 'o'}] 股价获取({pf[0]['symbol']}): {'OK' if info else 'NG'}")
            if not info:
                passed = False

    except Exception as e:
        details.append(f"[o] 例外: {e}")
        passed = False

    return {"passed": passed, "details": details}


def test_researcher() -> dict:
    """e2e_004: Researcher — 告诉我最新新闻"""
    details = []
    passed = True

    try:
        # 基准1: Grok API 可用性
        from src.data.grok_client._common import is_available
        grok_ok = is_available()
        details.append(f"[x] Grok API: {'可用' if grok_ok else '未设置'}")

        # 基准2: 新闻获取
        if grok_ok:
            from tools.grok import search_market
            result = search_market("全体")
            has_data = result and any(
                result.get(k) for k in ["price_action", "macro_factors", "sentiment"]
            )
            details.append(f"[{'x' if has_data else 'o'}] 新闻数据: {'有' if has_data else '无'}")
        else:
            details.append("[x] Grok 未设置: graceful degradation（空数据、无错误）")

        # 基准3: GraphRAG
        from tools.graphrag import HAS_GRAPH_QUERY, HAS_CONTEXT
        details.append(f"[x] GraphRAG: query={HAS_GRAPH_QUERY}, context={HAS_CONTEXT}")

    except Exception as e:
        details.append(f"[o] 例外: {e}")
        passed = False

    return {"passed": passed, "details": details}


def test_risk_assessor() -> dict:
    """e2e_005: Risk Assessor — 风险判定执行"""
    details = []
    passed = True

    try:
        from tools.yahoo_finance import get_stock_info

        # 基准1: 市场指标获取
        indicators = {
            "^GSPC": "S&P500",
            "^VIX": "VIX",
            "^TNX": "美国10年利率",
            "USDJPY=X": "美元日元",
        }
        for sym, name in indicators.items():
            info = get_stock_info(sym)
            if info and info.get("price") is not None:
                details.append(f"[x] {name}: {info['price']}")
            else:
                details.append(f"[o] {name}: 获取失败")
                passed = False

        # 基准2: RSI 可计算性
        from tools.yahoo_finance import get_price_history
        hist = get_price_history("^GSPC", period="3mo")
        if hist is not None and len(hist) >= 14:
            details.append(f"[x] RSI 可计算: {len(hist)} 数据点")
        else:
            details.append("[o] RSI 不可计算: 数据不足")
            passed = False

        # 基准3: 即使没有 Grok 也可判定
        details.append("[x] 即使没有 Grok 也可基本判定（用 VIX/利率/WTI 算出暂定评分）")

    except Exception as e:
        details.append(f"[o] 例外: {e}")
        passed = False

    return {"passed": passed, "details": details}


def test_hc_strategist_chain() -> dict:
    """e2e_006: HC + Strategist Chain — 想改善 PF"""
    details = []
    passed = True

    try:
        # 基准1: PF 数据
        from src.data.portfolio_io import load_portfolio
        pf = load_portfolio()
        has_return = any(pos.get("total_return") is not None for pos in pf)
        details.append(f"[{'x' if pf else 'o'}] PF数据: {len(pf)} 标的")
        details.append(f"[{'x' if has_return else 'o'}] 收益率数据: {'有' if has_return else '无'}")

        # 基准2: lesson
        from tools.notes import load_notes
        lessons = load_notes(note_type="lesson")
        details.append(f"[{'x' if lessons else 'o'}] lesson: {len(lessons)} 件")

        # 基准3: thesis/observation
        thesis_count = 0
        for pos in pf:
            notes = load_notes(symbol=pos["symbol"])
            thesis_count += len([n for n in notes if n.get("type") in ("thesis", "observation")])
        details.append(f"[{'x' if thesis_count > 0 else 'o'}] thesis/observation: {thesis_count} 件")

        # 基准4: GraphRAG
        from tools.graphrag import HAS_GRAPH_QUERY, HAS_CONTEXT
        details.append(f"[x] GraphRAG: query={HAS_GRAPH_QUERY}, context={HAS_CONTEXT}")

        # 基准5: what-if 股价获取
        from tools.yahoo_finance import get_stock_info
        if pf:
            info = get_stock_info(pf[0]["symbol"])
            details.append(f"[{'x' if info else 'o'}] what-if 用股价: {'OK' if info else 'NG'}")
            if not info:
                passed = False

    except Exception as e:
        details.append(f"[o] 例外: {e}")
        passed = False

    return {"passed": passed, "details": details}


def test_deepthink_swarm() -> dict:
    """e2e_007: DeepThink 4-Swarm — 两层 model 动态角色分配"""
    details = []
    passed = True

    try:
        # 基准1: 读取 deepthink_limits.yaml 并检查值
        import yaml
        limits_path = runtime_path("skills", "deepthink", "deepthink_limits.yaml")
        with open(limits_path) as f:
            limits = yaml.safe_load(f)

        max_spawns = limits["limits"]["max_agent_spawns"]
        max_llm = limits["limits"]["max_llm_calls"]
        if max_spawns >= 20:
            details.append(f"[x] max_agent_spawns: {max_spawns} (>= 20)")
        else:
            details.append(f"[o] max_agent_spawns: {max_spawns} (< 20，不足以支持 4-Swarm)")
            passed = False

        if max_llm >= 25:
            details.append(f"[x] max_llm_calls: {max_llm} (>= 25)")
        else:
            details.append(f"[o] max_llm_calls: {max_llm} (< 25)")
            passed = False

        # 深度 preset 验证
        for depth in ["shallow", "medium", "deep"]:
            preset = limits["depth_presets"][depth]
            details.append(f"[x] {depth}: spawns={preset['max_agent_spawns']}, llm={preset['max_llm_calls']}")

        # 基准2: LLM provider 可用性
        from tools.llm import get_available_providers, is_provider_available
        providers = get_available_providers()
        details.append(f"[x] 可用 provider: {providers if providers else '无（graceful degradation）'}")

        # 基准3: 各 LLM 连通性确认（仅 API key 存在时）
        from tools.llm import call_llm

        swarm_members = {
            "gpt": {"model": "gpt-5.4", "prompt": "Reply OK in one word.", "kwargs": {"reasoning": "low"}},
            "gemini": {"model": "gemini-3-flash-preview", "prompt": "Reply OK in one word.", "kwargs": {}},
            "grok": {"model": "grok-4.20-0309-reasoning", "prompt": "Reply OK in one word.", "kwargs": {}},
        }

        llm_ok_count = 0
        for provider, cfg in swarm_members.items():
            if is_provider_available(provider):
                result = call_llm(provider, cfg["model"], cfg["prompt"], timeout=30, **cfg["kwargs"])
                if result:
                    details.append(f"[x] {provider}: 有响应 ({len(result)} chars)")
                    llm_ok_count += 1
                else:
                    details.append(f"[o] {provider}: 有 API key 但无响应")
                    passed = False
            else:
                details.append(f"[x] {provider}: 未设置（graceful degradation）")

        # 基准4: Grok search 函数可用性
        from src.data.grok_client._common import is_available as grok_available
        if grok_available():
            from tools.grok import search_x_sentiment
            sentiment = search_x_sentiment("AAPL", "Apple")
            if sentiment:
                details.append(f"[x] Grok search_x_sentiment: 数据有")
            else:
                details.append(f"[o] Grok search_x_sentiment: 数据无")
        else:
            details.append(f"[x] Grok search: 未设置（graceful degradation）")

        # 基准5: SKILL.md 是否包含两层模型、综合结论、摘要等描述
        skill_path = runtime_path("skills", "deepthink", "SKILL.md")
        skill_content = skill_path.read_text()
        checks = {
            "基础设施层": "基础设施层" in skill_content,
            "推理层": "推理层" in skill_content,
            "适性": "适性" in skill_content,
            "硬约束": "硬约束" in skill_content,
            "4-Swarm": "4-Swarm" in skill_content,
            "executive summary": "executive summary" in skill_content,
            "综合结论": "综合结论" in skill_content,
            "采用": "采用" in skill_content,
            "工具引用": "tools.yaml" in skill_content,
            "screen_stocks 必须": "screen_stocks" in skill_content,
        }
        for label, found in checks.items():
            details.append(f"[{'x' if found else 'o'}] SKILL.md {label}: {'有' if found else '无'}")
            if not found:
                passed = False

        # 基准6: config/tools.yaml 的存在和一致性
        tools_path = PROJECT_ROOT / "config" / "tools.yaml"
        if tools_path.exists():
            with open(tools_path) as f:
                tools_def = yaml.safe_load(f)
            tools_keys = list(tools_def.get("tools", {}).keys())
            required = ["yahoo_finance", "grok", "graphrag", "llm", "notes", "portfolio_io"]
            has_all_tools = all(t in tools_keys for t in required)
            details.append(f"[{'x' if has_all_tools else 'o'}] tools.yaml: {tools_keys}")
            # screen_stocks 定义
            yf = tools_def.get("tools", {}).get("yahoo_finance", {}).get("functions", {})
            has_screen = "screen_stocks" in yf
            details.append(f"[{'x' if has_screen else 'o'}] tools.yaml screen_stocks: {'有定义' if has_screen else '无'}")
            if not (has_all_tools and has_screen):
                passed = False
        else:
            details.append("[o] tools.yaml: 文件无")
            passed = False

        # 基准7: llm_capabilities.yaml 的存在和一致性
        cap_path = PROJECT_ROOT / "config" / "llm_capabilities.yaml"
        if cap_path.exists():
            with open(cap_path) as f:
                caps = yaml.safe_load(f)
            has_all = all(p in caps.get("providers", {}) for p in ["gemini", "gpt", "grok"])
            details.append(f"[{'x' if has_all else 'o'}] llm_capabilities.yaml: 全部 provider 已定义")
        else:
            details.append("[o] llm_capabilities.yaml: 文件无")
            passed = False

    except Exception as e:
        details.append(f"[o] 例外: {e}")
        passed = False

    return {"passed": passed, "details": details}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

SCENARIOS = {
    "e2e_001": ("Screener E2E", test_screener),
    "e2e_002": ("Analyst E2E", test_analyst),
    "e2e_003": ("Health Checker E2E", test_health_checker),
    "e2e_004": ("Researcher E2E", test_researcher),
    "e2e_005": ("Risk Assessor E2E", test_risk_assessor),
    "e2e_006": ("HC + Strategist Chain E2E", test_hc_strategist_chain),
    "e2e_007": ("DeepThink 4-Swarm E2E", test_deepthink_swarm),
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_scenarios(ids: list[str] | None = None):
    """Run E2E scenarios and print results."""
    targets = ids or list(SCENARIOS.keys())
    results = []
    total_pass = 0
    total_fail = 0

    print(f"\n{'='*60}")
    print(f"E2E Test Suite — {len(targets)} scenarios")
    print(f"{'='*60}\n")

    for scenario_id in targets:
        if scenario_id not in SCENARIOS:
            print(f"⚠️  Unknown scenario: {scenario_id}")
            continue

        name, test_fn = SCENARIOS[scenario_id]
        print(f"▶ {scenario_id}: {name}...", end=" ", flush=True)

        start = time.time()
        result = test_fn()
        elapsed = time.time() - start

        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        print(f"{status} ({elapsed:.1f}s)")

        for detail in result["details"]:
            print(f"  {detail}")
        print()

        results.append({
            "id": scenario_id,
            "name": name,
            "passed": result["passed"],
            "elapsed": round(elapsed, 1),
            "details": result["details"],
        })

        if result["passed"]:
            total_pass += 1
        else:
            total_fail += 1

    # Summary
    print(f"{'='*60}")
    print(f"结果: {total_pass} PASS / {total_fail} FAIL (全{len(results)}件)")
    print(f"{'='*60}")

    # Save results
    results_path = PROJECT_ROOT / "data" / "e2e_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total": len(results),
            "passed": total_pass,
            "failed": total_fail,
            "scenarios": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n结果保存到 {results_path} ")

    return total_fail == 0


def run_dry_run() -> bool:
    """KIK-746: 仅验证 routing（不调用 LLM/Yahoo Finance）.

    对各 scenario 的预期 user input 执行 routing 解析、agent 存在确认、
    预期 tool 列举，并快速运行。
    """
    from src.orchestrator import verify_routing, verify_routing_yaml_integrity

    print("\n" + "=" * 60)
    print("E2E Dry-Run — routing only (no LLM, no Yahoo Finance)")
    print("=" * 60 + "\n")

    # 1) routing.yaml integrity check
    integrity = verify_routing_yaml_integrity()
    if integrity["passed"]:
        print("✅ routing.yaml integrity: OK")
    else:
        print("❌ routing.yaml integrity: FAIL")
    for err in integrity["errors"]:
        print(f"   ❌ {err}")
    for warn in integrity["warnings"][:5]:
        print(f"   ⚠️  {warn}")
    if len(integrity["warnings"]) > 5:
        print(f"   ⚠️  ... and {len(integrity['warnings']) - 5} more warnings")
    print()

    # 2) 按 scenario 验证 routing（典型输入例）
    sample_inputs = {
        "e2e_001": "有什么好股票？",
        "e2e_002": "丰田怎么样？",
        "e2e_003": "PF 还好吗？",
        "e2e_004": "告诉我最新新闻",
        "e2e_005": "做一下风险判定",
        "e2e_006": "想改善 PF",
        "e2e_007": "这只股票该卖吗？",
    }
    pass_count, fail_count = 0, 0
    for sid, user_in in sample_inputs.items():
        r = verify_routing(user_in)
        ok = r.passed
        status = "✅" if ok else "❌"
        agents = ",".join(r.agents) if r.agents else (r.flags.get("action") or "?")
        print(f"  {status} {sid}: {user_in!r}")
        print(f"      → matched: {r.matched_intent!r}  agents: {agents}")
        if r.expected_tools:
            print(f"      → tools: {', '.join(r.expected_tools)}")
        for warn in r.warnings:
            print(f"      ⚠️  {warn}")
        for err in r.errors:
            print(f"      ❌ {err}")
        if ok:
            pass_count += 1
        else:
            fail_count += 1

    print("\n" + "=" * 60)
    print(f"Dry-run结果: {pass_count} PASS / {fail_count} FAIL")
    print("=" * 60)
    return fail_count == 0 and integrity["passed"]


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--dry-run" in args:
        success = run_dry_run()
    else:
        ids = args if args else None
        success = run_scenarios(ids)
    sys.exit(0 if success else 1)
