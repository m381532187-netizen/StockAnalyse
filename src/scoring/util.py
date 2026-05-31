# -*- coding: utf-8 -*-
"""打分层公共工具。"""
from __future__ import annotations


def make_item(name: str, points: float, maxpts: float, detail: str) -> dict:
    return {"item": name, "points": round(max(0.0, points), 2), "max": maxpts, "detail": detail}


def make_dim(name: str, items: list, maxscore: float) -> dict:
    raw = sum(i["points"] for i in items)
    return {"name": name, "score": round(min(raw, maxscore), 2),
            "max": maxscore, "raw": round(raw, 2), "items": items}


def linear_decay(dist: float, tol: float, decay_range: float) -> float:
    """距离 dist：≤tol 返回 1；之后线性衰减，超过 tol+decay_range 返回 0。"""
    if dist <= tol:
        return 1.0
    return max(0.0, 1.0 - (dist - tol) / decay_range)
