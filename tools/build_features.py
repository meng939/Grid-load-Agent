"""工具 3：特征构造——时间特征 + 滞后 + 滚动统计。"""

import numpy as np
import pandas as pd

from harness.agent import ToolError, ToolResult

LOAD_COL = "load_mw"


def run(df: pd.DataFrame, lags: tuple = (1, 2, 3, 24, 168),
        rolling_windows: tuple = (24, 168, 336)) -> ToolResult:
    """在时间序列上构造预测特征。

    Args:
        df: 清洗后的 DataFrame（timestamp 索引）
        lags: 滞后阶数（168 = 7 天）
        rolling_windows: 滚动窗口（小时）

    Returns:
        ToolResult，payload: {"feat_df": DataFrame(含 load_mw 目标列 + 各特征)}
    """
    if df is None or df.empty:
        return ToolResult(payload={}, code=ToolError.DATA_MISSING, logs=["empty input"])

    feat = pd.DataFrame(index=df.index)
    feat["load_mw"] = df[LOAD_COL].astype(float)

    ts = feat.index
    feat["hour"] = ts.hour
    feat["dow"] = ts.dayofweek
    feat["is_weekend"] = (ts.dayofweek >= 5).astype(int)
    feat["month"] = ts.month
    feat["day_of_year"] = ts.dayofyear

    # 时间正弦编码（周期性平滑）
    feat["hour_sin"] = np.sin(2 * np.pi * feat["hour"] / 24)
    feat["hour_cos"] = np.cos(2 * np.pi * feat["hour"] / 24)

    for lag in lags:
        feat[f"load_lag_{lag}"] = feat["load_mw"].shift(lag)
    for w in rolling_windows:
        feat[f"load_rollmean_{w}"] = feat["load_mw"].shift(1).rolling(w).mean()
        feat[f"load_rollstd_{w}"] = feat["load_mw"].shift(1).rolling(w).std()

    feat = feat.dropna()
    n_feat = feat.shape[1]
    return ToolResult(
        payload={"feat_df": feat, "n_features": n_feat, "n_rows": len(feat)},
        code=ToolError.OK,
        logs=[f"features: {n_feat} cols, {len(feat)} rows"],
    )
