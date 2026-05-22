---
name: deepthink
description: DeepThinking。用于自主补齐缺失视角，并通过 scenario branching 做深度分析。采用 Evaluator-Optimizer pattern。用户要求深度思考、scenario analysis、复杂判断、PF 设计、再投资候选，或投资判断含多个不确定性时启动。
user_invocable: true
---

# DeepThink

DeepThink 以 Evaluator-Optimizer pattern 做自律深度分析。普通 stock-skills 通常一下一步 agent 执行即可回答；DeepThink 会持续进行 **评价 -> 改善** loop，直到收敛或触及 harness 上限。

## 使用时机

- 地缘或 macro scenario 对 PF 的影响
- 再投资候选选择，需要候选筛选、RSI 检查、scenario 验证和 PF target 对照
- 面向 6 个月后的 PF 设计，需需要 macro scenario、sector rotation、currency allocation 一起分析

普通 stock-skills 足够时不需要使用。DeepThink 只用于多个不确定性相互缠绕的判断。

## Harness 强制规则

以下规则不可省略或改写:

```text
MUST: Step 2b 必须执行 GPT / Gemini / Grok + Claude Code 自身 4 方 review，不能省略。
MUST: 每个缺失项必须写明“做什么 -> 用哪个 LLM/工具 -> 为什么”。
MUST: 收敛条件未满足前自律 loop，不需要每轮等待批准。
MUST: 只有触及 harness 上限时才停止并请求用户批准。
```

## 执行 flow

### Step 0: 启动通知 + 执行计划 + 等待批准

向用户说明:

```text
🧠 DeepThinking mode
深度: [shallow / medium / deep](max N agents, M LLM calls)

📋 执行计划:
  Step 1: lesson load -> [按主题生成的初始分析]([使用 agent])
  Step 2: evaluation + 4-Swarm 并行 review(两层模型: 固定基础设施 + 动态推理分配)
  Step 3: 若有不足则追加调查([预计追加调查])
  -> Step 2-3 自律 loop 直到收敛
  Step 5: 综合报告

继续吗？ [直接执行 / 修改计划 / 取消]
```

**MUST (KIK-735): Step 1 前必须通过 preflight gate。**

```python
from tools.preflight import run_preflight
result = run_preflight(domain="pf")
if not result["passed"]:
    raise SystemExit(f"Preflight failed: {result['violations']}")
```

这会在 code level 阻止 cash_balance.json 未参考、conviction violation、lot_size 错误等事故。

执行计划从主题自动生成。典型映射:

| 主题 | Step 1 | 可能的 Step 3 |
|:---|:---|:---|
| PF 再投资候选 | HC + Researcher 获取 PF 现况和市场 | 候选 RSI、scenario branching |
| 地缘事件影响 | Researcher 做地缘研究 | PF symbol sensitivity |
| 6 个月 PF 设计 | HC + Researcher 做 macro | sector rotation x currency allocation |

深度指南:

- **shallow**: 1 下一步追加调查。轻量补足信息(max 3 agents, 5 LLM calls, 建议输出约 1500 字)
- **medium**: 2-3 下一步评价 -> 改善 loop(max 6 agents, 12 LLM calls, 建议输出约 2500 字)
- **deep**: 最多 5 下一步 loop(max 10 agents, 20 LLM calls, 建议输出约 4000 字)

只有 Step 0 等用户明确响应。Step 1 之后自律 loop。

## 可用工具

参见 [config/tools.yaml](../../config/tools.yaml)。其中定义所有工具函数、角色和使用时机。

**MUST:** 涉及再投资、换仓、候选选择时，必须用 `screen_stocks()` 以数据驱动生成候选。不得只凭 AI 知识手选。

## Step 1: 初始分析

**MUST (KIK-738): lesson 必须全量 load 后，用 `filter_relevant_lessons()` 抽取与主题相关部分。**

不需要全量硬塞 lesson。只把相关 lesson 明确筛出，并在后续步骤持续引用。

