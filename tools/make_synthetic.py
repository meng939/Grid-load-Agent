"""生成仿真 PJM 风格负荷数据（临时缓存用）。

真实 PJM 数据下载通之前，先用它让全链路跑通。
生成 1 年逐小时序列：日周期 + 周周期 + 季节趋势 + 噪声。
"""

import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT = DATA_DIR / "pjm_load_cache.csv"


def generate(hours: int = 24 * 365, base_mw: float = 60000.0, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2025-01-01", periods=hours, freq="h")

    t = np.arange(hours)
    hour = ts.hour
    doy = ts.dayofyear
    dow = ts.dayofweek

    # 日周期：早晚双峰，夜间低谷
    daily = 0.18 * np.sin(2 * np.pi * (hour - 6) / 24) + 0.05 * np.sin(2 * np.pi * (hour - 18) / 24)
    # 周周期：周末略低
    weekly = -0.04 * (dow >= 5)
    # 季节：夏季高、冬季次高
    seasonal = 0.12 * np.cos(2 * np.pi * (doy - 15) / 365)
    # 趋势 + 噪声
    trend = 0.00002 * t
    noise = 0.015 * rng.standard_normal(hours)

    load = base_mw * (1 + daily + weekly + seasonal + trend + noise)
    df = pd.DataFrame({"load_mw": load}, index=ts)
    df.index.name = "timestamp"
    return df


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df = generate()
    df.to_csv(OUT)
    print(f"synthetic PJM-style data -> {OUT} ({len(df)} rows)")


if __name__ == "__main__":
    main()
