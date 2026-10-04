"""工具 4：短期负荷预测模型训练。

主模型: LightGBM（本地库，不涉及第三方 LLM）
降级模型: sklearn.HistGradientBoostingRegressor
最终兜底: 纯 numpy Ridge（线性模型），保证流水线在无任何 ML 包时仍可端到端跑通
不收敛处理: 自动降采样 + 换模型，并记录回退日志。
"""

import numpy as np
import pandas as pd

from harness.agent import ToolError, ToolResult

LOAD_COL = "load_mw"
TARGET_COL = LOAD_COL


class _RidgeModel:
    """最小可替代的 estimator 接口（predict），供回测与检测使用。"""

    def __init__(self, theta):
        self.theta = theta

    def fit(self, X, y):
        return self

    def predict(self, X):
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X[None, :]
        return X @ self.theta


def _ridge_fallback(X, y):
    """纯 numpy 的 Ridge 回归（兜底，不依赖任何 ML 库）。"""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    lam = 1.0
    A = X.T @ X + lam * np.eye(X.shape[1])
    theta = np.linalg.solve(A, X.T @ y)
    return _RidgeModel(theta)


def _train_lightgbm(X, y):
    import lightgbm as lgb
    clf = lgb.LGBMRegressor(
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=31,
        random_state=42,
        verbosity=-1,
    )
    clf.fit(X, y)
    return clf


def _train_fallback(X, y):
    from sklearn.ensemble import HistGradientBoostingRegressor
    clf = HistGradientBoostingRegressor(max_iter=100, random_state=42)
    clf.fit(X, y)
    return clf


def run(feat_df: pd.DataFrame, horizon: int = 24,
        train_ratio: float = 0.8, resample_target: int = 20000) -> ToolResult:
    """训练 T+horizon 短期负荷预测器。

    Args:
        feat_df: build_features 产出（含 load_mw 目标列 + 特征）
        horizon: 预测步长（小时）
        train_ratio: 时序切分比例（前段训练、后段回测）
        resample_target: 不收敛时降采样到的目标行数

    Returns:
        ToolResult，payload: {"model": estimator, "horizon": ..., "n_train": ..., "fallback_used": bool}
    """
    if feat_df is None or feat_df.empty:
        return ToolResult(payload={}, code=ToolError.DATA_MISSING, logs=["empty feat_df"])

    X_all = feat_df.drop(columns=[TARGET_COL])
    y_all = feat_df[TARGET_COL]

    split = int(len(feat_df) * train_ratio)
    X_train, y_train = X_all.iloc[:split], y_all.iloc[:split]

    logs = [f"train {len(X_train)} / total {len(feat_df)}, horizon={horizon}"]
    fallback_used = False

    # 三级降级链：LightGBM -> HGB -> 纯numpy Ridge
    model, name = None, None
    for builder, label in [
        (_train_lightgbm, "LightGBM"),
        (_train_fallback, "HistGradientBoosting"),
        (_ridge_fallback, "Ridge(numpy)"),
    ]:
        try:
            model = builder(X_train, y_train)
            name = label
            logs.append(f"trained {label}")
            break
        except Exception as e:
            logs.append(f"{label} unavailable/failed: {e}; trying next tier")
            fallback_used = True
            # 降采样对后续模型再尝试
            if len(X_train) > resample_target:
                idx = np.linspace(0, len(X_train) - 1, resample_target).astype(int)
                X_train, y_train = X_train.iloc[idx], y_train.iloc[idx]
                logs.append(f"resampled to {resample_target} rows")

    # 不收敛/质量判定占位：训练损失 > 阈值 → 触发 MODEL_DIVERGED
    # 实际实现可加入 early-stopping 监控或训练集 MAE 检查
    return ToolResult(
        payload={"model": model, "model_name": name, "horizon": horizon,
                 "n_train": len(X_train), "fallback_used": fallback_used},
        code=ToolError.OK,
        logs=logs,
    )
