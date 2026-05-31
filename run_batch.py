# -*- coding: utf-8 -*-
"""模式B · 批量打分 + 定时任务入口。

读取 watchlist.txt，对每只打分：
  - 每只 md 存到 reports/batch/<日期>/代号_股票名_时间戳.md
  - 汇总 md + 汇总 PDF 存到同目录
  - 若 config.yaml 配好邮箱，则把【PDF 汇总报告】作为附件发邮件

用法:
    python run_batch.py                  # 用 watchlist.txt
    python run_batch.py my_list.txt      # 指定列表文件
"""
from __future__ import annotations
import sys
import warnings
from datetime import datetime
from pathlib import Path
warnings.filterwarnings("ignore")

from score import analyze
from src.report import save_report, report_dir
from src.pdf_report import build_batch_pdf
from src.notifier import load_config, send_email, email_ready

ROOT = Path(__file__).resolve().parent


def read_watchlist(path: Path) -> list[str]:
    codes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            codes.append(line)
    return codes


def build_summary(rows: list[dict]) -> str:
    rows = sorted(rows, key=lambda r: r.get("total", -1), reverse=True)
    L = [f"# 见底打分汇总　{datetime.now():%Y-%m-%d %H:%M}", "",
         "| 排名 | 名称 | 代码 | 总分 | 评级 | 仓位建议 | 时间 | 空间 | 量价 | 指标 |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    rank = 0
    for r in rows:
        if "error" in r:
            L.append(f"| - | {r['code']} | {r['code']} | ❌ {r['error']} | | | | | | |")
            continue
        rank += 1
        d = r["dims"]
        L.append(f"| {rank} | {r['name']} | {r['code']} | **{r['total']}** | {r['level']} | "
                 f"{r['position']} | {d[0]} | {d[1]} | {d[2]} | {d[3]} |")
    L.append("")
    L.append("> 评分越高=见底概率越高。口径见 CLAUDE.md。仅供研究参考，不构成投资建议。")
    return "\n".join(L)


def run(watchlist_path: Path):
    when = datetime.now()
    codes = read_watchlist(watchlist_path)
    print(f"批量打分 {len(codes)} 只 -> reports/batch/{when:%Y-%m-%d}/")
    items, errors, rows = [], [], []
    for code in codes:
        try:
            result, features, md = analyze(code)
            m = result["meta"]
            save_report(md, m["code"], m["name"], mode="batch", when=when)
            items.append({"result": result, "features": features})
            rows.append({"code": m["code"], "name": m["name"], "total": result["total"],
                         "level": result["level"], "position": result["position"],
                         "dims": [d["score"] for d in result["dims"]]})
            print(f"  ✓ {m['name']}({m['code']}) {result['total']}/100 [{result['level']}]")
        except Exception as ex:
            errors.append((code, type(ex).__name__))
            rows.append({"code": code, "error": f"{type(ex).__name__}"})
            print(f"  ✗ {code} 失败: {type(ex).__name__}: {ex}")

    sdir = report_dir("batch", when)
    ts = when.strftime("%Y%m%d_%H%M%S")
    summary = build_summary(rows)
    (sdir / f"汇总_{ts}.md").write_text(summary, encoding="utf-8")
    pdf_path = sdir / f"见底打分汇总_{ts}.pdf"
    try:
        build_batch_pdf(items, errors, pdf_path, when)
        print(f"\n汇总 PDF: {pdf_path}")
    except Exception as ex:
        pdf_path = None
        print(f"\nPDF 生成失败: {type(ex).__name__}: {ex}")
    print(f"目录: {sdir}")

    cfg = load_config()
    if email_ready(cfg) and pdf_path:
        ok, info = send_email(
            subject=f"[见底打分] {when:%Y-%m-%d} 汇总（成功{len(items)}/共{len(codes)}只）",
            body=summary, attachments=[pdf_path], cfg=cfg)
        print(("邮件: " + info) if ok else ("邮件未发: " + info))
    else:
        print("邮件: 未配置，仅本地输出（config.yaml 填好 app_password 且 enabled:true 即可发 PDF）")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) > 1:
        wl = Path(sys.argv[1])
    else:
        # 优先用本地私有列表(不进仓库)，否则用示例 watchlist.txt
        local = ROOT / "watchlist.local.txt"
        wl = local if local.exists() else (ROOT / "watchlist.txt")
    if not wl.exists():
        print(f"找不到列表文件: {wl}")
        sys.exit(1)
    run(wl)


if __name__ == "__main__":
    main()