```python
python3 -c "
import sys; sys.path.insert(0, '.')
from tools.notes import load_notes
from src.data.lesson_enforcer import filter_relevant_lessons

all_lessons = load_notes(note_type='lesson')
user_input = '<USER_PROMPT_HERE>'
relevant_lessons = filter_relevant_lessons(user_input, all_lessons)

print(f'=== Lessons {len(relevant_lessons)}/{len(all_lessons)} relevant ===')
for n in relevant_lessons:
    print(f'[{n.get(\"date\",\"\")}] trigger={n.get(\"trigger\",\"(none)\")[:60]}')
    print(f'  expected_action: {n.get(\"expected_action\",\"(none)\")[:100]}')

if not relevant_lessons:
    print('[fallback] no trigger-match -> recent 10 of', len(all_lessons))
    relevant_lessons = all_lessons[-10:]

import csv
with open('data/portfolio.csv') as f:
    symbols = [row['symbol'] for row in csv.DictReader(f)]
print('\\n=== Strategic notes ===')
for sym in symbols:
    notes = load_notes(symbol=sym)
    thesis = [n for n in notes if n.get('type') in ('thesis', 'observation')]
    if thesis:
        print(f'{sym}: {len(thesis)} notes')
        for n in thesis[:2]:
            print(f'  [{n.get(\"type\")}] {n.get(\"content\",\"\")[:150]}')
"
```

`relevant_lessons` 必须在后续所有步骤中使用，并在 Step 5 的 `verify_lesson_cited()` 中传入同一个列表。

随后按主题启动 stock-skills agent(Screener / Analyst / Health Checker / Researcher / Strategist)。可用 agent 见 [stock-skills routing.yaml](../stock-skills/routing.yaml)。

## Step 2: Evaluation(自评 + 3 LLM 并行 review + 反证再计划)

DeepThink 的价值是展示“为什么这样判断”，而不是只给结论。

### 2a. 自评

对初始分析从以下维度评价:

| 维度 | 检查内容 |
|:---|:---|
| 信息充足 | 是否缺 RSI、财报日期、sentiment 等 |
| Scenario | 是否有乐观/中性/悲观 |
| PF 一致性 | 是否对照用户 PF 和 target |
| 反证 | 是否有 Devil's Advocate |
| lesson | 是否与 Step 1 lesson 一致 |

### 2b. 4-Swarm 并行 review(4 方全必需)

采用两层模型: 基础设施层固定 + 推理层动态。

基础设施层:

| LLM | 固定职责 | 原因 |
|:---|:---|:---|
| Grok | X / 实时市场数据 | X Firehose 是硬约束 |
| Gemini | Google 搜索 + 长上下文 | Google Search Grounding 是硬约束 |

推理层角色:

| 角色 | 内容 |
|:---|:---|
| Devil's Advocate | 反证、风险、遗漏 |
| Scenario Analyst | scenario branching、sensitivity、长期推理 |
| Lesson Auditor | lesson 一致性和历史学习检查 |
| Portfolio Aligner | PF 一致性、target、currency/region allocation |

适性:

| 角色 | GPT | Gemini | Grok | Claude Code |
|:---|:---|:---|:---|:---|
| Devil's Advocate | 最适 | 中立偏强 | 可 | 可 |
| Scenario Analyst | 最适 | 强 | 表层 | 可 |
| Lesson Auditor | 可 | 最适 | 可 | 强 |
| Portfolio Aligner | 可 | 可 | 可 | 最适 |

先固定硬约束，再用适性分配推理角色。

主题例:

```text
地缘风险:
  Grok   = X 市场反应 + Devil's Advocate
  Gemini = Google 搜索 + Scenario Analyst
  GPT    = Lesson Auditor
  Claude Code  = Portfolio Aligner

财报分析:
  Grok   = X 财报反应
  Gemini = 财报数据验证 + Lesson Auditor
  GPT    = Scenario Analyst
  Claude Code  = Devil's Advocate

PF 重设:
  Grok   = X 市场评价 + sentiment
  Gemini = Google 搜索 + Scenario Analyst
  GPT    = Devil's Advocate
  Claude Code  = Portfolio Aligner
```

调用方式:

| LLM | 调用 |
|:---|:---|
| GPT | `call_llm('gpt', 'gpt-5.4', prompt, reasoning='high')` |
| Gemini | `call_llm('gemini', 'gemini-3-flash-preview', prompt, web_search=True)` 或 `call_llm('gemini', 'gemini-3.1-pro-preview', prompt)` |
| Grok | `tools/grok.py` 的 `search_x_sentiment()` / `search_market()` 或 `call_llm('grok', 'grok-4.20-0309-reasoning', prompt)` |
| Claude Code | orchestrator 层直接执行 |

### 2c. 反证 -> 再计划

