"""AGH 工具注册与 agent 定义。

所有工具均为可执行函数，返回结构化结果 + 异常码。
AGH 通过读取异常码决定是否走降级分支。
"""

from dataclasses import dataclass, field
from enum import IntEnum


class ToolError(IntEnum):
    OK = 0
    FETCH_TIMEOUT = 1
    DATA_MISSING = 2
    OUTLIER_DETECTED = 3
    MODEL_DIVERGED = 4
    BACKTEST_FAILED = 5
    ANOMALY_DETECTED = 6
    REPORT_THRESHOLD_EXCEEDED = 7


@dataclass
class ToolResult:
    """统一工具返回结构：payload + 异常码 + 日志。"""
    payload: dict = field(default_factory=dict)
    code: ToolError = ToolError.OK
    logs: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.code == ToolError.OK


def registry():
    """AGH 工具注册表：name -> callable。延迟导入，避免 tools<->harness 循环依赖。"""
    from tools import (
        fetch_data,
        clean_df,
        build_features,
        train_predictor,
        backtest,
        detect_anomaly,
        verify_report,
    )
    return {
        "fetch_data": fetch_data.run,
        "clean_df": clean_df.run,
        "build_features": build_features.run,
        "train_predictor": train_predictor.run,
        "backtest": backtest.run,
        "detect_anomaly": detect_anomaly.run,
        "verify_report": verify_report.run,
    }


# AGH agent 定义示例（YAML 形式，AGH 加载）。
# 注意：AGENT_SPEC 在模块导入时只求工具名列表，不实例化 callable，
# 以避免 tools <-> harness 循环导入；工具本体在 AGH 运行时通过 registry() 绑定。
def _tool_names() -> list:
    return [
        "fetch_data",
        "clean_df",
        "build_features",
        "train_predictor",
        "backtest",
        "detect_anomaly",
        "verify_report",
    ]


AGENT_SPEC = {
    "name": "grid-load-agent",
    "model": "agnes",  # 仅 Agnes 模型
    "tools": _tool_names(),
    "plan": [
        {"step": 1, "tool": "fetch_data", "on_error": "retry:3, fallback:local_cache"},
        {"step": 2, "tool": "clean_df", "on_error": "impute, mark"},
        {"step": 3, "tool": "build_features"},
        {"step": 4, "tool": "train_predictor", "on_error": "resample, fallback_model"},
        {"step": 5, "tool": "backtest", "on_error": "retrain"},
        {"step": 6, "tool": "detect_anomaly"},
        {"step": 7, "tool": "verify_report"},
    ],
}
