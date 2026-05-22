---
name: stock-skills
description: 投资组合 assistant / stock portfolio assistant。用户用中文自然语言请求选股、股票筛选、公司分析、portfolio/PF/持仓/现金、新闻、市场风险、投资判断、交易、换仓或 rebalance 时必须启动。包含 session-start / portfolio 关键词(早上好、早盘、今天、现状、PF)时也必须启动，并分派到 screener/analyst/health-checker/researcher/strategist/risk-assessor/reviewer。session-start 时必须先执行 reconcile_session_state() hard gate。
user_invocable: true
---

# Stock Skills Orchestrator

解释用户的中文自然语言输入，并路由到合适的 agent。该 skill 是 Claude Code mirror；Codex canonical 在 `.agents/`，由 Phase 5 同步生成。

## Output & Visibility v1(KIK-729)

所有输出按 5 层生成。每下一步 agent 执行都必须遵守。

```text
[Layer 1] Header(执行前，常开)       -> 告诉用户将运行什么
─────────────────
[Layer 2] Progress(链式执行时)       -> 告诉用户进度
─────────────────
[Layer 3] Body(Pattern A/B/C)        -> 结论和详细内容
─────────────────
[Layer 4] Footer(执行后，固定顺序)    -> 保存、Reviewer、下一步
─────────────────
[Layer 5] Cited Sources(KIK-739)     -> 依赖的 lesson/thesis 和 freshness marker
```

Layer 5 对包含投资判断、交易建议、Strategist 或 DeepThink 输出的报告是必需的。用 `src/data/citation_formatter.format_cited_sources()` 生成，规则见本文末尾。

### Layer 1: Header(常开)

Routing 确定后、agent 启动前必须输出 1 行。Pattern A 也不能省略。

格式: `🎯 [<agent or chain>] <task summary>`

- 单一: `🎯 [health-checker] VIX 检查`
- 链式: `🎯 [risk -> HC -> strategist] 卖出判断`
- 并列: `🎯 [HC + researcher] 市场检查`
- routine: `🎯 [routine-daily] 日常检查`

优先使用 `routing.yaml` 的 `header` 字段。没有时自动生成:

- 来源: `routing.yaml` 的 `agents:` section 中 `<agent_name>.role`
- 格式: `🎯 [<agent>] <role 的简短摘要>`
- `agents` 数组链式执行时，生成 `🎯 [A -> B -> C] <最终目的>`

### Layer 2: Progress(链式执行时)

适用条件:

- pattern 中 `progressive: true`
- `agents.length >= 2`
- `mode: routine-*`

每个 agent 完成时输出:

```text
✅ <agent_name> 完成 (X.Xs) — <1 行摘要>
```

### Layer 3: Body(Pattern A/B/C)

判定 flow:

```text
Pattern A: 1-3 行可回答的事实查询(VIX/TODO/价格/note 件数等)
Pattern B: 单一 agent 执行(analyst/screener/HC/researcher 单下一步)
Pattern C: 链式执行或 routine(agents 数组多个 / progressive: true)
```

优先使用 `routing.yaml` 的 `pattern` 字段。未指定时按 agents 数组长度自动判定(1 -> B，2+ -> C)。Pattern A 必须显式指定。

#### Pattern A: Minimal

```markdown
[Layer1 header]
**结论 1 行**
[补充 1-2 行]
```

#### Pattern B: Standard

```markdown
[Layer1 header]

**结论:** <1 行 + 判定 marker 🟢/🟡/🔴>

| 项目 | 值 | 状态 |
|---|---|---|

### 详细(可选)
- bullet

### 下一步
- <1-2 个>
```

#### Pattern C: Chain

```markdown
[Layer1 header]
[Layer2 progress lines]

──────────
**综合结论:** <综合判定 🟢/🟡/🔴>

## ① <Agent> 结果
<Pattern B subset>

## ② <Agent> 结果
...

### 下一步
- 按优先级列 2-3 个
```

### Layer 4: Footer(固定顺序)

顺序必须固定:

```text
📊 执行: A -> B -> C
💾 保存: data/<path>
🔍 Reviewer 检查？ [y/skip]   <- 仅 adhoc 对象
➡ 下一步: <suggestion>
```

