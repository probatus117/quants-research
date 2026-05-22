# 开发工作流规则

> 编码约定、依赖和测试基础设施参见 [development.md](development.md)。

## 原则

- 所有开发工作原则上在 worktree 上完成；不需要直接在 main 分支编辑
- 每个 issue 按 **设计 -> 实装 -> 单元测试 -> 代码审查 -> 集成测试** 五个阶段推进
- 集成测试可由多个 agent 视角并行验证，但本 Claude Code 会遵守当前平台的 sub-agent 使用限制

## 1. 创建 worktree

**推荐:** 使用 helper script 一下一步性设置(KIK-745)

```bash
bash scripts/setup_worktree.sh KIK-NNN [short-desc]
# -> 创建 worktree + 复制 sample fixture(不触碰个人 PF)
# -> 展开到 ~/stock-skills-kik{NNN}，可立即运行 pytest
```

手动创建时:

```bash
git worktree add -b feature/kik-{NNN}-{short-desc} ~/stock-skills-kik{NNN} main
mkdir -p ~/stock-skills-kik{NNN}/data
cp tests/fixtures/sample_portfolio.csv ~/stock-skills-kik{NNN}/data/portfolio.csv
cp tests/fixtures/sample_cash_balance.json ~/stock-skills-kik{NNN}/data/cash_balance.json
```

- 工作目录: `~/stock-skills-kik{NNN}`
- 分支名: `feature/kik-{NNN}-{short-desc}`
- 后续实装、测试和集成验证都在该 worktree 中执行

### Worktree 准备(KIK-745)

禁止把个人 PF(例如 `~/stock-skills/data/portfolio.csv`)复制进 worktree。误执行 `git add -f` 会泄露真实 symbol 和数量。

使用以下方式之一:

1. `tests/fixtures/sample_portfolio.csv` 的通用测试 symbol(推荐)
2. 通过环境变量只读引用个人数据:

```bash
export STOCK_SKILLS_DATA_DIR=$HOME/stock-skills/data
# 传给 tools/portfolio_io.py 的 csv_path 参数
```

## 2. 设计阶段

- 调查代码库并制定实装方针
- 明确影响范围、修改文件、测试方针
- 用户批准后再进入实装

## 3. 实装阶段

- 在 worktree 上修改代码
- `.py` 文件修改后，应保持 `conda run -n stock-skills-2 python -m pytest tests/ -q` 可通过
- 小步修改，小步验证

## 4. 单元测试

- 新模块添加对应测试文件
- 用 `conda run -n stock-skills-2 python -m pytest tests/ -q` 确认全量通过
- worktree 示例:

```bash
cd ~/stock-skills-kik{NNN}
conda run -n stock-skills-2 python -m pytest tests/ -q
```

## 5. 代码审查

测试通过后，从多角度检查变更。

| 审查视角 | 检查内容 |
| --- | --- |
| 架构 | 模块分割、职责边界、既有模式一致性、循环依赖 |
| 逻辑 | 计算正确性、边界情况、错误处理、异常值 guard |
| 测试 | 覆盖范围、边界值、mock 合理性、测试独立性 |

给审查者的信息:

- worktree 路径
- 修改文件列表
- diff 概要
- 设计意图摘要

小变更(1-2 个文件、无逻辑变更)可只做轻量审查。新模块或大规模重构需要完整审查。

## 6. 集成测试

实装完成后，从各 skill 入口验证自然语言流程。

| 测试视角 | 验证内容 |
| --- | --- |
| screener | 多种筛选模式和 region/preset/theme 推断 |
| analyst | 个股分析和 ETF 评估 |
| portfolio | Health Checker + Strategist 的 PF 诊断和建议 |
| researcher | 新闻、情绪、行业和市场研究 |

自然语言验证例:

```text
寻找日本股票的价值股 -> Screener
分析 7203.T -> Analyst
查看最新新闻 -> Researcher
PF 还好吗？ -> Health Checker
```

如果变更仅限某个 skill，可以只跑相关集成验证。共通模块(如 `src/data/common.py`, `src/data/ticker_utils.py`)变更需要完整验证。

## 7. 文档和规则更新

功能实装后、合并前必须检查以下内容。

| 对象 | 更新条件 | 更新内容 |
| --- | --- | --- |
| 相关 `agent.md` + `examples.yaml` | agent 角色或工具变化 | 判断流程、few-shot 例 |
| `routing.yaml` | 增加新的 intent 模式 | triggers、examples |
| `orchestration.yaml` | retry 或 review 条件变化 | 规则追加 |
| `AGENTS.md` / `CLAUDE.md` | 架构变化 | 架构图、工具列表 |
| `docs/data-models.md` | stock_info / stock_detail 字段变化 | schema 表 |
| `README.md` | 用户可见功能变化 | 使用方法、设置 |

判断基准:

- 新功能: 更新 agent.md + examples.yaml + routing.yaml + README.md
- 既有功能改善: 更新相关 agent.md + examples.yaml
- 纯 bug fix: 通常无需文档；行为变化时更新 agent.md

## 8. 完成

```bash
cd ~/stock-skills
git merge --no-ff feature/kik-{NNN}-{short-desc}
git push
git worktree remove ~/stock-skills-kik{NNN}
git branch -d feature/kik-{NNN}-{short-desc}
```

- 将 Linear issue 更新为 Done
