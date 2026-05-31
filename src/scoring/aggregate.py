# -*- coding: utf-8 -*-
"""总分汇总 + 仓位建议（口径见 docx / CLAUDE.md §2）。"""
from __future__ import annotations

LEVELS = [
    (80, "极佳", "见底概率极高", "重仓 50–80%"),
    (70, "良好", "调整充分", "分批买入 30–50%"),
    (60, "及格", "调整接近尾声", "轻仓试探 10–20%"),
    (50, "偏弱", "继续观望", "等待更多信号"),
    (0,  "差",  "调整未充分", "不动"),
]


def aggregate(dims: list) -> dict:
    total = round(sum(d["score"] for d in dims), 2)
    for thr, level, conclusion, position in LEVELS:
        if total >= thr:
            return {"total": total, "level": level, "conclusion": conclusion,
                    "position": position, "dims": dims}
    return {"total": total, "level": "差", "conclusion": "调整未充分",
            "position": "不动", "dims": dims}
