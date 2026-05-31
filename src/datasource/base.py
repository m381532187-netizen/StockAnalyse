# -*- coding: utf-8 -*-
"""统一数据接口：市场识别、标准化 schema、分发到各市场加载器。

对上层暴露唯一入口 `get_stock_data(code_or_name)`，返回标准化的 `StockData`。
所有 K 线帧统一为列：[dt, open, high, low, close, volume, amount, turnover]
- dt        : pandas datetime（日/周为当天 00:00，分钟线含具体时间）
- volume    : 成交量（股）
- amount    : 成交额（元）
- turnover  : 换手率，**统一为百分比**（如 0.61 表示 0.61%）；缺失为 NaN
价格一律**前复权**。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional
import pandas as pd

# 标准列
STD_COLS = ["dt", "open", "high", "low", "close", "volume", "amount", "turnover"]
# K 线周期键
FRAME_KEYS = ["day", "week", "60min", "15min"]

# 大盘/小盘流通市值阈值（元）——见 CLAUDE.md §6
LARGE_CAP_THRESHOLD = 300e8


@dataclass
class StockData:
    code: str                      # 标准化代码，如 'sh.600519' / '0700.HK'
    raw_code: str                  # 用户原始输入
    market: str                    # 'A' | 'HK'
    name: str                      # 证券名称
    float_mktcap: Optional[float]  # 流通市值（元），可能为 None
    frames: Dict[str, pd.DataFrame] = field(default_factory=dict)

    @property
    def is_large_cap(self) -> bool:
        """流通市值 ≥ 阈值为大盘。取不到市值时保守按大盘处理（换手率阈值更严）。"""
        if self.float_mktcap is None:
            return True
        return self.float_mktcap >= LARGE_CAP_THRESHOLD

    @property
    def turnover_threshold_pct(self) -> float:
        """换手率达标阈值（百分比）：大盘 1%，小盘 3%。"""
        return 1.0 if self.is_large_cap else 3.0

    def frame(self, key: str) -> pd.DataFrame:
        return self.frames.get(key, pd.DataFrame(columns=STD_COLS))


def detect_market(code_or_name: str) -> str:
    """识别市场。返回 'A' 或 'HK'。

    规则：
    - 含 '.HK' 或 'hk' 前缀 -> HK
    - 纯 6 位数字 -> A股
    - 4~5 位数字（港股常见 5 位代码如 00700） -> HK
    - 其它（中文名/英文）-> 暂按 A股 尝试（名称解析在加载器里做）
    """
    s = code_or_name.strip().upper()
    if ".HK" in s or s.startswith("HK"):
        return "HK"
    digits = "".join(ch for ch in s if ch.isdigit())
    if s.isdigit():
        if len(s) == 6:
            return "A"
        if len(s) in (4, 5):
            return "HK"
    # 带前缀如 SH600519 / SZ000001
    if s.startswith(("SH", "SZ", "BJ")) and digits:
        return "A"
    if digits and len(digits) == 6:
        return "A"
    # 默认按 A股 处理（名称解析交给加载器）
    return "A"


def standardize(df: pd.DataFrame, colmap: Dict[str, str],
                dt_builder=None) -> pd.DataFrame:
    """把原始 DataFrame 规整为标准 schema。

    colmap: {标准列名: 原始列名}，缺失的标准列填 NaN。
    dt_builder: 可选，传入原始 df 返回 dt 序列（用于分钟线 date+time 拼接）。
    """
    out = pd.DataFrame()
    if dt_builder is not None:
        out["dt"] = dt_builder(df)
    elif "dt" in colmap:
        out["dt"] = pd.to_datetime(df[colmap["dt"]])
    for col in STD_COLS:
        if col == "dt":
            continue
        src = colmap.get(col)
        if src is not None and src in df.columns:
            out[col] = pd.to_numeric(df[src], errors="coerce")
        else:
            out[col] = float("nan")
    out = out.dropna(subset=["close"]).reset_index(drop=True)
    out = out.sort_values("dt").reset_index(drop=True)
    return out[STD_COLS]


ETF_PREFIXES = ("51", "56", "58", "50", "15", "16")  # 沪深 ETF/LOF 代码前缀


def is_etf(code_or_name: str) -> bool:
    s = "".join(ch for ch in code_or_name if ch.isdigit())
    return len(s) == 6 and s[:2] in ETF_PREFIXES


def get_stock_data(code_or_name: str) -> StockData:
    """统一入口：输入代码或名称，返回标准化 StockData。
    路由：港股->yfinance；A股 ETF->akshare sina；A股个股->baostock。"""
    if detect_market(code_or_name) == "HK":
        from . import hk
        return hk.load(code_or_name)
    if is_etf(code_or_name):
        from . import etf
        return etf.load(code_or_name)
    from . import ashare
    return ashare.load(code_or_name)