整合外部 review，对初始结论进行修正或强化:

```text
📊 DeepThink Step 2 完成(Agents: X/Y, LLM calls: A/B)

初始结论: [...]

Swarm 分配:
  GPT    = [...]
  Gemini = [...]
  Grok   = [...]
  Claude Code  = [...]

反证:
  [Devil's Advocate]: [...]
  [Scenario Analyst]: [...]
  [Lesson Auditor]: [...]
  [Portfolio Aligner]: [...]

综合结论:
  [说明每个 LLM 指出的问题如何影响最终判断]

再计划:
  初始: [...]
  修正: [...]
  理由: [...]
```

**MUST:** 综合结论必须说明“各 LLM 指摘如何反映到判断中”。不需要只罗列观点。

收敛条件:

1. 5 个评价维度全部完成
2. 没有新不足

停止条件:

1. 达到 max_iterations
2. 达到 max_llm_calls
3. 达到 max_wall_time_minutes

触及停止条件时，展示当前结果并请求用户批准是否继续。

## Step 3: 改善(Optimizer)

根据不足列表，自主启动追加 agent / 工具。

**MUST:** 每个不足项必须写“做什么 -> 用哪个 LLM/工具 -> 为什么”。

```text
不足: X sentiment 未获取
  -> 做什么: UL 在 X 上的投资者评价
  -> 用哪个 LLM/工具: Grok search_x_sentiment("UL", "Unilever")
  -> 为什么: 补足候选的市场定性评价

不足: event scenario 未分析
  -> 做什么: BOJ/FOMC 最新预期
  -> 用哪个 LLM/工具: Gemini(web_search=True)
  -> 为什么: 下周事件可能影响短期价格

不足: RSI 未确认
  -> 做什么: 候选 symbol 的 RSI(14)
  -> 用哪个工具: yahoo_finance.get_price_history + code interpreter
  -> 为什么: 避免高位买入
```

多 LLM 使用(参见 `config/llm_capabilities.yaml`):

| 用途 | 优先 LLM | 原因 |
|:---|:---|:---|
| 事实收集(Google 搜索) | Gemini(web_search=True) | Google Search Grounding |
| X sentiment / real-time | Grok | X Firehose |
| 反证 / risk | GPT(reasoning='high') | 批判性推理 |
| lesson 对照 / 长文 | Gemini-Pro | 长上下文 |
| PF 一致性 / 整合判断 | Claude Code | 持有本地上下文 |
| 深度行业调查 | Gemini Deep Research | 多 source 带引用 |
| 多 symbol/theme 并行 | Grok bulk_x / bulk_web | X firehose 并行 |

### Deep Research / Bulk Search trigger(KIK-731 / KIK-732)

用户说“深入”“彻底”“DR”“花时间”，或分析对象超过 5 个 symbol / 3 个 theme 时，在 Step 3 提议:

```text
🔍 可启动 Deep Research
   - gemini.deep_research: Web 深度研究(80-160 sources，预计 $2.5，5-10 分钟)
   - grok.bulk_x_search: X 并行 sentiment(预计 $0.5-2.5，约 30 秒)
   执行吗？ [y/skip]
```

用户确认后执行。完成后在 Layer 4 记录:

```text
💰 cost=$X.XX | 📚 sources=N | ⏱ duration=Xs
```

`DEEPTHINK_DR_ENABLED=off` 时 DR 立即禁用。遵守 `deepthink_limits.yaml` 的 monthly/tool limits。

## Step 4: Checkpoint(只报告，不等待批准)

向用户做中间报告；若仍有不足，自主回到 Step 2。

必须严格使用格式:

```text
📊 DeepThink Step N/M 完成(Agents: X/Y, LLM calls: A/B)

中间结果:
- [...]
- [...]
- [...]

不足: [剩余不足列表 or "无，已收敛"]
-> 自主继续: [下一步] / 收敛: Step 5
```

用户只有在想停止或修正方向时介入。

## Step 5: 综合报告

**MUST (KIK-735): 如果包含买卖、trim、卖出建议，Step 5 前必须再下一步 preflight。**

```python
from tools.preflight import run_preflight
proposed = [("trim", "NVDA", 3), ("sell", "AMZN", 10)]
result = run_preflight(domain="pf", proposed_actions=proposed)
if not result["passed"]:
    raise SystemExit(f"Preflight failed at Step 5: {result['violations']}")
```

