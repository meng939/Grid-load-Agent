"""异常注入模块（演示 + 验证闭环用）。

在干净负荷序列上注入 5 类异常，测试 AGH 各分支是否被正确触发。
"""

import numpy as np
import pandas as pd

TARGET_COL = "load_mw"
SEED = 42


def _rng():
    return np.random.default_rng(SEED)


def inject_missing(clean_df: pd.DataFrame, rate: float = 0.05) -> pd.DataFrame:
    """随机置空 `rate` 比例的样本，模拟数据缺失。"""
    rng = _rng()
    df = clean_df.copy()
    mask = rng.random(len(df)) < rate
    df.loc[mask, TARGET_COL] = np.nan
    return df


def inject_spikes(clean_df: pd.DataFrame, n: int = 10, z: float = 5.0) -> pd.DataFrame:
    """注入 n 个 z-sigma 瞬时尖峰，模拟传感器跳变。"""
    rng = _rng()
    df = clean_df.copy()
    s = df[TARGET_COL]
    mu, sd = s.mean(), s.std()
    idx = rng.choice(len(df), size=n, replace=False)
    signs = rng.choice([-1, 1], size=n)
    df.loc[df.index[idx], TARGET_COL] = mu + signs * z * sd
    return df


def truncate_train(clean_df: pd.DataFrame, keep_ratio: float = 0.3) -> pd.DataFrame:
    """截断训练样本，测试模型不收敛时的降采样/换模型分支。"""
    return clean_df.iloc[: int(len(clean_df) * keep_ratio)]


def exceed_threshold(metrics: dict, target_mae: float = 100.0) -> dict:
    """人为放大指标，测试 verify_report 未达标 → 重训分支。"""
    out = dict(metrics)
    out["mae"] = max(out["mae"], target_mae)
    out["mape"] = max(out["mape"], target_mae / 100 * 10)
    return out


def simulate_fetch_outage() -> None:
    """占位：模拟网络抖动导致 fetch_data 重试后降级本地缓存。"""
    pass


INJECTORS = {
    "missing": inject_missing,
    "spikes": inject_spikes,
    "truncate": truncate_train,
    "threshold": exceed_threshold,
    "fetch_outage": simulate_fetch_outage,
}
