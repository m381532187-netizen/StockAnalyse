# -*- coding: utf-8 -*-
"""维度二 · 空间维度（25）= 黄金回撤7 + 均线支撑7 + 支撑价位7 + 三重重合4。"""
from __future__ import annotations
from .util import make_item, make_dim, linear_decay

RETR_BASE = {0.382: 4.7, 0.500: 7.0, 0.618: 7.0, 0.786: 3.9}
PRICE_TOL = 0.015
RETR_DECAY = 0.03

# 均线支撑权重（满分7，长期均线权重高）
MA_WEIGHT = {"日250": 2.3, "日120": 1.9, "日55": 1.6, "日20": 0.8, "日5": 0.4,
             "周55": 1.6, "周20": 0.8, "周5": 0.4}


def score(sf: dict) -> dict:
    items = []

    # 1) 黄金分割回撤位（7）
    r = sf["retr_hit"]
    base = RETR_BASE[r]
    pts = base * linear_decay(sf["retr_dist"], PRICE_TOL, RETR_DECAY)
    items.append(make_item("黄金分割回撤位", pts, 7,
                           f"当前价贴近{r:.3f}位（偏离{sf['retr_dist']*100:.2f}%）"))

    # 2) 重要均线支撑（7，命中累加封顶）
    hits = [k for k, v in sf["ma_support"].items() if v["hit"]]
    ma_pts = sum(MA_WEIGHT.get(k, 0.5) for k in hits)
    ma_pts = min(ma_pts, 7)
    items.append(make_item("重要均线支撑", ma_pts, 7,
                           f"获支撑均线：{('、'.join(hits)) if hits else '无'}"))

    # 3) 支撑价位接近（7，三档各≈2.33）
    sup_hits = [k for k, v in sf["supports"].items() if v["hit"]]
    sup_pts = len(sup_hits) * (7 / 3)
    items.append(make_item("支撑价位接近", sup_pts, 7,
                           f"命中支撑：{('、'.join(sup_hits)) if sup_hits else '无'}"))

    # 4) 三重支撑重合（4）
    tp = 4.0 if sf["triple_overlap"] else 0.0
    items.append(make_item("三重支撑重合", tp, 4,
                           "黄金位+均线+支撑位高度重合" if sf["triple_overlap"] else "未形成三重重合"))

    return make_dim("二、空间维度", items, 25)
