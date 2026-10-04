"""一键复现入口。

用法:
  python run.py --demo             # 主路径 + 自动注入异常 + 出报告
  python run.py --baseline-only    # 仅跑基线对照
  python run.py --anomaly missing spikes threshold
"""

import argparse
from pathlib import Path

import pandas as pd

from harness.agent import ToolError, ToolResult
from tools import (
    fetch_data,
    clean_df,
    build_features,
    train_predictor,
    backtest,
    detect_anomaly,
    verify_report,
)
from anomaly_inject import INJECTORS, exceed_threshold

PROJECT_ROOT = Path(__file__).resolve().parent
RUNS_DIR = PROJECT_ROOT / "runs"


def log_step(name: str, res: ToolResult, logs: list) -> None:
    logs.extend([f"[{name}] " + x for x in res.logs])
    print(f"[{name}] code={res.code.name} -> {res.payload.get('n_rows') or ''}".rstrip())


def run_main(inject: list, logs: list) -> ToolResult:
    """执行 7 步主路径，按 AGENT_SPEC 的 on_error 策略降级。"""
    # 1. 数据获取（带重试 + 本地缓存降级）
    r1 = fetch_data.run(source="local")
    log_step("fetch_data", r1, logs)
    if r1.code != ToolError.OK and r1.code != ToolError.FETCH_TIMEOUT:
        return r1
    df = r1.payload["df"]

    # 异常注入（演示闭环分支）
    for kind in inject:
        fn = INJECTORS.get(kind)
        if fn is None:
            continue
        if kind in ("missing", "spikes"):
            df = fn(df)
            logs.append(f"[inject:{kind}] applied to df")
        elif kind == "threshold":
            # 指标层注入，在 backtest 后应用
            pass

    # 2. 清洗——两条用途：
    #    - 训练/回测用：线性插补，保证无 NaN（缺失误报不能进模型）
    #    - 异常检测用：fill_method="none" 保留尖峰与缺失，让数据异常可被捕获
    r2_train = clean_df.run(df, fill_method="linear")
    log_step("clean_df(train)", r2_train, logs)
    clean_df_out = r2_train.payload.get("clean_df")
    if clean_df_out is None:
        return r2_train

    r2_raw = clean_df.run(df, fill_method="none")
    log_step("clean_df(raw)", r2_raw, logs)
    raw_df = r2_raw.payload.get("clean_df", df)

    # 3. 特征（基于已插补的训练数据）
    r3 = build_features.run(clean_df_out)
    log_step("build_features", r3, logs)
    feat = r3.payload["feat_df"]

    # 4. 训练
    r4 = train_predictor.run(feat)
    log_step("train_predictor", r4, logs)
    if r4.code != ToolError.OK:
        return r4
    model = r4.payload["model"]

    # 4.5 正常工况 MAE 标定（自适应阈值锚点）：
    #     用【未注入异常】的数据单独走一遍 clean->features->backtest，
    #     得到干净工况下的 MAE，作为"通过线"基准。
    #     这样注入异常后 backtest 的 MAE 会显著高于该基准 → 自动判"未通过"，
    #     不注入时则判"通过"，判定与数据量级自洽。
    normal_mae = None
    if inject:
        r_clean_no = clean_df.run(r1.payload["df"], fill_method="linear")
        f_clean_no = build_features.run(r_clean_no.payload["clean_df"]).payload["feat_df"]
        r5_no = backtest.run(model, f_clean_no, normal_mae=None)
        normal_mae = r5_no.payload["metrics"]["mae"]
        logs.append(f"[calibrate] normal-condition MAE={normal_mae:.2f} "
                    f"(used as pass-line anchor)")

    # 5. 回测 + 基线（用 normal_mae 标定通过线）
    r5 = backtest.run(model, feat, normal_mae=normal_mae)
    log_step("backtest", r5, logs)
    if "threshold" in inject:
        r5.payload["metrics"] = exceed_threshold(r5.payload["metrics"])
        logs.append("[inject:threshold] metrics inflated for retrain-branch demo")

    # 6. 异常检测（基于保留尖峰/缺失的 raw 序列：数据异常在此被捕获）
    r6 = detect_anomaly.run(raw_df, residual=None)
    log_step("detect_anomaly", r6, logs)
    events = r6.payload.get("events", [])

    # 7. 验证报告
    r7 = verify_report.run(
        metrics=r5.payload["metrics"],
        baseline_metrics=r5.payload["baseline_metrics"],
        events=events,
        anomaly_events=events,
        extra_logs=logs,
        mae_threshold=r5.payload.get("mae_threshold"),
    )
    log_step("verify_report", r7, logs)
    return r7


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true",
                    help="主路径 + 注入 missing/spikes + 出报告")
    ap.add_argument("--baseline-only", action="store_true",
                    help="仅跑基线对照")
    ap.add_argument("--anomaly", nargs="*", default=[],
                    choices=list(INJECTORS.keys()),
                    help="指定注入异常类型")
    args = ap.parse_args()

    logs: list = []
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    if args.baseline_only:
        # 仅数据 + 回测基线
        r1 = fetch_data.run(source="local")
        log_step("fetch_data", r1, logs)
        r2 = clean_df.run(r1.payload["df"])
        log_step("clean_df", r2, logs)
        r3 = build_features.run(r2.payload["clean_df"])
        log_step("build_features", r3, logs)
        r4 = train_predictor.run(r3.payload["feat_df"])
        log_step("train_predictor", r4, logs)
        r5 = backtest.run(r4.payload["model"], r3.payload["feat_df"])
        log_step("backtest", r5, logs)
        print("baseline metrics:", r5.payload["baseline_metrics"])
    else:
        inject = ["missing", "spikes"] if args.demo else args.anomaly
        res = run_main(inject, logs)
        print("\n=== FINAL ===")
        print("verdict:", res.payload.get("verdict"))
        print("report:", res.payload.get("report_path"))
        print("validation:", res.payload.get("validation_path"))

    # 汇总日志落盘（UTF-8，避免控制台编码问题）
    run_log = RUNS_DIR / "run_log.txt"
    run_log.write_text("\n".join(logs), encoding="utf-8")
    print(f"\nlogs -> {run_log}")


if __name__ == "__main__":
    main()