**MUST (KIK-738): 最终建议必须逐字引用 Step 1 的 `relevant_lessons` 中的关键 expected_action / key_kpis。**

输出前执行:

```python
from src.data.lesson_enforcer import verify_lesson_cited

final_proposal_text = "<executive summary + swarm integration + details>"
ok, missing_lesson_ids = verify_lesson_cited(final_proposal_text, relevant_lessons)
if not ok:
    raise SystemExit(
        f"Step 5 lesson citation failed: {missing_lesson_ids} are not cited in proposal. "
        "Rewrite the proposal and quote expected_action/key_kpis from the relevant lessons."
    )
```

如果执行了 Deep Research / bulk_search，还需要 cross-check DR 中 rejected 的 symbol 没有混入最终建议:

```python
import re

def _extract_dr_rejected(dr_text: str) -> list[str]:
    if not dr_text:
        return []
    pattern = r"(?:skip|reject|excluded|not selected|avoid)[^\n]{0,400}"
    rejected: set[str] = set()
    for match in re.finditer(pattern, dr_text, flags=re.IGNORECASE):
        sect = match.group(0)
        for sym in re.findall(r"\b([A-Z]{2,5}|\d{4}\.T)\b", sect):
            rejected.add(sym)
    return sorted(rejected)

dr_text = "<DR report text>"
dr_rejected = _extract_dr_rejected(dr_text)
for sym in dr_rejected:
    if sym in final_proposal_text and not re.search(
        rf"{sym}.{{0,80}}(reject|skip|excluded|not selected|avoid)",
        final_proposal_text,
        flags=re.IGNORECASE,
    ):
        raise SystemExit(
            f"DR cross-check failed: '{sym}' was rejected by DR but appears in proposal "
            "without explicit rejection rationale."
        )
```

**MUST (KIK-739): 输出前生成 Layer 5 (Cited Sources) 并追加到正文末尾。**

```python
from src.data.citation_formatter import format_cited_sources

cited_lessons = [l for l in relevant_lessons if l.get("id") not in missing_lesson_ids]
cited_theses = [
    t for t in all_theses
    if (t.get("symbol") or "") and t["symbol"] in final_proposal_text
]
used_for_map = {
    cited_lessons[0]["id"]: "Cash 15-20% 判断",
}

citation_block = format_cited_sources(
    cited_lessons, cited_theses, used_for_map=used_for_map,
)
final_proposal_text = final_proposal_text.rstrip() + "\n\n" + citation_block
```

`format_cited_sources` freshness marker:

- `permanent` -> 🟢
- `seasonal` 或无 tag -> 0-30 天 🟢 / 31-90 天 🟡 / 91 天以上 🔴
- `expired` -> 自动排除
- thesis with conviction_override -> 🔒

最终报告必须采用 executive summary 先行的三段结构:

```text
■ Executive Summary
[3-5 行结论。建议行动 + 主要理由 + 关键数值]

■ Swarm Integration
[4 方指摘如何被采纳/拒绝/部分采纳]
  - [LLM-A] 指出 [...] -> [采纳/拒绝/部分采纳]，理由 [...]
  - [LLM-B] 分析 [...] -> 对结论的影响 [...]
  - [LLM-C] 报告 [...] -> 对判断的影响 [...]
  - Claude Code 评估 [...]
  -> 综合以上，最终判断 [...]

■ Details
  Scenario analysis:
    [...]
  Portfolio impact:
    [...]
  Evidence:
    [...]
  Recommended actions:
    [...]
```

**MUST:** Executive Summary 必须足以让用户快速判断。Swarm Integration 必须说明每个 LLM 观点如何被处理，不得只列观点。

## Harness limits

遵守 `deepthink_limits.yaml`:

- 达上限时停止 loop，展示当前结果，并等待用户批准
- 每步显示 progress: `Agents 4/6, LLM calls 8/12`

## Progress format

步骤开始:

```text
🔍 DeepThink Step N: [step name]
   [LLM/tool] 正在处理 [task]...
```

步骤完成:

```text
✅ DeepThink Step N 完成
   发现: [1-2 行主要发现]
   下一步: [next action]
```

## References

- Harness limits: [deepthink_limits.yaml](./deepthink_limits.yaml)
- LLM capabilities: [llm_capabilities.yaml](../../config/llm_capabilities.yaml)
- Normal mode: [stock-skills SKILL.md](../stock-skills/SKILL.md)
