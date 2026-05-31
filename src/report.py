# -*- coding: utf-8 -*-
"""报告层：把打分结果 + 采集数据渲染成 markdown，并落盘到 reports/。"""
from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path

from .form import form_markdown

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"


def clean_code(code: str) -> str:
    """去掉交易所前缀/点号，得到干净代号：sh.600519->600519，0700.HK->0700HK。"""
    for p in ("sh.", "sz.", "bj."):
        if code.startswith(p):
            return code[3:]
    return code.replace(".", "")


def safe_name(name: str) -> str:
    """去掉 Windows 文件名非法字符与空白（中文保留）。"""
    return re.sub(r'[\\/:*?"<>|\s]+', "", name) or "NA"


def report_dir(mode: str, when: datetime) -> Path:
    """single: reports/single/<YYYY-MM-DD>/
    batch:  reports/batch/<YYYY-MM-DD>/<HHMMSS>/（每次运行独立一层秒级时间戳目录）。"""
    d = REPORTS_DIR / mode / when.strftime("%Y-%m-%d")
    if mode == "batch":
        d = d / when.strftime("%H%M%S")
    d.mkdir(parents=True, exist_ok=True)
    return d


def report_basename(code: str, name: str, when: datetime) -> str:
    """代号_股票名_时间戳（精确到秒）。"""
    return f"{clean_code(code)}_{safe_name(name)}_{when:%Y%m%d_%H%M%S}"


def _fmt_date(d):
    try:
        return d.strftime("%Y-%m-%d")
    except Exception:
        return str(d)


def _fmt(x, nd=2):
    try:
        return f"{float(x):.{nd}f}"
    except Exception:
        return "—"


def build_markdown(result: dict, features: dict) -> str:
    m = result["meta"]
    tf = features["time"]; sf = features["space"]; vf = features["volume"]
    cap = f"{m['float_mktcap']/1e8:.0f}亿" if m.get("float_mktcap") else "—"
    L = []
    L.append(f"# {m['name']}（{m['code']}）见底打分报告")
    L.append("")
    L.append(f"- 生成时间：{datetime.now():%Y-%m-%d %H:%M}")
    L.append(f"- 市场：{'A股' if m['market']=='A' else '港股'} ｜ 流通市值≈{cap} ｜ "
             f"{'大盘' if m['is_large_cap'] else '小盘'}（换手率阈值{vf['turnover_threshold']:.0f}%）")
    L.append(f"- 数据截止：{_fmt_date(tf['current_date'])} ｜ 当前价：{_fmt(tf['current_price'])}")
    L.append("")
    L.append(f"## 总分：{result['total']} / 100　【{result['level']}】")
    L.append(f"> {result['conclusion']} → **{result['position']}**")
    if tf.get("weak_rise"):
        L.append(f">")
        L.append(f"> ⚠️ **前期上涨腿仅 {tf['rise_pct']*100:.0f}%**（半年内无明显前期上涨），"
                 f"可能处于顶部/下跌结构，**时间/空间维度的斐波那契与回撤评分参考性较低**。")
    L.append("")
    # 原始数据（按《个股见底特征打分表》填充）
    L.append("## 原始数据（见底特征打分表）")
    L.append("")
    L.append(form_markdown(result, features))
    L.append("---")
    L.append("> 前期高低点采用半年窗口峰谷检测。RSI 按 RSI(12) 计算。"
             "本报告仅供研究参考，不构成投资建议。")
    return "\n".join(L)


def save_report(md: str, code: str, name: str, mode: str = "single",
                when: datetime | None = None) -> Path:
    """保存 md 报告到 reports/<mode>/<日期>/代号_股票名_时间戳.md。"""
    when = when or datetime.now()
    path = report_dir(mode, when) / f"{report_basename(code, name, when)}.md"
    path.write_text(md, encoding="utf-8")
    return path