不需要的行可以省略；出现时必须按此顺序。

### 数值、marker、表格使用规则

| 元素 | 使用标准 |
|---|---|
| 表格 | 比较对象 >= 3 行或维度 >= 2 |
| 🟢🟡🔴 | 只用于有状态的值，不作装饰 |
| ⚠ | 仅用于 exit-rule 命中、conviction 警告、limit 超过 |
| 粗体 | 结论行；每个 section 最多 1 个关键数值 |
| 💾 | data/ 保存后必须输出 1 行 |

## Routing

1. 读取 `routing.yaml`，用最接近用户意图的 example 选择 agent
2. 单一 `agent` -> 读取 `.claude/agents/<agent>/agent.md` 与 `examples.yaml`，按该 role 执行
3. 多个 `agents` -> 按数组顺序链式执行，并整合结果
4. 没有匹配 pattern -> 用 `agents` section 的 `role` 和 `triggers` 自主判断

## Claude Code Runtime Compatibility

该目录下的 SKILL.md 是 Claude Code mirror。`.agents/` 是 Codex canonical。

- Canonical Claude Code paths:
  - Skill: `.claude/skills/stock-skills/SKILL.md`
  - Routing: `.claude/skills/stock-skills/routing.yaml`
  - Agent roles: `.claude/agents/<agent>/agent.md`
  - Agent examples: `.claude/agents/<agent>/examples.yaml`
  - Rules: `.claude/rules/`
- `routing.yaml` 的 `agent` / `agents` 是 role file 名，不是 Claude Code tool 名
- 常规自然语言输入由 Claude Code 自身读取必需要 role file，调用 `tools/`，并按 Output & Visibility v1 回答
- 只有用户明确要求 sub-agent、并行 agent、委派等时，才使用 Claude Code sub-agent 功能
- `.agents` 和 `.claude` 同时存在时，Claude Code 优先 `.claude`

## Session Start State Reconcile(KIK-738/739 后续)

**MUST: 在谈及 PF / cash / holdings / 交易 timing 前，必须先调用 `tools.session_state.reconcile_session_state()`，以 disk 状态为准。**

即使是轻量 session-start 问候或“PF 现状”类问题，也不能只依赖 AI memory。用户可能在 AI 不参与时交易，disk 状态更可信。

```python
from tools.session_state import reconcile_session_state

state = reconcile_session_state()
for w in state["warnings"]:
    print(f"⚠ {w}")
# 后续回答必须直接基于 state["portfolio"], state["cash_balance"],
# state["recent_notes"], state["recent_trades"]
```

返回值:

- `portfolio`: 当前持仓(CSV master)
- `cash_balance`: 现金余额(JSON，缺失时 None)
- `cash_missing`: cash_balance.json 缺失时 True
- `cash_stale`: cash_balance.json 的 date 超过 `cash_stale_days`(默认 3)时 True
- `recent_notes`: 最近 7 天 note(newer-first)
- `recent_trades`: 最近 7 天 trade JSON 文件名
- `warnings`: 面向用户的 warning 字符串

不执行该 hard gate 会重演 2026-04-29 事故：AI 根据旧 memory 展示未执行 todo，但 disk 中 portfolio.csv 和 journal 已更新。

实现位置:

- `tools/session_state.py`: 薄 facade
- `src/data/session_state.py`: 主体逻辑

## Intent Clarification

Routing 后、Execution 前执行。目标是确认用户意图是否已被正确补全。

### 上下文补全优先级

按 `routing.yaml` 的 `required_context` 定义补全必要参数:

1. **input_text**: 从用户输入直接抽取
2. **prior_output**: 从前一下一步 agent 输出补全
3. **portfolio**: 从 `data/portfolio.csv` 的持仓和 region 推断
4. **memory**: 用户历史偏好
5. **ask once**: 以上都不能解决时才问 1 下一步

### 解决规则

- `optional: true` 未解决时使用 `default` 并执行
- `optional: false` 未解决时，最多问 1 下一步
- 多个未解决参数合并成 1 条问题

### 提问格式

必须带上推测，并尽量让用户用 Yes/No 回答:

```text
输入模糊且无上下文:
  “我先按中国/美国之外的默认市场做价值股筛选，可以吗？如果要指定地区或 theme，请告诉我。”

输入模糊但有上下文:
  前一下一步 PF 诊断显示日本股票偏多 -> 自动筛选美国/欧洲股票，不追问

对象缺失(optional: false):
  “要分析哪个 symbol？”
```

### 不追问的情况

- 输入明确
- `required_context: []`
- `mode: routine-*`

### Header 和 progress

Header 使用 Output & Visibility v1 Layer 1。Progress 使用 Layer 2。

`routing.yaml` 的 `context_rules` 提供具体 heuristic，例如省略 symbol 时从 prior_output 补全。Intent Clarification 是参数满足性框架，二者互补。

## Execution

### Hook 顺序

```text
收到 user prompt
  -> 1. Routing 判定(routing.yaml，含 pattern A/B/C)
  -> 2. [PF 系] reconcile_session_state() hard gate
  -> 3. 输出 Layer 1 header
  -> 4. 启动 agent 或 direct action
       -> DeepThink Step 0 preflight(KIK-735)
       -> DeepThink Step 1 filter_relevant_lessons(KIK-736/738)
       -> DeepThink Step 5 verify_lesson_cited + Layer 5 Cited Sources(KIK-739)
```

### PF/cash/holdings 触发词必须调用 reconcile_session_state

如果 `routing.yaml` 中 `pf_state_required: true`，必须调用。即使没有该 flag，安全侧关键词也触发:

- PF / portfolio / 持仓 / 现金 / Cash / holdings
- 交易 / 卖出 / 买入 / 换仓 / rebalance / conviction / target
- session-start 词，如早晨问候、今天、现状

纯信息查询(例如 ETF universe 说明或单一指数查询)可省略。犹豫时调用；false positive 成本低，false negative 会重演事故。

### Role 执行

Claude Code 把 `.claude/agents/<agent>/agent.md` 和 `examples.yaml` 作为 role 定义。通常由 Claude Code 自身读取并执行。

只有用户明确要求 sub-agent / 并行委派时，才使用 sub-agent:

```text
spawn_agent({
  agent_type: "worker",
  message: "<agent.md key points> + <examples.yaml key points> + <user input> + <context>"
})
```

Role 执行时必须参考 agent.md 和 examples.yaml，并自主调用 `tools/` 获取数据、判断和输出。

### Conviction symbol 强制注入

启动 Strategist / Reviewer 前，用 `notes.load_notes(note_type="thesis")` 抽取 conviction(用户明确不卖的 symbol)，注入 prompt:

```text
⚠ conviction symbols(禁止卖出建议):
- 7751.T: hold locked by user
- AMZN: hold locked, trim allowed but full exit prohibited
禁止卖出，除非有足以推翻 conviction 理由的证据。
```

thesis content 含 hold lock、do not sell、conviction，或 source 以 `user-conviction` 开头时命中。

### Growth 筛选与风险判定联动

用户请求 growth 类选股时，**Screener 前先执行 Risk Assessor**。

流程:

1. Risk Assessor 输出 verdict + sector_signal + do-nothing check
2. Orchestrator 决定:

| 判定 | Screener mode | sector_signal 处理 |
|:---|:---|:---|
| normal | momentum / trending | 优先使用 favorable sector |
| risk-off | 不买 | 不启动 Screener，除非用户确认继续 |

3. do-nothing check 命中时，说明理由并建议“不行动”；用户坚持时执行。

向 Screener 注入:

- favorable sector 作为优先 theme
- unfavorable sector 可包含但加 ⚠
- income 框架: 总回报 > 4% + Beta <= 0.5
- growth 框架: EPS 增长为正 + thesis 清晰

### Screener 启动时的追加上下文(KIK-670)

启动 Screener 前，用 `tools/portfolio_io.py` 的 `load_portfolio()` 获取既有持仓，传入 prompt:

```text
1. agent.md + examples.yaml key points
2. user input
3. 前段 agent 结果(链式执行时)
4. 既有持仓 symbol 列表(从新候选中排除)
```

如果 CSV 不存在或读取失败，则不排除并继续。

### 链式 vs 并行(KIK-672)

`agents: [A, B]` 默认是有序链式执行，A 的结果进入 B。

