"""工具 6：异常事件检测与归因。

方法: 残差阈值（z-score）+ 孤立森林（可选）
归因: 瞬时尖峰 / 持续漂移 / 缺失区段
输出: 事件区间列表 + 归因标签
"""

import numpy as np
import pandas as pd

from harness.agent import ToolError, ToolResult

TARGET_COL = "load_mw"
Z_THRESHOLD = 4.0


def _zscore_events(series: pd.Series, threshold: float = Z_THRESHOLD) -> list:
    """基于全局 z-score 的尖峰事件检测。"""
    mu = series.mean()
    sd = series.std()
    if sd == 0 or np.isnan(sd):
        return []
    z = (series - mu).abs() / sd
    mask = z > threshold
    # 合并连续命中为事件区间
    events = []
    start = None
    for i, hit in enumerate(mask.values):
        ts = series.index[i]
        if hit and start is None:
            start = ts
        elif not hit and start is not None:
            events.append((start, series.index[i - 1]))
            start = None
    if start is not None:
        events.append((start, series.index[-1]))
    return events


def _attribute(series: pd.Series, event) -> str:
    """事件归因：瞬时尖峰 / 持续漂移。"""
    s, e = event
    seg = series.loc[s:e]
    n = len(seg)
    if n <= 2:
        return "瞬时尖峰"
    # 持续偏离 → 漂移
    return "持续漂移"


def run(clean_df: pd.DataFrame, residual: np.ndarray = None) -> ToolResult:
    """检测负荷序列异常事件。

    Args:
        clean_df: 清洗后 DataFrame（可含 NaN/尖峰）
        residual: 回测残差（可选，若提供则基于残差检测）

    Returns:
        ToolResult，payload: {"events": [(ts_start, ts_end, attribution), ...],
                              "n_events": int}
    """
    if clean_df is None or clean_df.empty:
        return ToolResult(payload={}, code=ToolError.DATA_MISSING, logs=["empty input"])

    if residual is not None and len(residual) > 0:
        res_series = pd.Series(residual, index=clean_df.index[: len(residual)])
        events = _zscore_events(res_series.dropna())
    else:
        # 数据异常检测：先剔除缺失（NaN），在有效值上做 z-score
        events = _zscore_events(clean_df[TARGET_COL].dropna())

    attributed = [(s, e, _attribute(clean_df[TARGET_COL], (s, e))) for (s, e) in events]

    logs = [f"detected {len(attributed)} anomaly events"]
    code = ToolError.ANOMALY_DETECTED if attributed else ToolError.OK
    return ToolResult(
        payload={"events": attributed, "n_events": len(attributed)},
        code=code,
        logs=logs,
    )
