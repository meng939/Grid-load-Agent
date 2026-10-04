"""工具 0：从你手头的 EIA 导出文件中抽取 EBA.US48-ALL.D.H 序列，
转换为逐小时负荷代理数据，灌入 data/pjm_load_cache.csv。

背景：
  EIA 导出文件是 16 个序列横向拼接，第 1 对列（0,1）是
  EBA.US48-ALL.D.H（US 48-state 发电量，MWh，逐小时）。
  美国电网总发电量 ≈ 总负荷，故该序列可用作负荷代理。

用法：
  python tools/fetch_eia_eba.py --eia "C:\\Users\\MR\\Downloads\\SeriesExport-10-03-2026-12-16-39.csv"

产出：
  data/pjm_load_cache.csv（timestamp, load_mw 两列）
"""

import argparse
import csv
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUT_FILE = DATA_DIR / "pjm_load_cache.csv"

# EIA 导出文件里 EBA.US48-ALL.D.H 固定占据第 0/1 列（timestamp, value）
EBA_COL_TS = 0
EBA_COL_VAL = 1
META_ROWS = 8  # 前 8 行是元信息（Series Key / Name / Units / Freq / Start / End / Source）


def _parse_ts(raw: str) -> pd.Timestamp:
    """EIA 时间戳格式：YYYYMMDDTHH（例 20260309T08）。"""
    m = re.match(r"(\d{8})T(\d{2})\d*", raw.strip())
    if not m:
        return pd.NaT
    date, hour = m.group(1), m.group(2)
    return pd.Timestamp(f"{date[:4]}-{date[4:6]}-{date[6:8]} {hour}:00:00")


def extract_eba(eia_path: str) -> pd.DataFrame:
    """从 EIA 多序列文件抽取 EBA.US48-ALL.D.H 列对。

    返回：DataFrame(index=timestamp, 列=load_mw)，已按时间升序、缺口插补。
    """
    with open(eia_path, "r", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    pts = []
    for r in rows[META_ROWS:]:
        if len(r) <= EBA_COL_VAL:
            continue
        ts_raw, val_raw = r[EBA_COL_TS].strip(), r[EBA_COL_VAL].strip()
        if not ts_raw or not ts_raw[0].isdigit() or not val_raw:
            continue
        ts = _parse_ts(ts_raw)
        if ts is pd.NaT:
            continue
        try:
            val = float(val_raw)
        except ValueError:
            continue
        pts.append((ts, val))

    pts.sort(key=lambda x: x[0])
    ts = pd.DatetimeIndex([p[0] for p in pts])
    vals = np.array([p[1] for p in pts], dtype=float)

    df = pd.DataFrame({"load_mw": vals}, index=ts)
    df = df[~df.index.duplicated(keep="first")]
    df = df.sort_index()

    # 缺口插补到逐小时（线性），保证时序连续
    if len(df) > 2:
        expected = pd.date_range(df.index.min(), df.index.max(), freq="h")
        df = df.reindex(expected)
        gap_rate = float(df["load_mw"].isna().mean())
        if gap_rate > 0:
            df["load_mw"] = df["load_mw"].interpolate(method="linear", limit_direction="both")
            print(f"  缺口插补：{gap_rate:.1%} 小时被线性填补")
        else:
            print("  无缺口，时序连续")

    return df[["load_mw"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eia", default=None,
                    help="你下载的 EIA 多序列 CSV 路径（含 EBA.US48-ALL.D.H 列对）")
    args = ap.parse_args()

    if not args.eia:
        default = r"C:\Users\MR\Downloads\SeriesExport-10-03-2026-12-16-39.csv"
        args.eia = default
        print(f"(未指定 --eia，使用默认路径 {default})")
    if not Path(args.eia).exists():
        print(f"EIA 文件不存在：{args.eia}，请用 --eia 指定正确路径")
        sys.exit(1)

    print(f"读取 EIA 文件：{args.eia}")
    df = extract_eba(args.eia)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # 写为两列（timestamp, load_mw），保证 fetch_data 可解析
    out = df.copy()
    out.index.name = "timestamp"
    out.reset_index().to_csv(OUT_FILE, index=False)
    print(f"\n负荷代理数据已写入 {OUT_FILE}")
    print(f"  时间范围: {df.index.min()} -> {df.index.max()}  ({len(df)} 小时)")
    print(f"  负荷范围: {df['load_mw'].min():.0f} ~ {df['load_mw'].max():.0f} MW")
    print(f"  说明: 该序列为 US48 小时发电量(MWh)，近似负荷代理；"
          f"严格负荷需后续用 PJM/ISO 数据替换")
    print("\n下一步：python run.py --demo")


if __name__ == "__main__":
    main()
