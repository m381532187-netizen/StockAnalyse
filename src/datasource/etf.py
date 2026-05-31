# -*- coding: utf-8 -*-
"""ETF / LOF 数据加载器：走 akshare sina（baostock 对 ETF 只有 2026-01 起的少量数据）。

- 日线：ak.fund_etf_hist_sina（历史完整，老 ETF 可达 5 年+）
- 15/60 分钟：ak.stock_zh_a_minute（sina，约 1970 根）
- 周线：日线重采样
- 无换手率（sina ETF 不提供）-> turnover NaN，打分层弱化
- 名称：用 baostock query_stock_basic 取（baostock 有 ETF 名称）
"""
from __future__ import annotations
import pandas as pd

from .base import StockData, standardize, STD_COLS


def _digits(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())


def _exchange(code: str) -> str:
    return "sh" if code[0] == "5" else "sz"   # 5xx 沪市ETF，1xx 深市ETF


def _sina_symbol(code: str) -> str:
    return f"{_exchange(code)}{code}"


def _etf_name(code: str) -> str:
    try:
        import baostock as bs
        bs.login()
        b = bs.query_stock_basic(code=f"{_exchange(code)}.{code}").get_data()
        bs.logout()
        if len(b):
            return b.iloc[0]["code_name"]
    except Exception:
        pass
    return code


def _sina_minute(ak, sym: str, period: str) -> pd.DataFrame:
    try:
        df = ak.stock_zh_a_minute(symbol=sym, period=period, adjust="qfq")
        if df is None or len(df) == 0:
            return pd.DataFrame(columns=STD_COLS)
        cmap = {"open": "open", "high": "high", "low": "low", "close": "close",
                "volume": "volume", "amount": "amount"}
        return standardize(df, cmap, dt_builder=lambda d: pd.to_datetime(d["day"]))
    except Exception:
        return pd.DataFrame(columns=STD_COLS)


def _resample_weekly(day: pd.DataFrame) -> pd.DataFrame:
    if len(day) == 0:
        return day
    g = (day.set_index("dt")
            .resample("W-FRI")
            .agg({"open": "first", "high": "max", "low": "min",
                  "close": "last", "volume": "sum", "amount": "sum"})
            .dropna(subset=["close"]).reset_index())
    g["turnover"] = float("nan")
    return g[STD_COLS]


def load(code_or_name: str) -> StockData:
    import akshare as ak

    code = _digits(code_or_name)
    if len(code) != 6:
        raise ValueError(f"无法解析 ETF 代码: {code_or_name!r}")
    sym = _sina_symbol(code)

    raw = ak.fund_etf_hist_sina(symbol=sym)  # date,open,high,low,close,volume,amount
    day_map = {"dt": "date", "open": "open", "high": "high", "low": "low",
               "close": "close", "volume": "volume", "amount": "amount"}
    day = standardize(raw, day_map) if raw is not None and len(raw) else pd.DataFrame(columns=STD_COLS)

    frames = {
        "day": day,
        "week": _resample_weekly(day),
        "60min": _sina_minute(ak, sym, "60"),
        "15min": _sina_minute(ak, sym, "15"),
    }
    return StockData(code=f"{_exchange(code)}.{code}", raw_code=code_or_name,
                     market="A", name=_etf_name(code), float_mktcap=None, frames=frames)
