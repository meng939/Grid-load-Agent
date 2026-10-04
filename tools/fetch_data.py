"""工具 1：PJM 负荷数据获取。

带重试 + 本地缓存降级。
"""

from pathlib import Path

from harness.agent import ToolError, ToolResult

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOCAL_CACHE = DATA_DIR / "pjm_load_cache.csv"


def run(source: str = "pjm", max_retries: int = 3) -> ToolResult:
    """加载 PJM 逐小时负荷数据。

    Args:
        source: 数据源标识（"pjm" 走 PJM API，"local" 直接读缓存）
        max_retries: 网络重试次数

    Returns:
        ToolResult，payload: {"df": DataFrame, "rows": int, "cache_used": bool}
    """
    import pandas as pd

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if source == "local" or LOCAL_CACHE.exists():
        try:
            df = pd.read_csv(LOCAL_CACHE)
            # 兼容：首列可能是时间戳（无列名或列名非 timestamp）
            ts_col = "timestamp" if "timestamp" in df.columns else df.columns[0]
            df[ts_col] = pd.to_datetime(df[ts_col])
            df = df.set_index(ts_col).sort_index()
            if "load_mw" not in df.columns:
                # 取第一个数值列作为负荷
                num_cols = df.select_dtypes("number").columns
                if len(num_cols) == 0:
                    raise ValueError("缓存 CSV 中找不到 load_mw 或数值列")
                df = df.rename(columns={num_cols[0]: "load_mw"})
            return ToolResult(
                payload={"df": df[["load_mw"]], "rows": len(df), "cache_used": True},
                code=ToolError.OK,
                logs=[f"loaded local cache: {len(df)} rows"],
            )
        except Exception as e:
            return ToolResult(
                payload={},
                code=ToolError.DATA_MISSING,
                logs=[f"local cache read failed: {e}"],
            )

    # 在线拉取（占位）：实际实现按 PJM 数据接口
    # PJM 公开数据通常需通过 developer.pjm.com API 或开放数据门户下载
    # 此处保留占位逻辑，团队接入真实数据源后替换
    logs = []
    for attempt in range(1, max_retries + 1):
        logs.append(f"fetch attempt {attempt}/{max_retries}")
        try:
            # TODO: 替换为真实 PJM 下载逻辑，例如:
            # resp = requests.get(url, timeout=30)
            # df = pd.read_csv(io.BytesIO(resp.content))
            raise NotImplementedError(
                "PJM online fetch placeholder: 请下载 PJM 负荷 CSV 放入 "
                f"{DATA_DIR / 'pjm_load_raw.csv'} 或 {LOCAL_CACHE}"
            )
        except NotImplementedError:
            raise
        except Exception as e:
            logs.append(f"  failed: {e}")

    # 重试耗尽 → 降级本地缓存
    if LOCAL_CACHE.exists():
        df = pd.read_csv(LOCAL_CACHE)
        ts_col = "timestamp" if "timestamp" in df.columns else df.columns[0]
        df[ts_col] = pd.to_datetime(df[ts_col])
        df = df.set_index(ts_col).sort_index()
        if "load_mw" not in df.columns:
            num_cols = df.select_dtypes("number").columns
            df = df.rename(columns={num_cols[0]: "load_mw"}) if len(num_cols) else df
        return ToolResult(
            payload={"df": df[["load_mw"]], "rows": len(df), "cache_used": True},
            code=ToolError.FETCH_TIMEOUT,  # 标记降级过
            logs=logs + ["fallback to local cache"],
        )

    return ToolResult(payload={}, code=ToolError.FETCH_TIMEOUT, logs=logs)
