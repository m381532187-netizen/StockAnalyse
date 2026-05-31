# -*- coding: utf-8 -*-
"""模式A · 单股即时查询入口。

三种用法：
  1) 直接带代码:   python score.py 600519
  2) 交互模式:     python score.py        （回车后按提示反复输入代码，空行退出）
  3) 双击运行:     score.bat
生成的 md 报告会保存到 reports/ 并自动打开。
"""
from __future__ import annotations
import os
import sys
import warnings
warnings.filterwarnings("ignore")

from src.datasource import get_stock_data
from src.features import compute_features
from src.scoring import score_all
from src.report import build_markdown, save_report


def analyze(code_or_name: str):
    sd = get_stock_data(code_or_name)
    features = compute_features(sd)
    result = score_all(features)
    md = build_markdown(result, features)
    return result, features, md


def _print_summary(result: dict, features: dict):
    m = result["meta"]
    print(f"\n{m['name']}（{m['code']}）  {'大盘' if m['is_large_cap'] else '小盘'}")
    print(f"总分 {result['total']}/100  【{result['level']}】{result['conclusion']} → {result['position']}")
    if features["time"].get("weak_rise"):
        print(f"⚠️ 前期上涨腿仅 {features['time']['rise_pct']*100:.0f}%，疑顶部/下跌结构，时间/空间维度参考性低")
    print("-" * 56)
    for d in result["dims"]:
        print(f"  {d['name']:12} {d['score']:>6}/{d['max']}")


def _open_report(path):
    try:
        if os.name == "nt":
            os.startfile(str(path))          # Windows 用默认程序打开 md
    except Exception:
        pass


def run_once(query: str):
    try:
        result, features, md = analyze(query)
    except Exception as ex:
        print(f"\n❌ 查询失败: {type(ex).__name__}: {ex}")
        return
    _print_summary(result, features)
    m = result["meta"]
    path = save_report(md, m["code"], m["name"], mode="single")
    print(f"\n报告已保存: {path}")
    _open_report(path)


def interactive():
    print("=== 股票见底打分 · 交互模式 ===")
    print("输入股票代码（A股6位 / 港股如 0700.HK / 也可输中文名），空行回车退出。")
    while True:
        try:
            q = input("\n股票代码> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            break
        run_once(q)
    print("已退出。")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) >= 2:
        run_once(sys.argv[1])
    else:
        interactive()


if __name__ == "__main__":
    main()
