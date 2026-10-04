"""工具 7：验证报告生成（基线对照 + 阈值判定 + HTML 产物）。

所有指标落盘到 validation/，报告落盘到 reports/。
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from harness.agent import ToolError, ToolResult

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VALIDATION_DIR = PROJECT_ROOT / "validation"
REPORTS_DIR = PROJECT_ROOT / "reports"

# 与 backtest.py 保持一致的 MAPE 绝对上限；MAE 通过线改为由
# backtest 产出的 mae_threshold（自适应标定值）传入，不再写死 50MW。
MAPE_THRESHOLD = 5.0


def _verdict(metrics: dict, mae_threshold: float = float("inf")) -> str:
    if metrics["mae"] <= mae_threshold and metrics["mape"] <= MAPE_THRESHOLD:
        return "通过"
    return "未通过"


def run(metrics: dict, baseline_metrics: dict, events: list,
        anomaly_events: list, extra_logs: list = None,
        mae_threshold: float = None) -> ToolResult:
    """生成验证报告。

    Args:
        metrics: backtest 产出的指标
        baseline_metrics: 基线指标
        events: 预测回测事件（可为空）
        anomaly_events: detect_anomaly 产出
        extra_logs: 各工具日志汇总
        mae_threshold: 自适应 MAE 通过线（来自 backtest.payload["mae_threshold"]）

    Returns:
        ToolResult，payload: {"report_path": ..., "validation_path": ..., "verdict": ...}
    """
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if mae_threshold is None:
        mae_threshold = float("inf")
    verdict = _verdict(metrics, mae_threshold)
    all_logs = extra_logs or []

    # 指标 CSV
    val_df = pd.DataFrame([
        {"source": "model", "mae": metrics["mae"], "rmse": metrics["rmse"], "mape": metrics["mape"]},
        {"source": "baseline", "mae": baseline_metrics["mae"],
         "rmse": baseline_metrics["rmse"], "mape": baseline_metrics["mape"]},
    ])
    val_path = VALIDATION_DIR / "metrics.csv"
    val_df.to_csv(val_path, index=False)

    # 异常事件 CSV
    if anomaly_events:
        ev_df = pd.DataFrame(
            [{"start": s, "end": e, "attribution": a} for (s, e, a) in anomaly_events],
        )
        ev_path = VALIDATION_DIR / "anomaly_events.csv"
        ev_df.to_csv(ev_path, index=False)
    else:
        ev_path = None

    # HTML 报告
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rpt_path = REPORTS_DIR / f"report_{ts}.html"
    rpt = _render_html(metrics, baseline_metrics, anomaly_events, verdict, all_logs)
    rpt_path.write_text(rpt, encoding="utf-8")

    logs = [f"verdict={verdict} mae={metrics['mae']:.2f} mape={metrics['mape']:.2f}%"]
    code = ToolError.REPORT_THRESHOLD_EXCEEDED if verdict == "未通过" else ToolError.OK
    return ToolResult(
        payload={"report_path": str(rpt_path), "validation_path": str(val_path),
                 "events_path": str(ev_path) if ev_path else None,
                 "verdict": verdict, "mae_threshold": mae_threshold},
        code=code,
        logs=logs,
    )


def _render_html(metrics, baseline, anomaly_events, verdict, logs) -> str:
    table_rows = [
        ["模型", f"{metrics['mae']:.2f}", f"{metrics['rmse']:.2f}",
         f"{metrics['mape']:.2f}", "本报告"],
        ["基线(昨日同期)", f"{baseline['mae']:.2f}", f"{baseline['rmse']:.2f}",
         f"{baseline['mape']:.2f}", "对照"],
    ]
    rows = "".join(
        f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td></tr>"
        for r in table_rows
    )
    ev_rows = "".join(
        f"<tr><td>{str(s)}</td><td>{str(e)}</td><td>{a}</td></tr>"
        for (s, e, a) in (anomaly_events or [])
    )
    log_rows = "".join(f"<li>{x}</li>" for x in logs)
    return f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>电力负荷预测验证报告</title>
<style>body{{font-family:sans-serif;margin:2rem}}table{{border-collapse:collapse;margin:1rem 0}}
td,th{{border:1px solid #ccc;padding:.4rem .8rem}}h1{{font-size:1.3rem}}</style></head>
<body>
<h1>电力负荷预测验证报告</h1>
<p>判定：<b>{verdict}</b></p>
<h2>指标对照</h2>
<table><tr><th>来源</th><th>MAE</th><th>RMSE</th><th>MAPE(%)</th><th>说明</th></tr>{rows}</table>
<h2>异常事件（{len(anomaly_events or [])} 个）</h2>
<table><tr><th>起</th><th>止</th><th>归因</th></tr>{ev_rows}</table>
<h2>运行日志</h2>
<ol>{log_rows}</ol>
</body></html>"""
