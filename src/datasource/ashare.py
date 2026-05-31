# -*- coding: utf-8 -*-
"""A股数据加载器：baostock 主，akshare(sina) 兜底。

- 前复权（adjustflag='2'）
- 日线带换手率 turn(%)；分钟线无换手率
- 流通市值由 volume 与 turn 反算：float_shares = volume*100/turn
"""
from __future__ import annotations
from datetime import datetime, timedelta
import pandas as pd

from .base import StockData, standardize, STD_COLS


def _normalize_code(raw: str) -> str | None:
    """把各种写法规整为 baostock 格式 'sh.600519' / 'sz.000001' / 'bj.830xxx'。
    无法从纯数字判断时返回 None（交给名称解析）。"""
    s = raw.strip().lower().replace(".", "").replace(" ", "")
    for p in ("sh", "sz", "bj"):
        if s.startswith(p) and s[2:].isdigit():
            return f"{p}.{s[2:]}"
        if s.endswith(p) and s[:-2].isdigit():
            return f"{p}.{s[:-2]}"
    if s.isdigit() and len(s) == 6:
        head = s[0]
        if head == "6" or s.startswith("5"):       # 60x/68x 沪股，51x/50x/58x 沪市ETF/基金
            return f"sh.{s}"
        if head in ("0", "3") or s.startswith("1"):  # 00x/30x 深股，15x/16x 深市ETF/LOF
            return f"sz.{s}"
        if head in ("4", "8") or s.startswith("9"):
            return f"bj.{s}"
        return f"sh.{s}"
    return None


def _resolve_name_to_code(name: str):
    """用 baostock 按证券名称反查代码。返回 (code, code_name) 或 (None, None)。"""
    import baostock as bs
    rs = bs.query_stock_basic(code_name=name)
    rows = rs.get_data()
    if rows is not None and len(rows):
        r = rows.iloc[0]
        return r["code"], r["code_name"]
    return None, None


def _query(bs, code: str, fields: str, start: str, end: str, freq: str) -> pd.DataFrame:
    """查询一个周期，自动重试一次。"""
    last_err = None
    for _ in range(2):
        rs = bs.query_history_k_data_plus(
            code, fields, start_date=start, end_date=end,
            frequency=freq, adjustflag="2")  # 2=前复权
        if rs.error_code == "0":
            df = rs.get_data()
            if df is not None and len(df):
                return df
        last_err = rs.error_msg
    if last_err:
        # 返回空帧，让上层决定是否容忍该周期缺失
        return pd.DataFrame()
    return pd.DataFrame()


def _intraday_dt(df: pd.DataFrame) -> pd.Series:
    # baostock time 形如 '20260529133000000'(YYYYMMDDHHMMSSfff)
    return pd.to_datetime(df["time"].str[:14], format="%Y%m%d%H%M%S")


def load(code_or_name: str) -> StockData:
    import baostock as bs

    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    try:
        code = _normalize_code(code_or_name)
        name = None
        if code is None:  # 输入是名称
            code, name = _resolve_name_to_code(code_or_name)
            if code is None:
                raise ValueError(f"无法解析 A股 代码或名称: {code_or_name!r}")
        if name is None:
            basic = bs.query_stock_basic(code=code).get_data()
            name = basic.iloc[0]["code_name"] if len(basic) else code

        today = datetime.now().strftime("%Y-%m-%d")
        d_start = (datetime.now() - timedelta(days=800)).strftime("%Y-%m-%d")   # MA250 + 半年回溯
        w_start = (datetime.now() - timedelta(days=1500)).strftime("%Y-%m-%d")  # 55周均线
        h_start = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")   # 60分钟
        m_start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")    # 15分钟

        day_fields = "date,open,high,low,close,volume,amount,turn,pctChg"
        wk_fields = "date,open,high,low,close,volume,amount,turn"
        min_fields = "date,time,open,high,low,close,volume,amount"

        raw_day = _query(bs, code, day_fields, d_start, today, "d")
        raw_week = _query(bs, code, wk_fields, w_start, today, "w")
        raw_60 = _query(bs, code, min_fields, h_start, today, "60")
        raw_15 = _query(bs, code, min_fields, m_start, today, "15")

        frames = {}
        day_map = {"dt": "date", "open": "open", "high": "high", "low": "low",
                   "close": "close", "volume": "volume", "amount": "amount",
                   "turnover": "turn"}
        frames["day"] = standardize(raw_day, day_map) if len(raw_day) else pd.DataFrame(columns=STD_COLS)
        frames["week"] = standardize(raw_week, day_map) if len(raw_week) else pd.DataFrame(columns=STD_COLS)
        min_map = {"open": "open", "high": "high", "low": "low", "close": "close",
                   "volume": "volume", "amount": "amount"}
        frames["60min"] = (standardize(raw_60, min_map, dt_builder=_intraday_dt)
                           if len(raw_60) else pd.DataFrame(columns=STD_COLS))
        frames["15min"] = (standardize(raw_15, min_map, dt_builder=_intraday_dt)
                           if len(raw_15) else pd.DataFrame(columns=STD_COLS))

        float_mktcap = _calc_float_mktcap(frames["day"])
    finally:
        bs.logout()

    return StockData(code=code, raw_code=code_or_name, market="A",
                     name=name, float_mktcap=float_mktcap, frames=frames)


def _calc_float_mktcap(day: pd.DataFrame):
    """由换手率反算流通市值：float_shares = volume*100/turn(%)，再×收盘价。"""
    if day is None or len(day) == 0:
        return None
    valid = day[(day["turnover"] > 0) & day["volume"].notna() & (day["volume"] > 0)]
    if len(valid) == 0:
        return None
    row = valid.iloc[-1]
    float_shares = row["volume"] * 100.0 / row["turnover"]
    return float(float_shares * row["close"])
