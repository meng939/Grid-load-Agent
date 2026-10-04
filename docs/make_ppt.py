# -*- coding: utf-8 -*-
"""生成《Grid Load Agent》项目介绍 PPT（12 页，含原生可编辑图表 + 闭环示意图）。

运行：python docs/make_ppt.py
产出：docs/Grid_Load_Agent_项目介绍.pptx
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt, Emu

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "pjm_load_cache.csv"
OUT = ROOT / "docs" / "Grid_Load_Agent_项目介绍.pptx"

# ---- 配色 ----
NAVY = RGBColor(0x0F, 0x17, 0x2A)      # 深底
BLUE = RGBColor(0x25, 0x63, 0xEB)      # 主色
LBLUE = RGBColor(0x93, 0xC5, 0xFD)
GREEN = RGBColor(0x16, 0xA3, 0x4A)
RED = RGBColor(0xDC, 0x26, 0x26)
AMBER = RGBColor(0xF5, 0x9E, 0x0B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREY = RGBColor(0x6B, 0x72, 0x80)
LIGHT = RGBColor(0xF3, 0xF6, 0xFC)
LINE = RGBColor(0xD6, 0xDE, 0xEA)


def set_bg(slide, color):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def add_text(slide, l, t, w, h, text, size=18, color=NAVY, bold=False,
             align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, font="Microsoft YaHei"):
    tb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.color.rgb = color
    r.font.bold = bold
    r.font.name = font
    return tb


def add_bullets(slide, l, t, w, h, items, size=15, color=NAVY, gap=6):
    tb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        r = p.add_run()
        r.text = it
        r.font.size = Pt(size)
        r.font.color.rgb = color
        r.font.name = "Microsoft YaHei"
    return tb


def add_header(slide, kicker, title, page_no):
    """统一内容页页眉：kicker 小字 + 大标题 + 页码 + 顶部分隔线。"""
    set_bg(slide, WHITE)
    add_text(slide, 0.6, 0.35, 9.0, 0.35, kicker, size=12, color=BLUE, bold=True)
    add_text(slide, 0.6, 0.68, 11.0, 0.7, title, size=28, color=NAVY, bold=True)
    # 分隔线
    ln = slide.shapes.add_connector(1, Inches(0.6), Inches(1.45), Inches(12.73), Inches(1.45))
    ln.line.color.rgb = LINE
    ln.line.width = Pt(1.2)
    # 页脚
    add_text(slide, 0.6, 7.05, 8.0, 0.3,
             "Grid Load Agent · AGH 电力负荷预测与异常检测闭环", size=9, color=GREY)
    add_text(slide, 12.2, 7.05, 1.1, 0.3, f"{page_no:02d}", size=9,
             color=GREY, align=PP_ALIGN.RIGHT)


def add_card(slide, l, t, w, h, title, body, tcolor=BLUE, bcolor=NAVY, tsize=15, bsize=12):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                  Inches(l), Inches(t), Inches(w), Inches(h))
    card.fill.solid()
    card.fill.fore_color.rgb = LIGHT
    card.line.color.rgb = LINE
    card.line.width = Pt(0.75)
    card.shadow.inherit = False
    tf = card.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.18); tf.margin_right = Inches(0.18)
    tf.margin_top = Inches(0.12); tf.margin_bottom = Inches(0.12)
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = title
    r.font.size = Pt(tsize); r.font.bold = True; r.font.color.rgb = tcolor
    r.font.name = "Microsoft YaHei"
    for seg in body:
        p2 = tf.add_paragraph()
        p2.space_before = Pt(3)
        r2 = p2.add_run(); r2.text = seg
        r2.font.size = Pt(bsize); r2.font.color.rgb = bcolor
        r2.font.name = "Microsoft YaHei"
    return card


def style_chart(chart, y_max=None, y_min=None):
    try:
        plot = chart.plots[0]
        va = chart.chart_area  # noqa
    except Exception:
        pass
    try:
        # 值轴范围
        if y_min is not None or y_max is not None:
            va = chart.value_axis
            if y_min is not None:
                va.minimum_scale = y_min
            if y_max is not None:
                va.maximum_scale = y_max
    except Exception:
        pass
    try:
        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(11)
    except Exception:
        pass


def main():
    df = pd.read_csv(DATA, parse_dates=["timestamp"], index_col="timestamp")
    tail = df.iloc[-24 * 30:]  # 最近 30 天负荷曲线

    # 回测 48 点数据（从 npz 读，保证与工具一致）
    z = np.load(ROOT / "data" / "ppt_data.npz", allow_pickle=True)
    y_true = z["y_true"]; y_pred = z["y_pred"]
    mae_m, mae_b, mape_m = float(z["mae"]), float(z["bmae"]), float(z["mape"])

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    # ============ S1 封面 ============
    s = prs.slides.add_slide(blank)
    set_bg(s, NAVY)
    add_text(s, 0.9, 1.5, 11.5, 0.5, "2026 江苏省 AI+科学与工程创新实践黑客松（高校组）",
             size=14, color=LBLUE)
    add_text(s, 0.9, 2.1, 11.5, 1.4, "Grid Load Agent", size=60, color=WHITE, bold=True)
    add_text(s, 0.9, 3.35, 11.5, 0.8, "电力负荷预测与异常检测 · AGH 智能体完整闭环",
             size=26, color=LBLUE, bold=True)
    add_text(s, 0.9, 4.4, 11.5, 0.5, "环境能源 × 数据科学 × 智能体工程", size=15, color=WHITE)
    add_text(s, 0.9, 6.3, 11.5, 0.4, "基于 Agnes Harness（AGH） · 模型调用仅限 Agnes · 可复现可验证",
             size=12, color=GREY)
    # 底部色条
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.9), Inches(5.15), Inches(11.5), Inches(0.06))
    bar.fill.solid(); bar.fill.fore_color.rgb = BLUE; bar.line.fill.background()

    # ============ S2 问题与价值 ============
    s = prs.slides.add_slide(blank)
    add_header(s, "PROBLEM & VALUE", "问题与价值", 2)
    add_card(s, 0.6, 1.7, 6.0, 2.3, "真实问题",
             ["电网短期负荷预测（T+24h）是电力调度的核心任务，",
              "直接关系发电计划、成本与安全。",
              "实际负荷序列常含缺失、传感器跳变、漂移，",
              "自动检测 + 归因是调度侧真实痛点。"], tsize=16, bsize=14)
    add_card(s, 6.9, 1.7, 5.8, 2.3, "本作品做什么",
             ["用 AGH 把“预测 + 异常”做成一条",
              "可复现、可验证的闭环，而非孤立模型：",
              "规划 → 调用 → 反馈 → 验证 → 异常处理。"], tsize=16, bsize=14)
    add_card(s, 0.6, 4.25, 12.1, 2.5, "为什么值得做（问题价值 × 学科融合）",
             ["环境能源（电网调度）× 数据科学（时序预测）× 智能体工程（Agent 闭环）",
              "异常检测闭环 = 多数队伍只做 happy path，我们做到全异常分支 + 自动验证",
              "公开数据完成验证，符合赛题“无硬件可用公开数据”之规定"], tsize=16, bsize=14,
             tcolor=GREEN)

    # ============ S3 技术方案总览 ============
    s = prs.slides.add_slide(blank)
    add_header(s, "TECHNICAL APPROACH", "技术方案总览", 3)
    add_text(s, 0.6, 1.7, 12.0, 0.5, "AGH 运行底座 + 7 个可执行工具 + 三级模型降级 + 异常注入闭环",
             size=15, color=GREY)
    # 7 工具横向卡片
    tools = ["① fetch_data\n数据获取·重试·缓存降级",
             "② clean_df\n缺失插补·跳变标记",
             "③ build_features\n时间/滞后/滚动特征",
             "④ train_predictor\nLightGBM 三级降级",
             "⑤ backtest\n滑窗回测·基线对照",
             "⑥ detect_anomaly\nz-score 尖峰·归因",
             "⑦ verify_report\n阈值判定·HTML 报告"]
    x = 0.6
    for i, t in enumerate(tools):
        head, sub = t.split("\n")
        add_card(s, x, 2.35, 1.68, 1.55, head, [sub], tsize=13, bsize=10.5,
                 tcolor=(BLUE if i < 4 else (GREEN if i < 6 else AMBER)))
        x += 1.78
    add_card(s, 0.6, 4.35, 12.1, 2.35, "三级模型降级链（不收敛自动换模型）",
             ["LightGBM（主）  →  HistGradientBoosting（降级）  →  纯 numpy Ridge（兜底）",
              "每级失败自动降采样 + 切换，并记录回退日志，保证无 ML 包也能跑通闭环"],
             tsize=16, bsize=14, tcolor=AMBER)

    # ============ S4 闭环示意（自绘） ============
    s = prs.slides.add_slide(blank)
    add_header(s, "CLOSED-LOOP DESIGN", "AGH 智能执行闭环", 4)
    steps = ["任务规划", "工具调用", "执行反馈", "结果验证", "异常处理"]
    colors = [BLUE, BLUE, BLUE, GREEN, AMBER]
    n = len(steps)
    box_w, box_h, y0 = 1.9, 1.0, 2.2
    gap = (12.1 - n * box_w) / (n - 1)
    x = 0.6
    for i, (st, c) in enumerate(zip(steps, colors)):
        bx = x + i * (box_w + gap)
        b = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(bx), Inches(y0),
                               Inches(box_w), Inches(box_h))
        b.fill.solid(); b.fill.fore_color.rgb = c
        b.line.color.rgb = c; b.shadow.inherit = False
        tf = b.text_frame; tf.word_wrap = True
        tf.margin_left = Inches(0.05); tf.margin_right = Inches(0.05)
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = f"{i+1}. {st}"
        r.font.size = Pt(15); r.font.bold = True; r.font.color.rgb = WHITE
        r.font.name = "Microsoft YaHei"
        if i < n - 1:
            ar = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW,
                                    Inches(bx + box_w + 0.03), Inches(y0 + box_h/2 - 0.12),
                                    Inches(gap - 0.06), Inches(0.24))
            ar.fill.solid(); ar.fill.fore_color.rgb = LINE
            ar.line.color.rgb = LINE; ar.shadow.inherit = False
    # 回环箭头：从“异常处理”回到“任务规划”
    add_text(s, 0.6, 3.45, 12.0, 0.4, "异常处理 → 回退到任务规划（换策略 / 重训 / 降级数据源），全程留痕",
             size=13, color=AMBER, align=PP_ALIGN.CENTER, bold=True)
    # 下方 5 行说明
    desc = ["AGH 输出结构化计划：每步绑定工具 + 输入 + 失败分支",
            "7 个工具均为可执行函数，非描述；返回结构化结果 + 异常码",
            "每步返回数值指标 + 日志，AGH 读反馈决定继续 / 换路",
            "自动对照朴素基线 + 自适应阈值 → 通过 / 未通过",
            "数据缺失 / 跳变 / 模型不收敛 / 回测不达标 / 接口超时，五类异常分支"]
    add_bullets(s, 1.2, 4.0, 11.0, 2.6, ["• " + d for d in desc], size=14, color=NAVY, gap=8)

    # ============ S5 数据 ============
    s = prs.slides.add_slide(blank)
    add_header(s, "DATA", "数据：公开电网负荷序列", 5)
    add_card(s, 0.6, 1.7, 5.5, 4.9, "数据源与口径",
             [f"来源：EIA 公开小时序列（US48 总需求代理）",
              f"样本：{len(df)} 小时（{df.index.min().strftime('%Y-%m-%d')} → {df.index.max().strftime('%Y-%m-%d')}）",
              f"量级：{df['load_mw'].min():.0f} ~ {df['load_mw'].max():.0f} MW",
              "特征：日周期 + 季节趋势 + 噪声",
              "合规：公开数据完成验证，无需硬件 / 远程设备"],
             tsize=16, bsize=13.5)
    # 原生折线图：最近 30 天
    cd = CategoryChartData()
    step = max(1, len(tail) // 30)
    idx = tail.iloc[::step]
    cd.categories = [t.strftime("%m-%d %H:%M") for t in idx.index]
    cd.add_series("负荷 (MW)", [round(v) for v in idx["load_mw"]])
    gf = s.shapes.add_chart(XL_CHART_TYPE.LINE, Inches(6.4), Inches(1.7),
                            Inches(6.35), Inches(4.9), cd)
    ch = gf.chart
    ch.has_title = True
    ch.chart_title.text_frame.text = "最近 30 天逐小时负荷（日周期清晰）"
    for r_ in ch.chart_title.text_frame.paragraphs[0].runs:
        r_.font.size = Pt(13); r_.font.color.rgb = NAVY; r_.font.bold = True
    style_chart(ch, y_min=int(df['load_mw'].min() * 0.95))
    try:
        ser = ch.plots[0].series[0]
        ser.format.line.color.rgb = BLUE
        ser.format.line.width = Pt(2)
        ser.smooth = False
    except Exception:
        pass

    # ============ S6 模型与特征 ============
    s = prs.slides.add_slide(blank)
    add_header(s, "MODEL & FEATURES", "特征工程与预测模型", 6)
    add_card(s, 0.6, 1.7, 5.9, 4.9, "19 维特征（build_features）",
             ["时间：hour / dow / is_weekend / month / day_of_year",
              "周期编码：hour_sin / hour_cos（平滑日周期）",
              "滞后：load_lag_1/2/3/24/168（168=7天）",
              "滚动：load_rollmean/std_24/168/336",
              "共 19 列，dropna 后训练"], tsize=16, bsize=13.5, tcolor=BLUE)
    add_card(s, 6.7, 1.7, 6.0, 4.9, "短期预测（train_predictor）",
             ["目标：T+24h 短期负荷预测",
              "主模型：LightGBM（本地开源库，非第三方 LLM）",
              "降级：HistGradientBoosting → 纯 numpy Ridge",
              "时序切分：前 80% 训练 / 后 20% 回测",
              "不收敛：自动降采样 + 换模型 + 回退日志"], tsize=16, bsize=13.5, tcolor=AMBER)

    # ============ S7 验证指标 ============
    s = prs.slides.add_slide(blank)
    add_header(s, "VALIDATION", "验证指标：模型 vs 朴素基线", 7)
    add_text(s, 0.6, 1.6, 12.0, 0.4,
             f"回测段 48 点：模型 MAE {mae_m:.0f} MW  比  基线 MAE {mae_b:.0f} MW  好 {mae_b/mae_m:.1f} 倍",
             size=15, color=NAVY, bold=True)
    # 原生柱状图：MAE 对比
    cd2 = CategoryChartData()
    cd2.categories = ["模型 MAE", "基线 MAE"]
    cd2.add_series("MAE (MW)", [round(mae_m), round(mae_b)])
    gf2 = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(2.15),
                             Inches(6.0), Inches(4.4), cd2)
    ch2 = gf2.chart
    ch2.has_title = True
    ch2.chart_title.text_frame.text = "MAE 对比（越低越好）"
    for r_ in ch2.chart_title.text_frame.paragraphs[0].runs:
        r_.font.size = Pt(13); r_.font.bold = True; r_.font.color.rgb = NAVY
    style_chart(ch2)
    try:
        pts = ch2.plots[0].series[0].points
        pts[0].format.fill.solid(); pts[0].format.fill.fore_color.rgb = GREEN
        pts[1].format.fill.solid(); pts[1].format.fill.fore_color.rgb = GREY
    except Exception:
        pass
    add_card(s, 7.0, 2.15, 5.7, 4.4, "指标口径",
             [f"MAE = {mae_m:.1f} MW（模型） / {mae_b:.1f} MW（基线）",
              f"MAPE = {mape_m:.2f}%（模型）",
              "基线：朴素“昨日同期”（同小时历史均值）",
              "自适应通过线：1.25 × 干净工况 MAE",
              "干净工况判“通过”，注入异常判“未通过”"],
             tsize=15, bsize=13, tcolor=GREEN)

    # ============ S8 预测 vs 实际 ============
    s = prs.slides.add_slide(blank)
    add_header(s, "FORECAST", "预测曲线：模型 vs 实际（48h）", 8)
    cd3 = CategoryChartData()
    cd3.categories = [str(i) for i in range(1, len(y_true) + 1)]
    cd3.add_series("实际 (MW)", [round(v) for v in y_true])
    cd3.add_series("预测 (MW)", [round(v) for v in y_pred])
    gf3 = s.shapes.add_chart(XL_CHART_TYPE.LINE, Inches(0.6), Inches(1.7),
                             Inches(8.2), Inches(4.9), cd3)
    ch3 = gf3.chart
    ch3.has_title = False
    style_chart(ch3)
    try:
        s1, s2 = ch3.plots[0].series
        s1.format.line.color.rgb = GREEN; s1.format.line.width = Pt(2)
        s2.format.line.color.rgb = RED; s2.format.line.width = Pt(2)
    except Exception:
        pass
    add_card(s, 9.1, 1.7, 3.6, 4.9, "读图",
             [f"48 小时滚动预测", f"模型贴合实际日周期",
              f"MAE {mae_m:.0f} MW", f"MAPE {mape_m:.2f}%", "峰值/谷值时刻对齐"],
             tsize=15, bsize=12.5, tcolor=BLUE)

    # ============ S9 异常处理矩阵 ============
    s = prs.slides.add_slide(blank)
    add_header(s, "ANOMALY HANDLING", "异常处理矩阵（核心得分点）", 9)
    rows = [
        ("异常类型", "注入方式", "AGH 行为", "验证证据"),
        ("数据缺失", "随机置空 5%", "clean_df 标记+插补，记录插补率", "插补前后对比"),
        ("传感器跳变", "注入 10 个 5σ 尖峰", "detect_anomaly 捕获+归因“瞬时尖峰”", "事件列表+位置"),
        ("模型不收敛", "截断训练样本", "降采样 + 换模型（三级降级）", "回退日志"),
        ("回测不达标", "阈值未过", "verify_report 标红 + 触发重训", "基线对照表"),
        ("接口超时", "模拟网络抖动", "fetch_data 重试 3 次 + 降级缓存", "重试日志"),
    ]
    tbl_shape = s.shapes.add_table(len(rows), 4, Inches(0.6), Inches(1.7),
                                   Inches(12.1), Inches(4.6))
    tbl = tbl_shape.table
    widths = [2.2, 3.4, 4.0, 2.5]
    for i, w in enumerate(widths):
        tbl.columns[i].width = Inches(w)
    for r in range(len(rows)):
        for c in range(4):
            cell = tbl.cell(r, c)
            cell.text = rows[r][c]
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if c else PP_ALIGN.CENTER
            for run in p.runs:
                run.font.size = Pt(12 if r else 13)
                run.font.name = "Microsoft YaHei"
                run.font.bold = (r == 0)
                run.font.color.rgb = WHITE if r == 0 else NAVY
            cell.fill.solid()
            cell.fill.fore_color.rgb = NAVY if r == 0 else (LIGHT if r % 2 else WHITE)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = Inches(0.08); cell.margin_right = Inches(0.08)
    add_text(s, 0.6, 6.45, 12.0, 0.4,
             "演示时主动触发至少 2 类异常（missing + spikes），证明 AGH 真实读反馈、走分支",
             size=13, color=AMBER, bold=True)

    # ============ S10 结果与可复现 ============
    s = prs.slides.add_slide(blank)
    add_header(s, "RESULTS & REPRODUCE", "结果与一键复现", 10)
    add_card(s, 0.6, 1.7, 6.0, 4.9, "验证结果",
             [f"模型 MAE {mae_m:.0f} MW，比朴素基线好 {mae_b/mae_m:.1f} 倍",
              f"MAPE {mape_m:.2f}%",
              "注入 10 个 5σ 尖峰 100% 捕获 + 归因",
              "缺失 5% 检测 + 线性插补",
              "干净工况判“通过”，注入异常判“未通过”"],
             tsize=16, bsize=13.5, tcolor=GREEN)
    add_card(s, 6.8, 1.7, 5.9, 4.9, "一键复现（评委 5 分钟跑通）",
             ["python tools\\fetch_eia_eba.py   # 真实数据入缓存",
              "python run.py --demo             # 主路径+注入+出报告",
              "python run.py --anomaly threshold # 重训分支",
              "产物：reports/ HTML + validation/ CSV + runs/ 日志"],
             tsize=16, bsize=13, tcolor=BLUE)

    # ============ S11 创新性与应用潜力 ============
    s = prs.slides.add_slide(blank)
    add_header(s, "INNOVATION & POTENTIAL", "创新性与应用潜力", 11)
    add_card(s, 0.6, 1.7, 12.1, 2.1, "相对常规做法的差异化",
             ["全异常闭环：不止 happy path，五类异常分支 + 自动验证判定",
              "三级模型降级：无 ML 包也能跑通，强调“可复现”而非“跑一次”",
              "AGH 作为底座：工具注册 + 结构化计划 + 异常码驱动分支，而非把 AGH 当聊天框"],
             tsize=16, bsize=13.5, tcolor=BLUE)
    add_card(s, 0.6, 4.0, 12.1, 2.7, "应用潜力（可扩展方向）",
             ["接入 PJM / ISO 真实逐小时负荷，替换当前 EIA 代理序列",
              "扩展 T+72h 中期预测 + 滚动重训 + 在线学习",
              "异常归因升级：孤立森林 + 变点检测，定位“持续漂移 / 计划性检修”",
              "对接电网调度 / 虚拟电厂场景，形成“预测-告警-建议”数字孪生"],
             tsize=16, bsize=13, tcolor=GREEN)

    # ============ S12 结尾 ============
    s = prs.slides.add_slide(blank)
    set_bg(s, NAVY)
    add_text(s, 0.9, 2.0, 11.5, 1.0, "可执行 · 可验证 · 可复现", size=44, color=WHITE, bold=True)
    add_text(s, 0.9, 3.3, 11.5, 0.6, "Grid Load Agent — AGH 电力负荷预测与异常检测闭环",
             size=20, color=LBLUE)
    add_text(s, 0.9, 4.3, 11.5, 0.5,
             "LLM 层仅调用 Agnes 模型 · 数值层用本地开源库 · 公开数据完成验证",
             size=14, color=WHITE)
    add_text(s, 0.9, 5.6, 11.5, 0.5, "一条命令复现：python run.py --demo", size=15,
             color=LBLUE, bold=True)
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.9), Inches(5.4), Inches(11.5), Inches(0.06))
    bar.fill.solid(); bar.fill.fore_color.rgb = BLUE; bar.line.fill.background()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT))
    print("saved:", OUT, f"({len(prs.slides)} slides)")
    return OUT


if __name__ == "__main__":
    main()