| pattern | 判断 | 示例 |
|:---|:---|:---|
| A 输出影响 B 输入 | 链式 | researcher -> screener |
| A 与 B 独立分析同一对象 | 并行 | health-checker + researcher |

只有 routing.yaml 明确可独立时才并行。犹豫时选择链式。

### Orchestrator 主导并行(KIK-673)

Claude Code 常规执行中按独立 role task 顺序处理并 merge。只有用户明确要求 sub-agent / 并行委派时才实际同时发 sub-agent。

Screener 拆分:

```text
NG: 一个 Screener 处理所有 theme
OK: 每个 theme x region 作为独立 role task
```

Reviewer 拆分:

```text
NG: 一个 Reviewer 同时混合全部 LLM 视角
OK: risk reviewer、logic reviewer、data reviewer 独立，最后 orchestrator 汇总
```

单 theme 或轻量 review 时可不拆分。

## Routine Execution(KIK-724)

当 `routing.yaml` 匹配 `mode: routine-daily` 或 `mode: routine-weekly` 时，由 orchestrator 控制流程。

### Level 判定

| level | trigger | 预计时间 |
|:---|:---|:---|
| daily | 日常检查、例行检查、快速汇总 | 3-4 分钟 |
| weekly | 周度 review、完整检查、深入检查 | 8-13 分钟 |
| default | 未指定 | daily |

### Daily flow

```text
Step 1: detect_alerts
  -> CRITICAL symbol 注入 Step 2
Step 2: HC — PF health check
Step 3a: HC — 市场定量        ─┐ 并行
Step 3b: researcher — 新闻     ─┘
Step 4: HC — target 偏离(config/allocation.yaml)+ watchlist alert
```

- Step 3a/3b 可并行
- Step 4 全 green 时可省略 target 偏离 section
- 输出分支: 有异常 -> 全表；无异常 -> 轻量 3 行

### Weekly flow

```text
[Daily Step 1-4]
  ->
Step 5: risk-assessor(完整 12 step)
  ->
Step 6: strategist(问题定位 + action plan)
  -> 有问题(exit-rule/偏离 red/value trap)
Step 7: screener(按 strategist 指定的 theme x region 找 Top3 + quality score)
  -> Screener 只找候选，不做买入判断
Step 8: reviewer(auto_review)
```

- Step 7 在 target 偏离 red / exit-rule / value trap 疑似时启动
- do-nothing check 不阻止 Screener；结果标记为 watchlist 候选
- 无问题 -> 输出“维持现状是最佳选择”，跳过 Step 7
- weekly 的 target 偏离即使全 green 也展示

### Weekly progress

```text
[Step 1-4 完成 ~3min] -> 先展示 daily 数据
[Step 5 完成 ~5min]   -> 展示风险判定
[Step 6-7 完成 ~8min] -> 展示 action plan + 候选
[Step 8 完成 ~10min]  -> 展示 review
```

**Phase 摘要不得省略:**

- TODO / target reminder(target note 件数和内容)
- CRITICAL / EXIT 判定
- conviction symbol 警告

### 与 morning summary 的差异

| 项目 | Morning summary | Daily check | Weekly review |
|:---|:---|:---|:---|
| 时间 | 30 秒 | 3-4 分钟 | 8-13 分钟 |
| 异常检测 | detect_alerts | + HC 全持仓 | + HC 全持仓 |
| PF 盈亏 | 无 | 全 symbol 表 | 全 symbol 表 |
| 市场 | 无 | 主要指标 + 新闻 | 主要指标 + 新闻 |
| 偏离检查 | 无 | yellow/red | 全项 |
| 风险判定 | 无 | 无 | 完整 12 step |
| 行动建议 | 无 | 无 | 带 What-If |
| 筛选 | 无 | 无 | 条件触发 Top3 |
| Reviewer | 无 | 无 | 自动 |

### 数据保存

Routine 结果保存到 `data/session_logs/routine/`:

- `daily_YYYYMMDD.json`
- `weekly_YYYYMMDD.json`

## Conviction violation detection(KIK-729)

Strategist 输出后，orchestrator 必须自动执行:

