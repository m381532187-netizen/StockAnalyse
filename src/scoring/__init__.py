# -*- coding: utf-8 -*-
"""打分层：features -> 四维度得分 -> 总分 + 仓位建议。"""
from __future__ import annotations
from . import time_dim, space_dim, volume_dim, tech_dim
from .aggregate import aggregate


def score_all(features: dict) -> dict:
    dims = [
        time_dim.score(features["time"]),
        space_dim.score(features["space"]),
        volume_dim.score(features["volume"]),
        tech_dim.score(features["tech"]),
    ]
    result = aggregate(dims)
    result["meta"] = features["meta"]
    return result


__all__ = ["score_all"]
