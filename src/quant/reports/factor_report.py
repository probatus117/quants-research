"""Markdown report generation for factor evaluation artifacts."""

from __future__ import annotations

from pathlib import Path


def _format_float(value: object, digits: int = 4) -> str:
    if value is None:
        return "NA"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "NA"


def render_factor_report(factor_summary: dict[str, object], coverage: dict[str, object]) -> str:
    """Render a compact Markdown factor evaluation report from exported artifacts."""
    warnings = coverage.get("warnings", [])
    warning_text = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- No coverage warning."
    ic_rows = []
    for row in factor_summary.get("ic_summary", []):
        ic_rows.append(
            "| {period} | {ic_mean} | {rank_ic_mean} | {icir} | {positive} | {obs} |".format(
                period=row.get("period"),
                ic_mean=_format_float(row.get("ic_mean")),
                rank_ic_mean=_format_float(row.get("rank_ic_mean")),
                icir=_format_float(row.get("icir")),
                positive=_format_float(row.get("ic_positive_ratio")),
                obs=row.get("observations"),
            )
        )
    quantile_rows = []
    for row in factor_summary.get("quantile_summary", []):
        if str(row.get("quantile")) in {"1", "5", "long_short"}:
            quantile_rows.append(
                "| {period} | {quantile} | {mean_return} | {obs} |".format(
                    period=row.get("period"),
                    quantile=row.get("quantile"),
                    mean_return=_format_float(row.get("mean_forward_return")),
                    obs=row.get("observations"),
                )
            )
    coverage_summary = coverage.get("summary", {})
    conclusion = "初步观察：该因子已有可计算 IC/Rank IC 与五分位收益，需结合 Phase 4 回测后再形成策略判断。"
    if warnings:
        conclusion = "初步观察：覆盖率存在不足，当前结果只能作为样本内诊断，暂不应外推为策略证据。"

    return "\n".join(
        [
            f"# Factor Evaluation Report: {factor_summary.get('factor_name')}",
            "",
            "## 因子定义",
            f"- Factor: {factor_summary.get('factor_name')}",
            f"- Score column: {factor_summary.get('factor_column')}",
            f"- Universe: {factor_summary.get('universe')}",
            "",
            "## 数据区间",
            f"- Date range: {factor_summary.get('start_date')} to {factor_summary.get('end_date')}",
            f"- Rows: {factor_summary.get('row_count')}",
            "",
            "## IC / Rank IC",
            "| Period | IC Mean | Rank IC Mean | ICIR | IC Positive Ratio | Observations |",
            "|---:|---:|---:|---:|---:|---:|",
            *ic_rows,
            "",
            "## 分组收益",
            "| Period | Quantile | Mean Forward Return | Observations |",
            "|---:|---:|---:|---:|",
            *quantile_rows,
            "",
            "## 覆盖率",
            f"- Threshold: {_format_float(coverage_summary.get('min_coverage_threshold'))}",
            f"- Factor coverage min: {_format_float(coverage_summary.get('factor_coverage_min'))}",
            warning_text,
            "",
            "## 初步结论",
            conclusion,
            "",
            "## 风险提示",
            "- Fixture 数据为离线样本，不代表真实可交易全市场。",
            "- 当前为单因子评价，不包含交易成本、换手、容量或行业/市值中性化。",
            "- 本报告只提供量化证据，不构成买卖建议。",
            "",
        ]
    )


def write_factor_report(factor_summary: dict[str, object], coverage: dict[str, object], output_path: str | Path) -> Path:
    """Write a Markdown factor evaluation report."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_factor_report(factor_summary, coverage), encoding="utf-8")
    return path
