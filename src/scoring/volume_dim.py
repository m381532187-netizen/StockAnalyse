# -*- coding: utf-8 -*-
"""维度三 · 量价维度（25）= 缩量6 + 换手率6 + K线形态8 + 量价配合5。"""
from __future__ import annotations
from .util import make_item, make_dim

STRONG = {"放量阳线": 4, "阳包阴": 4, "底部堆量": 4}
WEAK = {"地量十字星": 2, "缩量横盘": 2}


def score(vf: dict) -> dict:
    items = []

    # 1) 缩量比例（6）
    sr = vf["shrink_ratio"]
    if sr != sr:
        sp = 0.0; note = "成交量数据缺失"
    elif sr < 0.5:
        sp = 6.0; note = f"当前量为5日均量的{sr*100:.0f}%（<50%，明显缩量）"
    elif sr < 0.7:
        sp = 3.0; note = f"当前量为5日均量的{sr*100:.0f}%（50~70%）"
    else:
        sp = 0.0; note = f"当前量为5日均量的{sr*100:.0f}%（未缩量）"
    items.append(make_item("缩量比例", sp, 6, note))

    # 2) 换手率达标（6）；港股无数据弱化为缺省半分
    to, th = vf["turnover"], vf["turnover_threshold"]
    if to != to:
        tp = 3.0; note = f"无换手率数据（港股），按缺省{tp}分"
    elif to < th:
        tp = 6.0; note = f"换手率{to:.2f}% < {th:.0f}%（达标）"
    elif to < th * 1.5:
        tp = 2.6; note = f"换手率{to:.2f}%（略高于{th:.0f}%）"
    else:
        tp = 0.0; note = f"换手率{to:.2f}%（明显高于{th:.0f}%）"
    items.append(make_item("换手率达标", tp, 6, note))

    # 3) 底部K线形态（8，累加封顶）
    pats = vf["patterns"]
    hit = [k for k, v in pats.items() if v]
    kp = sum(STRONG.get(k, 0) + WEAK.get(k, 0) for k in hit)
    kp = min(kp, 8)
    items.append(make_item("底部K线形态", kp, 8,
                           f"命中：{('、'.join(hit)) if hit else '无'}"))

    # 4) 量价配合（5）
    vp = vf["vp_match"]
    vpp = (2.5 if vp["上涨放量"] else 0) + (2.5 if vp["下跌缩量"] else 0)
    parts = [k for k in ("上涨放量", "下跌缩量") if vp[k]]
    items.append(make_item("量价配合", vpp, 5,
                           f"{('、'.join(parts)) if parts else '量价配合不佳'}"))

    return make_dim("三、量价维度", items, 25)
