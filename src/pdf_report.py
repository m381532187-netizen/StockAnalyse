# -*- coding: utf-8 -*-
"""PDF 报告生成（中文）：用 reportlab + 内置 STSong-Light CJK 字体，无需外部依赖。

用于模式B：把整批打分结果生成一个 PDF（汇总排名 + 每只明细），作为邮件附件。
"""
from __future__ import annotations
import os
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak)

from .form import form_sections


def _register_cjk_font() -> str:
    """优先嵌入 Windows 本地 CJK 字体（保证任何阅读器都能显示中文）；
    找不到时退回 reportlab 内置 CID 字体 STSong-Light。"""
    candidates = [
        ("SimSun", r"C:\Windows\Fonts\simsun.ttc", 0),
        ("MSYaHei", r"C:\Windows\Fonts\msyh.ttc", 0),
        ("SimHei", r"C:\Windows\Fonts\simhei.ttf", None),
    ]
    for name, path, idx in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(
                    TTFont(name, path) if idx is None else TTFont(name, path, subfontIndex=idx))
                return name
            except Exception:
                continue
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    return "STSong-Light"


FONT = _register_cjk_font()

_ss = getSampleStyleSheet()
TITLE = ParagraphStyle("t", parent=_ss["Title"], fontName=FONT, fontSize=18, leading=22)
H1 = ParagraphStyle("h1", parent=_ss["Heading1"], fontName=FONT, fontSize=14, leading=18,
                    textColor=colors.HexColor("#1a3b5d"))
H2 = ParagraphStyle("h2", parent=_ss["Heading2"], fontName=FONT, fontSize=11, leading=15,
                    textColor=colors.HexColor("#1a3b5d"))
NORMAL = ParagraphStyle("n", parent=_ss["Normal"], fontName=FONT, fontSize=9, leading=13)
SMALL = ParagraphStyle("s", parent=_ss["Normal"], fontName=FONT, fontSize=8, leading=11)
WARN = ParagraphStyle("w", parent=NORMAL, textColor=colors.HexColor("#b00020"))
BIG = ParagraphStyle("b", parent=NORMAL, fontSize=13, leading=17,
                     textColor=colors.HexColor("#0a7d2c"))


def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _P(text, style=NORMAL) -> Paragraph:
    return Paragraph(_esc(text), style)


def _Pb(text, style=NORMAL) -> Paragraph:
    """加粗段落。"""
    return Paragraph(f"<b>{_esc(text)}</b>", style)


def _fmt(x, nd=2):
    try:
        return f"{float(x):.{nd}f}"
    except Exception:
        return "—"


def _fmt_date(d):
    try:
        return d.strftime("%Y-%m-%d")
    except Exception:
        return str(d)


def _table(data, widths, header=True, align_right=None):
    style = [
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")),
                  ("FONTSIZE", (0, 0), (-1, 0), 9)]
    for c in (align_right or []):
        style.append(("ALIGN", (c, 0), (c, -1), "CENTER"))
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    t.setStyle(TableStyle(style))
    return t


# ============ 单只明细 ============
def stock_flowables(result: dict, features: dict) -> list:
    m = result["meta"]
    tf, sf, vf = features["time"], features["space"], features["volume"]
    cap = f"{m['float_mktcap']/1e8:.0f}亿" if m.get("float_mktcap") else "—"
    out = [
        _P(f"{m['name']}（{m['code']}）见底打分报告", H1),
        _P(f"市场：{'A股' if m['market']=='A' else '港股'}　流通市值≈{cap}　"
           f"{'大盘' if m['is_large_cap'] else '小盘'}（换手率阈值{vf['turnover_threshold']:.0f}%）"
           f"　数据截止：{_fmt_date(tf['current_date'])}　当前价：{_fmt(tf['current_price'])}", SMALL),
        Spacer(1, 3 * mm),
        _P(f"总分：{result['total']} / 100　【{result['level']}】"
           f"　{result['conclusion']} → {result['position']}", BIG),
    ]
    if tf.get("weak_rise"):
        out.append(_P(f"⚠️ 前期上涨腿仅 {tf['rise_pct']*100:.0f}%（半年内无明显前期上涨），"
                      f"可能处于顶部/下跌结构，时间/空间维度的斐波那契与回撤评分参考性较低。", WARN))
    out.append(Spacer(1, 2 * mm))

    # 原始数据（按见底特征打分表填充）
    out.append(_P("原始数据（见底特征打分表）", H2))
    for title, rows in form_sections(result, features):
        out.append(_P(title, NORMAL))
        body = []
        for row in rows:
            label, val = row[0], row[1]
            bold = len(row) > 2 and row[2].get("bold")
            body.append([_Pb(label, SMALL) if bold else _P(label, SMALL),
                         _Pb(val, SMALL) if bold else _P(val, SMALL)])
        out.append(_table(body, [180, 335], header=False))
        out.append(Spacer(1, 2 * mm))
    return out


# ============ 汇总排名 ============
def _summary_flowables(items: list, errors: list, when: datetime) -> list:
    rows = [["排名", "名称", "代号", "总分", "评级", "仓位建议", "时间", "空间", "量价", "指标"]]
    ranked = sorted(items, key=lambda x: x["result"]["total"], reverse=True)
    for i, it in enumerate(ranked, 1):
        r = it["result"]; d = [f"{x['score']}" for x in r["dims"]]
        rows.append([str(i), _P(r["meta"]["name"], SMALL), _P(r["meta"]["code"], SMALL),
                     f"{r['total']}", r["level"], _P(r["position"], SMALL), d[0], d[1], d[2], d[3]])
    for code, err in errors:
        rows.append(["-", _P(code, SMALL), _P(code, SMALL), "❌", err, "", "", "", "", ""])
    out = [
        _P("见底打分汇总", TITLE),
        _P(f"生成时间：{when:%Y-%m-%d %H:%M}　共 {len(items)} 只成功"
           f"{('，' + str(len(errors)) + ' 只失败') if errors else ''}", SMALL),
        Spacer(1, 4 * mm),
        _table(rows, [26, 70, 58, 36, 40, 92, 28, 28, 28, 28],
               align_right=[0, 3, 6, 7, 8, 9]),
        Spacer(1, 3 * mm),
        _P("评分越高=见底概率越高。口径见 CLAUDE.md 打分细则 v1.0。仅供研究参考，不构成投资建议。", SMALL),
    ]
    return out


def build_batch_pdf(items: list, errors: list, path: Path, when: datetime) -> Path:
    """items=[{'result':..,'features':..}], errors=[(code,err)]。"""
    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm,
                            title="见底打分汇总")
    story = _summary_flowables(items, errors, when)
    ranked = sorted(items, key=lambda x: x["result"]["total"], reverse=True)
    for it in ranked:
        story.append(PageBreak())
        story += stock_flowables(it["result"], it["features"])
    doc.build(story)
    return path


def build_single_pdf(result: dict, features: dict, path: Path) -> Path:
    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"{result['meta']['name']} 见底打分")
    doc.build(stock_flowables(result, features))
    return path
