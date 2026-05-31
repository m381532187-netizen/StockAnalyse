# -*- coding: utf-8 -*-
"""把打分结果还原成《个股见底特征打分表》的"原始数据填充"形式。

输出结构化 sections，供 md 与 PDF 两种报告复用；填写区域全部填实、勾选框已勾。
注：RSI 按用户修正用 RSI(12)（原表写 RSI(14)）。
"""
from __future__ import annotations

CK, UN = "■", "□"   # 已选 / 未选


def _box(flag) -> str:
    return CK if flag else UN


def _yn(flag) -> str:
    """是/否 勾选；flag 为 None 表示无数据。"""
    if flag is None:
        return f"{UN}是 {UN}否（无数据）"
    return f"{CK}是 {UN}否" if flag else f"{UN}是 {CK}否"


def _f(x, nd=2) -> str:
    try:
        return f"{float(x):.{nd}f}"
    except Exception:
        return "—"


def _md(d) -> str:
    try:
        return f"{d.month}月{d.day}日"
    except Exception:
        return str(d)


def form_sections(result: dict, features: dict) -> list:
    """返回 [(维度标题, [(项目, 填写区域), ...]), ...]。"""
    m = result["meta"]
    tf, sf, vf, te = features["time"], features["space"], features["volume"], features["tech"]
    ds = [d["score"] for d in result["dims"]]
    sec = []

    # ===== 一、时间维度 =====
    fib = " ".join(f"{_box(tf['nearest_fib'] == n and tf['fib_dist'] <= 2)}{n}天"
                   for n in [5, 8, 13, 21, 34, 55, 89])
    gr_hit = (tf["gr_dist"] == tf["gr_dist"]) and tf["gr_dist"] <= 0.05
    sec.append(("一、时间维度（25 分）", [
        ("前期高点日期", _md(tf["peak_date"])),
        ("当前日期", _md(tf["current_date"])),
        ("调整天数", f"{tf['adjust_days']} 天（上涨腿 {tf['rise_days']} 天 / 涨幅 {tf['rise_pct']*100:.0f}%）"),
        ("斐波那契窗口", fib),
        ("调整天数与上涨周期黄金比例(0.618/1.618)",
         f"{_box(gr_hit)}（实际比例 {_f(tf['time_ratio'], 2)}）"),
        ("15 天小周期重合", _box(tf["cycle15_dist"] <= 1)),
        ("本维度得分", f"{ds[0]} / 25"),
    ]))

    # ===== 二、空间维度 =====
    rows = [
        ("前期上涨起点", f"起点：{_f(sf['low'])} 元"),
        ("前期上涨高点", f"高点：{_f(sf['high'])} 元"),
        ("上涨幅度", f"幅度：{_f(sf['rise'])} 元"),
    ]
    for r in (0.382, 0.500, 0.618, 0.786):
        rows.append((f"黄金分割回撤 {r:.3f}",
                     f"{_f(sf['retr_levels'][r])} 元　{_yn(sf['retr_reached'][r])}"))
    for key, label in [("日5", "5 日线"), ("日20", "20 日线"), ("日55", "55 日线"),
                       ("日120", "120 日线"), ("日250", "250 日线"),
                       ("周5", "5 周线"), ("周20", "20 周线"), ("周55", "55 周线")]:
        ma = sf["ma_support"].get(key)
        if ma:
            rows.append((label, f"{_f(ma['value'])} 元　{_yn(ma['hit'])}"))
        else:
            rows.append((label, "—（数据不足）"))
    for key in ["第一支撑(前低)", "第二支撑(筹码密集)", "第三支撑(整数关口)"]:
        s = sf["supports"][key]
        rows.append((key, f"{_f(s['value'])} 元　{_yn(s['hit'])}"))
    # 第四支撑（箱体上、下沿）：暂留空待补，加粗标注
    rows.append(("第四支撑（箱体上、下沿）", "上沿：______ 元　下沿：______ 元　（待补充）", {"bold": True}))
    rows.append(("三重支撑重合", _box(sf["triple_overlap"])))
    rows.append(("本维度得分", f"{ds[1]} / 25"))
    sec.append(("二、空间维度（25 分）", rows))

    # ===== 三、量价维度 =====
    to = vf["turnover"]
    th = vf["turnover_threshold"]
    pats = vf["patterns"]
    kline = " ".join(f"{_box(pats[k])}{k}" for k in
                     ["放量阳线", "阳包阴", "地量十字星", "缩量横盘", "底部堆量"])
    vp = vf["vp_match"]
    sec.append(("三、量价维度（25 分）", [
        ("当前成交量", f"{_f(vf['current_vol']/1e4, 1)} 万股"),
        ("5 日均量", f"{_f(vf['ma5_vol']/1e4, 1)} 万股"),
        ("缩量比例 <50%", _yn(vf["shrink_ratio"] < 0.5 if vf["shrink_ratio"] == vf["shrink_ratio"] else None)),
        (f"换手率 <{th:.0f}%（{'大盘' if th == 1 else '小盘'}）",
         _yn(to < th if to == to else None)),
        ("K 线形态", kline),
        ("加分：上涨放量/下跌缩量", f"{_box(vp['上涨放量'])}上涨放量 {_box(vp['下跌缩量'])}下跌缩量"),
        ("本维度得分", f"{ds[2]} / 25"),
    ]))

    # ===== 四、技术指标 =====
    rows = []
    for k, lab in [("day", "日线"), ("60min", "60 分钟"), ("15min", "15 分钟")]:
        s = te.get(k)
        if s:
            rows.append((f"{lab} RSI(12)",
                         f"数值 {_f(s['rsi'], 1)}　是否<30 {_yn(s['rsi_below30'])}　"
                         f"是否拐头向上 {_yn(s['rsi_turn_up'])}"))
        else:
            rows.append((f"{lab} RSI(12)", "—（无数据）"))
    for k, lab in [("day", "日线"), ("60min", "60 分钟"), ("15min", "15 分钟")]:
        s = te.get(k)
        if s:
            rows.append((f"{lab} MACD",
                         f"{_box(s['绿柱缩短'])}绿柱缩短 {_box(s['金叉'])}金叉 {_box(s['底背离'])}底背离"))
        else:
            rows.append((f"{lab} MACD", "—（无数据）"))
    rows.append(("KDJ", f"J 值<0 后拐头 {_yn(te['kdj'].get('j_below0_turn'))}（J={_f(te['kdj'].get('j'), 1)}）"))
    rows.append(("布林带", f"跌破下轨后站回 {_yn(te['boll'].get('break_then_back'))}"))
    rows.append(("本维度得分", f"{ds[3]} / 25"))
    sec.append(("四、技术指标（25 分）", rows))

    # ===== 总分汇总 =====
    sec.append(("总分汇总", [
        ("各维度得分", f"时间：{ds[0]}　空间：{ds[1]}　量价：{ds[2]}　指标：{ds[3]}"),
        ("总分", f"{result['total']} / 100　【{result['level']}】{result['conclusion']} → {result['position']}"),
    ]))
    return sec


def form_markdown(result: dict, features: dict) -> str:
    """渲染为 markdown（项目 | 填写区域 两列表）。"""
    L = []
    for title, rows in form_sections(result, features):
        L.append(f"### {title}")
        L.append("")
        L.append("| 项目明细 | 填写区域 |")
        L.append("|---|---|")
        for row in rows:
            label, val = row[0], row[1]
            if len(row) > 2 and row[2].get("bold"):
                label, val = f"**{label}**", f"**{val}**"
            L.append(f"| {label} | {val} |")
        L.append("")
    return "\n".join(L)
