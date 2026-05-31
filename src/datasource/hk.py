# -*- coding: utf-8 -*-
"""港股数据加载器：yfinance 主。

- yfinance history 默认 auto_adjust（按拆分/分红调整，相当于复权）
- 无换手率字段 -> turnover 全为 NaN（打分层对港股弱化该因子，见 CLAUDE.md §3 维度三）
- 无成交额字段 -> amount 为 NaN
- 流通市值用 fast_info.market_cap 近似（HKD，总市值口径）
"""
from __future__ import annotations
import pandas as pd

from .base import StockData, STD_COLS


def _normalize_code(raw: str) -> str:
    """规整为 yfinance 港股代码 '0700.HK'。"""
    s = raw.strip().upper().replace("HK", "").replace(".", "")
    digits = "".join(ch for ch in s if ch.isdigit())
    if not digits:
        raise ValueError(f"无法解析港股代码: {raw!r}")
    n = int(digits)
    return f"{n:04d}.HK" if n < 10000 else f"{n}.HK"


def _to_std(df: pd.DataFrame) -> pd.DataFrame:
    """把 yfinance history df 规整为标准 schema。"""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=STD_COLS)
    idx = df.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("Asia/Hong_Kong").tz_localize(None)
    out = pd.DataFrame({
        "dt": pd.to_datetime(idx),
        "open": pd.to_numeric(df["Open"], errors="coerce").values,
        "high": pd.to_numeric(df["High"], errors="coerce").values,
        "low": pd.to_numeric(df["Low"], errors="coerce").values,
        "close": pd.to_numeric(df["Close"], errors="coerce").values,
        "volume": pd.to_numeric(df["Volume"], errors="coerce").values,
        "amount": float("nan"),
        "turnover": float("nan"),
    })
    out = out.dropna(subset=["close"]).sort_values("dt").reset_index(drop=True)
    return out[STD_COLS]


def load(code_or_name: str) -> StockData:
    import yfinance as yf

    symbol = _normalize_code(code_or_name)
    t = yf.Ticker(symbol)

    frames = {
        "day": _to_std(t.history(period="3y", interval="1d")),
        "week": _to_std(t.history(period="5y", interval="1wk")),
        "60min": _to_std(t.history(period="2y", interval="60m")),
        "15min": _to_std(t.history(period="60d", interval="15m")),
    }

    # 名称与流通市值（尽力而为）
    name = symbol
    float_mktcap = None
    try:
        fi = t.fast_info
        mc = getattr(fi, "market_cap", None)
        if mc:
            float_mktcap = float(mc)
    except Exception:
        pass
    try:
        info = t.get_info()
        name = info.get("shortName") or info.get("longName") or symbol
        if float_mktcap is None and info.get("marketCap"):
            float_mktcap = float(info["marketCap"])
    except Exception:
        pass

    return StockData(code=symbol, raw_code=code_or_name, market="HK",
                     name=name, float_mktcap=float_mktcap, frames=frames)
