# -*- coding: utf-8 -*-
"""维度四 · 技术指标（25）= RSI(12)9 + MACD9 + KDJ4 + 布林3。

RSI/MACD 各三周期（日/60分/15分），每周期 3 分。
"""
from __future__ import annotations
from .util import make_item, make_dim

TF_LABEL = {"day": "日线", "60min": "60分", "15min": "15分"}


def score(techf: dict) -> dict:
    items = []

    # 1) RSI(12) 三周期（9）：每周期 <30 给1.5 + 拐头向上 1.5
    rsi_pts = 0.0; details = []
    for k in ["day", "60min", "15min"]:
        s = techf.get(k)
        if not s:
            details.append(f"{TF_LABEL[k]}缺"); continue
        p = (1.5 if s["rsi_below30"] else 0) + (1.5 if s["rsi_turn_up"] else 0)
        rsi_pts += p
        tag = []
        if s["rsi_below30"]: tag.append("<30")
        if s["rsi_turn_up"]: tag.append("拐头")
        details.append(f"{TF_LABEL[k]}{s['rsi']:.0f}{'('+'+'.join(tag)+')' if tag else ''}")
    items.append(make_item("RSI(12)三周期", rsi_pts, 9, "；".join(details)))

    # 2) MACD 三周期（9）：绿柱缩短1 + 金叉1 + 底背离1
    macd_pts = 0.0; details = []
    for k in ["day", "60min", "15min"]:
        s = techf.get(k)
        if not s:
            details.append(f"{TF_LABEL[k]}缺"); continue
        p = (1 if s["绿柱缩短"] else 0) + (1 if s["金叉"] else 0) + (1 if s["底背离"] else 0)
        macd_pts += p
        tag = [t for t in ("绿柱缩短", "金叉", "底背离") if s[t]]
        details.append(f"{TF_LABEL[k]}{('('+'+'.join(tag)+')') if tag else '无'}")
    items.append(make_item("MACD三周期", macd_pts, 9, "；".join(details)))

    # 3) KDJ（4）
    kdj = techf.get("kdj", {})
    kp = 4.0 if kdj.get("j_below0_turn") else 0.0
    items.append(make_item("KDJ", kp, 4,
                           f"J={kdj.get('j', float('nan')):.1f}，"
                           f"{'J<0后拐头' if kdj.get('j_below0_turn') else '未现J<0拐头'}"))

    # 4) 布林带（3）
    boll = techf.get("boll", {})
    bp = 3.0 if boll.get("break_then_back") else 0.0
    items.append(make_item("布林带", bp, 3,
                           "跌破下轨后站回" if boll.get("break_then_back") else "未现跌破站回"))

    return make_dim("四、技术指标", items, 25)
