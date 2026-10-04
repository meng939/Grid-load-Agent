"""工具 0：从 ERCOT 公开接口下载逐小时 System Load（真实负荷数据）。

用途：把真实负荷 CSV 灌入 data/pjm_load_cache.csv，替代仿真数据。

两条路径：
  A. 自动下载（需注册 ERCOT API key）：
     1. 去 https://api.ercot.com 注册账号，生成 API Key
     2. 运行：python tools/fetch_ercot.py --api-key 你的key --start 2024-01-01 --end 2024-12-31
  B. 手动下载（免注册）：
     1. 浏览器打开 https://www.ercot.com/marketinfo/loads
     2. 选日期范围（至少 1 年）→ Download CSV
     3. 把下载的文件复制为 project/data/ercot_load_raw.csv
     4. 运行：python tools/fetch_ercot.py --local data/ercot_load_raw.csv

两种路径最终都产出 data/pjm_load_cache.csv（timestamp, load_mw 两列），
之后 fetch_data 自动读到真实数据。
"""

import argparse
import io
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUT_FILE = DATA_DIR / "pjm_load_cache.csv"


def _auto_download(api_key: str, start: str, end: str) -> pd.DataFrame:
    """ERCOT public API v1：逐小时 System Load。

    接口：GET https://api.ercot.com/api/download?fileIdentifier=SystemLoad
    &fileTimestamp=<start>Z&api_key=<key>
    返回 CSV 含 columns: timestamp, value (MW)。
    """
    import requests

    url = (
        "https://api.ercot.com/api/download"
        f"?fileIdentifier=SystemLoad"
        f"&fileTimestamp={start.replace('-', '')}T000000Z"
        f"&api_key={api_key}"
    )
    print(f"downloading {url[:80]}...")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    print(f"  fetched {len(df)} rows")
    return df


def _load_local(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    print(f"loaded local {path}: {len(df)} rows")
    return df


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """把 ERCOT 原始 CSV 规整成 (timestamp, load_mw) 两列。

    兼容 ERCOT 常见列名：timestamp / value；或 date / load。
    """
    df = df.copy()
    # 列名映射
    rename = {}
    for col in df.columns:
        lc = col.lower().strip()
        if lc in ("timestamp", "time", "datetime", "date"):
            rename[col] = "timestamp"
        elif lc in ("value", "load", "load (mw)", "system load", "load_mw", "mw"):
            rename[col] = "load_mw"
    df = df.rename(columns=rename)

    if "timestamp" not in df.columns:
        raise ValueError(f"未找到时间列，当前列：{list(df.columns)}；请确认 ERCOT CSV 格式")
    if "load_mw" not in df.columns:
        # 若存在 load 但带单位后缀，尝试取最接近的列
        candidates = [c for c in df.columns if "load" in c.lower() or "mw" in c.lower()]
        if candidates:
            df = df.rename(columns={candidates[0]: "load_mw"})
        else:
            raise ValueError(f"未找到负荷列，当前列：{list(df.columns)}")

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["load_mw"] = pd.to_numeric(df["load_mw"], errors="coerce")
    df = df.dropna(subset=["load_mw"]).set_index("timestamp").sort_index()

    # 若含日/月频率（非逐小时），重采样到小时
    if len(df) > 1:
        freq = df.index.to_series().diff().median()
        import pandas as _pd
        if freq > _pd.Timedelta("2h"):
            print("  非逐小时数据，重采样到小时")
            df = df.resample("h").mean().dropna()

    return df[["load_mw"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-key", default=None, help="ERCOT API key（路径 A 用）")
    ap.add_argument("--start", default="2024-01-01")
    ap.add_argument("--end", default="2024-12-31")
    ap.add_argument("--local", default=None,
                    help="手动下载的 ERCOT CSV 路径（路径 B 用）")
    args = ap.parse_args()

    if args.local:
        raw = _load_local(args.local)
    elif args.api_key:
        raw = _auto_download(args.api_key, args.start, args.end)
    else:
        print("需要 --api-key 或 --local 之一；"
              "API 注册见 https://api.ercot.com，手动下载见 "
              "https://www.ercot.com/marketinfo/loads")
        sys.exit(1)

    df = _normalize(raw)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_FILE)
    print(f"\n真实负荷数据已写入 {OUT_FILE}")
    print(f"  时间范围: {df.index.min()} -> {df.index.max()}  ({len(df)} 小时)")
    print(f"  负荷范围: {df['load_mw'].min():.0f} ~ {df['load_mw'].max():.0f} MW")
    print("\n下一步：python run.py --demo")


if __name__ == "__main__":
    main()
