# Grid Load Agent — AGH 电力负荷预测与异常检测闭环

## 项目定位
给定 PJM 电网逐小时负荷序列，AGH 自动完成：
数据获取 → 清洗 → 短期负荷预测（T+24h）→ 回测 → 异常事件检测与归因 → 生成带基线对照的验证报告；
数据缺失、传感器跳变或模型不收敛时自动降级并全程记录。

## 技术栈
- LLM 层：仅 Agnes 模型（AGH 内置）
- 数值/经典 ML：LightGBM / sklearn / statsmodels（本地库，不涉及第三方 LLM）
- 数据：PJM 公开负荷数据

## 快速开始
```bash
pip install -e .
python run.py --demo            # 主路径 + 自动注入异常 + 出报告
python run.py --baseline-only   # 仅基线对照
```

## 目录
- `tools/`      7 个可执行工具（AGH 注册）
- `harness/`    AGH 配置与 agent 定义
- `data/`       原始 + 清洗后数据
- `runs/`       每次运行产物
- `validation/` 基线对照 + 判定 CSV
- `reports/`    最终报告
- `docs/`       项目说明 / 分工声明 / 合规声明

## 模型合规声明
本作品所有 LLM 推理调用仅限 Agnes 模型；数值计算与经典机器学习使用本地开源库
（LightGBM/sklearn），不涉及任何第三方大模型推理接口。
