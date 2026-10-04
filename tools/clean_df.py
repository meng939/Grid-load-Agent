"""工具 2：数据清洗——缺失检测 + 插补 + 跳变标记。

输入: fetch_data 产出的 DataFrame（列: load_mw 等）
输出: 清洗后 DataFrame + 插补率 + 跳变位置列表
"""

import numpy as np
import pandas as pd

from harness.agent import ToolError, ToolResult

LOAD_COL = "load_mw"


def _detect_jumps(series: pd.Series, sigma: float = 5.0, window: int = 24) -> list:
    """基于滚动均值 + 标准差检测跳变（传感器尖峰）。"""
    mu = series.rolling(window).mean()
    sd = series.rolling(window).std()
    mask = (series - mu).abs() > sigma * sd
    return [int(i) for i in series.index[mask.fillna(False)]]


def run(df: pd.DataFrame, fill_method: str = "linear") -> ToolResult:
    """清洗负荷序列。

    Args:
        df: 带 timestamp 索引、load_mw 列的 DataFrame
        fill_method: 缺失插补方式（linear / time 等）

    Returns:
        ToolResult，payload: {"clean_df": ..., "missing_rate": ..., "jumps": [...]}
    """
    if df is None or df.empty:
        return ToolResult(payload={}, code=ToolError.DATA_MISSING, logs=["empty input"])

    s = df[LOAD_COL].copy()
    missing_before = int(s.isna().sum())
    total = len(s)
    missing_rate = missing_before / total if total else 0.0

    # 跳变检测（在插补前）
    jumps = _detect_jumps(s)

    # 插补
    if fill_method == "linear":
        s = s.interpolate(limit_direction="both")
    elif fill_method == "none":
        # 保留原值（含尖峰/缺失），仅做缺失标记，不插补
        s = s
    else:
        s = s.ffill().bfill()

    clean_df = df.copy()
    clean_df[LOAD_COL] = s
    clean_df["imputed"] = (df[LOAD_COL].isna() & s.notna()).astype(int)

    logs = [
        f"missing {missing_before}/{total} ({missing_rate:.2%})",
        f"fill_method={fill_method}",
        f"jumps detected: {len(jumps)}",
    ]
    code = ToolError.OUTLIER_DETECTED if jumps else ToolError.OK
    return ToolResult(
        payload={"clean_df": clean_df, "missing_rate": missing_rate, "jumps": jumps},
        code=code,
        logs=logs,
    )
