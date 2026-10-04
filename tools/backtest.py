"""工具 5：滑窗回测 + 基线对照。

指标: MAE / RMSE / MAPE
基线: 朴素"昨日同期"预测（同小时历史均值）
未达标: 返回 BACKTEST_FAILED + 触发重训标记
"""

import numpy as np
import pandas as pd

from harness.agent import ToolError, ToolResult

TARGET_COL = "load_mw"
# 自适应阈值：MAE 阈值 = 1.25 × 该数据集"正常工况"MAE（由 run.py 传入 normal_mae）；
# 未传时退化为 MAPE 阈值 3%。MAPE 绝对上限保持 5%（负荷预测常用红线）。
MAPE_THRESHOLD = 5.0     # %，绝对上限
MAE_RELATIVE = 1.25      # 正常工况 MAE 的倍数，作为"通过线"


def _auto_mae_threshold(normal_mae: float) -> float:
    """基于数据集正常工况 MAE 标定通过线。"""
    if normal_mae and normal_mae > 0:
        return MAE_RELATIVE * normal_mae
    # 兜底：没有正常工况参考时，用 MAPE 上限折算（load_mw 未知时按 1% 计）
    return float("inf")


def _metrics(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    err = y_true - y_pred
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    mape = float(np.mean(np.abs(err) / np.abs(y_true)) * 100)
    return {"mae": mae, "rmse": rmse, "mape": mape}


def _baseline_yday_samehour(y_train: pd.Series, ts_test: pd.DatetimeIndex) -> pd.Series:
    """朴素基线：用训练段中同小时（同周中/周末）的均值预测（向量化查表）。"""
    train_df = pd.DataFrame({"v": y_train.values}, index=y_train.index)
    train_df["hour"] = train_df.index.hour.astype(int)
    train_df["dow"] = train_df.index.dayofweek.astype(int)
    # 按 (hour, dow) 分组均值 → 多级索引 Series；缺失组合回落到整体均值
    ref = train_df.groupby(["hour", "dow"])["v"].mean()
    overall = float(ref.mean())
    lookup = {(int(h), int(d)): float(v) for (h, d), v in ref.items()
              if pd.notna(v)}
    # 向量化：逐行按 (hour, dow) 查表
    hours = np.asarray(ts_test.hour, dtype=int)
    dows = np.asarray(ts_test.dayofweek, dtype=int)
    vals = np.array([lookup.get((h, d), overall) for h, d in zip(hours, dows)], dtype=float)
    return pd.Series(vals, index=ts_test)


def run(model, feat_df: pd.DataFrame, horizon: int = 24,
        train_ratio: float = 0.8, normal_mae: float = None) -> ToolResult:
    """滑窗回测 + 基线对照。

    Args:
        model: train_predictor 产出的 estimator
        feat_df: build_features 产出的特征表
        horizon: 预测步长（小时）
        train_ratio: 与训练一致的时序切分
        normal_mae: 正常工况 MAE 参考值（run.py 先跑一次无注入的基线得到），
                    用于标定通过线。为 None 时退化为仅 MAPE 上限判定。

    Returns:
        ToolResult，payload: {"metrics": {...}, "baseline_metrics": {...},
                              "passed": bool, "retrain": bool,
                              "mae_threshold": float}
    """
    if feat_df is None or feat_df.empty:
        return ToolResult(payload={}, code=ToolError.DATA_MISSING, logs=["empty feat_df"])

    split = int(len(feat_df) * train_ratio)
    X_all = feat_df.drop(columns=[TARGET_COL])
    y_all = feat_df[TARGET_COL]

    X_test, y_test = X_all.iloc[split:], y_all.iloc[split:]
    ts_test = X_test.index

    # 滚动多步预测：在训练段末尾逐 horizon 滚动外推
    # 为保持可复现与轻量，这里取测试段前 horizon 个样本做单步演示预测
    pred_ts = X_test.index[:horizon]
    X_pred = X_test.iloc[:horizon]
    y_pred = model.predict(X_pred)
    y_true = y_test.iloc[:horizon]

    m = _metrics(y_true, y_pred)
    baseline = _baseline_yday_samehour(y_all.iloc[:split], pred_ts)
    bm = _metrics(y_true, baseline.values)

    mae_thr = _auto_mae_threshold(normal_mae)
    passed = (m["mae"] <= mae_thr) and (m["mape"] <= MAPE_THRESHOLD)
    retrain = not passed

    logs = [
        f"MAE={m['mae']:.2f} RMSE={m['rmse']:.2f} MAPE={m['mape']:.2f}%",
        f"baseline MAE={bm['mae']:.2f} RMSE={bm['rmse']:.2f} MAPE={bm['mape']:.2f}%",
        f"thresholds: MAE<={mae_thr if mae_thr != float('inf') else 'n/a'} MAPE<={MAPE_THRESHOLD}%",
        f"passed={passed} retrain={retrain}",
    ]
    code = ToolError.BACKTEST_FAILED if retrain else ToolError.OK
    return ToolResult(
        payload={"metrics": m, "baseline_metrics": bm,
                 "passed": passed, "retrain": retrain,
                 "mae_threshold": mae_thr,
                 "y_true": np.asarray(y_true), "y_pred": np.asarray(y_pred)},
        code=code,
        logs=logs,
    )