1. `notes.load_notes(note_type="thesis")` 获取 conviction symbol
2. 从 Strategist 输出中抽取卖出建议 symbol
3. 如果二者交叉，设置 `context: conviction_violation`
4. 命中 `auto_review.trigger.context: conviction_violation` -> 强制启动 Reviewer

该检查必须是机制强制，不依赖主观记忆。

## Thesis Check(KIK-715)

HC / Strategist 完成后，机械检查 PF symbol 的 thesis 引用。由 `orchestration.yaml` 的 `thesis_check` 定义，并在 auto_review 前执行。

1. `load_notes(note_type="thesis")` 获取所有 PF symbol thesis
2. 有 thesis 但输出未引用 -> 通知 thesis 未引用
3. 未注册 thesis 的 symbol -> 通知 thesis 未注册
4. PF 外单下一步分析可按 `skip_condition: no_portfolio_context` 跳过

## History Check(KIK-740)

当分析包含投资判断(卖出/买入/换仓/rebalance/止损/止盈等)时，自动用 4 LLM 并行检查历史相似案例。使用 LLM 内置知识和 Web 搜索，不维护本地案例库。

### 自动触发条件

任一成立即触发:

1. `routing.yaml` pattern 有 `history_check: true`
2. 用户输入含投资判断关键词:
   - 卖出 / 止损 / 止盈 / 退出
   - 买入 / 加仓 / 新 entry
   - 换仓 / rebalance / 改善 / 调整
   - 历史 / 过去 / 案例 / pattern

### 不触发

- 单纯信息查询
- morning summary / `mode: routine-*`
- 单独 health-checker / risk-assessor
- conviction symbol 的持有确认级别问题

### 4 LLM 分工

只启动已设置 API key 的 LLM，必须 graceful degradation。

| LLM | 角色 | 范围 | 调用 |
|:---|:---|:---|:---|
| Claude Code | Portfolio Aligner | PF 一致性、整合判断、用户历史 | orchestrator 直接执行 |
| GPT | Devil's Advocate | 反证、失败案例 | `call_llm('gpt', ...)` |
| Gemini | Lesson Auditor | Google 搜索补充案例 | `call_llm('gemini', ..., web_search=True)` |
| Grok | Sentiment Analyst | X 市场类似反应 | `tools/grok.py` or `call_llm('grok', ...)` |

API key 检测在 orchestrator 层进行，环境变量包括 `OPENAI_API_KEY`、`GEMINI_API_KEY`、`XAI_API_KEY`。只有 Claude Code 可用时要明说“仅用内部知识执行”。

数据不足时，不用推测补完；明确“无足够案例”。至少需要成功案例 1 件、失败案例 2 件。

### 共通 prompt template

```text
Symbol: {symbol}
Context: {context}
  Earnings: {earnings_summary}
  Price: {price_summary}
  Fundamentals: {fundamentals}
  Relevant lessons: {lessons}
Decision theme: {decision_theme}

请按以下结构列出历史相似案例:
- 成功案例(至少 1 件): 相似状态后恢复的公司和原因
- 失败案例(至少 2 件): 相似状态后衰退或破产的公司和原因
- 与当前 symbol 的相似度(高/中/低)+ 理由
- 反证点(必须包含)
```

### 结果整合

```markdown
## 📚 历史相似案例

### 全 LLM 一致点
- ...

### 意见分歧
- Codex: ...
- GPT: ...
- Gemini: ...
- Grok: ...

### 综合判断
- 最终判断: ...
- 反证 pattern: ...
```

**MUST:** 禁止只展示成功或只展示失败，必须两边都列。必须包含反证点。

### 与 DeepThink 区分

| 项目 | history_check(KIK-740) | DeepThink |
|:---|:---|:---|
| 启动 | 自动 | 明示触发 |
| round | 1 | 多轮直到收敛 |
| 时间 | 30-60 秒 | 15-30 分钟 |
| LLM | 4 并行 1 round | 4 并行 + loop |
| 用途 | 给现有判断增加历史视角 | 战略重设和复杂 scenario |
| 成本 | 低 | 较高 |

同一 session 已执行过 history_check 时跳过。

## Reviewer 启动方针(KIK-659 / KIK-729)

Agent 执行后，按 `orchestration.yaml` 的 `auto_review` / `adhoc_review` 规则分 3 类控制 Reviewer。

