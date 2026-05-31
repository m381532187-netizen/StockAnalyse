# -*- coding: utf-8 -*-
"""维度一 · 时间维度（25）= 斐波那契10 + 黄金比例8 + 15天小周期7。"""
from __future__ import annotations
from .util import make_item, make_dim, linear_decay

# 斐波那契命中基础分（满分10，保持 docx 内部比例）
FIB_BASE = {89: 10.0, 55: 10.0, 34: 9.3, 21: 8.0, 13: 6.7, 8: 5.3, 5: 4.0}
FIB_DAY_TOL = 2
FIB_DECAY = 12  # 超出容差 12 天衰减到 0


def score(tf: dict) -> dict:
    items = []

    weak = tf.get("weak_rise")
    warn = f"｜⚠️前期上涨腿仅{tf['rise_pct']*100:.0f}%，疑顶部/下跌结构，时间维度参考性低" if weak else ""

    # 1) 斐波那契时间窗（10）
    fib, dist = tf["nearest_fib"], tf["fib_dist"]
    base = FIB_BASE[fib]
    pts = base * linear_decay(dist, FIB_DAY_TOL, FIB_DECAY)
    items.append(make_item(
        "斐波那契时间窗", pts, 10,
        f"调整{tf['adjust_days']}天，最近Fib={fib}（差{dist}天）{warn}"))

    # 2) 黄金比例时间关系（8）
    gr = tf["gr_dist"]
    if gr != gr:  # NaN
        grp = 0.0; note = "上涨天数为0，无法计算比例"
    elif gr <= 0.05:
        grp = 8.0; note = f"比例={tf['time_ratio']:.3f}，命中黄金比例"
    elif gr <= 0.10:
        grp = 4.6; note = f"比例={tf['time_ratio']:.3f}，接近黄金比例"
    else:
        grp = 0.0; note = f"比例={tf['time_ratio']:.3f}，偏离黄金比例"
    items.append(make_item("黄金比例时间关系", grp, 8, note))

    # 3) 15天小周期重合（7）
    c = tf["cycle15_dist"]
    cp = 7.0 if c <= 1 else 0.0
    items.append(make_item("15天小周期重合", cp, 7,
                           f"调整天数距15整数倍差{c}天"))

    return make_dim("一、时间维度", items, 25)