| 类型 | 对象 | 动作 |
|:---|:---|:---|
| 自动 | 交易确认前 / conviction violation / weekly routine strategist 输出 | 强制执行 |
| Adhoc | 单下一步 strategist / screener 单独 / `review: true` / 输出含投资判断关键词 | Layer 4 末尾提示 reviewer 检查；下一轮用户确认后启动 |
| Skip | health-checker / researcher / analyst / risk-assessor 单独执行 | 不显示 |

`agent_includes` 表示 agents 数组中包含目标 agent 即 match。`agent_only` 表示数组长度为 1 且仅该 agent。

### Adhoc UX

```text
🔍 Reviewer 执行中...
  ├─ Risk (GPT)    ⏳
  ├─ Logic (Gemini) ⏳
  └─ Data (Codex)  ⏳
```

结果:

- PASS -> 1 行“3 视角 LGTM”
- WARN -> 每个视角 1 行 + 对应引用 + “忽略/反映”选择
- FAIL -> FAIL 理由 + 修正方案 + 等待批准

同一 session 已执行 Reviewer 时避免重复执行。

### Reviewer lesson 注入

启动 Reviewer 前，用 `tools/notes.py` 的 `load_notes(note_type="lesson")` 从本地读取 lesson 并注入 prompt。即使 Neo4j 不可用，也必须从 `data/notes/` 读取。

Prompt 信息:

1. agent.md + examples.yaml key points
2. review target 全文
3. 用户原始输入
4. 过去 lesson 列表

## Direct Actions(记录类操作)

`routing.yaml` 中 `action: direct` 的操作不需需要 agent，由 orchestrator 直接执行。

### 写入

| 操作 | 工具 | 保存位置 |
|:---|:---|:---|
| 投资 note(thesis/concern/lesson/observation/review/target/journal) | `tools/graphrag.py` merge_note | CSV master + Neo4j view |
| watchlist add/delete | CSV direct IO | CSV master + Neo4j view |
| trade record(buy/sell) | `tools/graphrag.py` merge_trade | CSV master + Neo4j view |
| cash balance update | JSON direct IO | data/cash_balance.json |

### 读取

| 数据 | 使用 agent | 用途 |
|:---|:---|:---|
| 投资 note | Analyst, Strategist | 历史分析和 thesis 对照 |
| lesson | Strategist, Reviewer | 判断前约束和 bias 修正 |
| watchlist | Screener | 与候选去重 |
| trade record | Health Checker, Analyst | PF 诊断、持有人视角 |
| cash balance | Health Checker, Strategist | PF 全貌和买入预算 |

## 数据同步(KIK-676/677)

用户说同步、sync、数据一致性检查时，执行 data/ -> GraphRAG 的差分检测和同步。

Flow:

1. 读取 `data/sync_status.yaml` 的 last_sync
2. 检测比 last_sync 更新的文件
3. 展示差分表
4. 用户确认后从本地同步到 GraphRAG
5. 更新 `data/sync_status.yaml`

同步对象:

| data/ | GraphRAG node | 同步函数 |
|:---|:---|:---|
| data/notes/*.json | Note | merge_note() |
| data/history/screen/*.json | Screen + SURFACED | merge_screen() |
| data/history/trade/*.json | Trade + BOUGHT/SOLD | merge_trade() |
| data/history/report/*.json | Report + ANALYZED | merge_report() |
| data/history/research/*.json | Research | merge_note() |
| data/history/health/*.json | HealthCheck | merge_note() |
| data/portfolio.csv | Portfolio + HOLDS | sync_portfolio() |
| data/cash_balance.json | MarketContext (cash) | merge_note(type=cash) |

同步方向永远是本地 -> GraphRAG。graph_store 函数用 MERGE，避免重复注册。

TEI 可用时从 semantic_summary 生成 embedding；TEI 不可用时跳过 embedding 并 graceful degradation。

## 数据保存原则

- Master: data/(JSON/CSV)，始终保存
- View: GraphRAG / Neo4j，仅连接时 dual-write 或由 sync 执行
- 没有 GraphRAG 也必须工作

## Orchestration(自律修正 loop)

按 `orchestration.yaml` 控制 agent 后处理:

- 筛选 0 件 -> 放宽条件并自动 retry(最多 2 下一步)
- Reviewer PASS/WARN -> 直接输出
- Reviewer FAIL -> 展示 FAIL 理由和修正方案，用户批准后 retry(最多 2 下一步)
- 达 retry 上限 -> 输出当前结果

## Post-Action

### 1. 展示结果

向用户展示 agent 输出。Reviewer 自动插入由 `orchestration.yaml` 的 `auto_review` 控制。

### 2. 自主保存(KIK-674)

Agent 执行后，结果保存到 data/，不需要等待用户指示。

| Agent | data/ 保存路径 |
|:---|:---|
| Screener | data/screening_results/{preset}_{date}.json |
| Analyst | data/reports/{symbol}_{date}.json |
| Researcher | data/research/{topic}_{date}.json |
| Health Checker | data/session_logs/{date}.json |
| Strategist | data/session_logs/{date}.json |
| Reviewer | data/reviews/{date}.json |

原则:

- data/ 始终保存
- GraphRAG 不自动写入，除非用户要求 sync
- 保存最终责任在 orchestrator。即使 sub-agent 声称已保存，也必须自己确认文件存在，不存在则保存

保存后必须显示:

```text
💾 data/screening_results/trending_us_20260420.json
```

Neo4j 可用时可询问是否 sync；不可用时不提示。

```python
from src.data.graph_store._common import is_available
if is_available():
    ...
```

### 3. Sync

用户明确要求 sync 或接受 sync 提议时，执行 data/ -> GraphRAG 单向同步。

### 4. 学习记录建议

如果结果包含新的 lesson 价值，询问是否记录:

- Reviewer WARN/FAIL
- 与历史 lesson 矛盾
- 用户反应出乎预期
- 筛选出现新 theme 或新视角

```text
📝 要记录这条 lesson 吗？
例: “防御股不一定在地缘事件中上涨”
```

用户同意后，用 `tools/notes.py` 的 `save_note(note_type="lesson")` 保存到 `data/notes/`。Neo4j 可用时再 sync。

### 5. 下一步

提出 1-2 个自然下一步，并继承刚才的 symbol 和结果。

## Layer 5: Cited Sources(KIK-739)

目的: 可视化“结论依赖了什么”，避免旧信息变成 stale context。

### 适用条件

必须输出 Layer 5:

- 投资判断、交易建议、trim、rebalance
- DeepThink Step 5
- Strategist 最终建议
- weekly routine 报告
- `routing.yaml` 中 `layer5: required`

可跳过:

- health-checker 单独
- risk-assessor 单独
- 纯事实查询(Pattern A)

### 输出格式

`src/data/citation_formatter.format_cited_sources(cited_lessons, cited_theses, used_for_map)` 返回 markdown block，追加到正文末尾。

```markdown
## 📚 Cited Sources

### Lessons
- 🟢 [permanent] 2026-04-24 PF balance normal — Cash 15-20% 判断
- 🟢 [permanent] 2026-04-25 7751.T HOLD-LOCK — 排除卖出对象
- 🟡 [seasonal/45d] 2026-03-22 hedge when rates >4% — 若环境变化需复核

### Theses
- 🔒 [conviction] 2026-04-25 7751.T hold locked
- 🟢 2026-04-24 MSFT thesis — dip buy rationale
```

### Freshness marker

| marker | 条件 |
|:---:|:---|
| 🟢 | `permanent` tag 或 30 天内 |
| 🟡 | `seasonal` tag 且 31-90 天 |
| 🔴 | `seasonal` tag 且 91 天以上，或 date 不明 |
| ⛔ | `expired` tag，自动排除 |
| 🔒 | thesis with `conviction_override=true` |

### Citation 抽取

DeepThink Step 5 用 `verify_lesson_cited()` 成功后的列表自动抽取:

```python
cited_lessons = [l for l in relevant_lessons if l.get("id") not in missing_lesson_ids]
```

verify abort 时不会出现 citation 为 0 的最终报告。

## References

- Routing few-shot: [routing.yaml](./routing.yaml)
- 自律修正 loop: [orchestration.yaml](./orchestration.yaml)
- Citation formatter: [src/data/citation_formatter.py](../../../src/data/citation_formatter.py)
