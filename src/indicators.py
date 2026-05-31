# -*- coding: utf-8 -*-
"""技术指标层：在标准化 K 线帧上计算指标，口径对齐通达信/常用约定。

指标参数（见 CLAUDE.md §5）：
- 均线 MA: 5/20/55/120/250
- RSI: 周期 12（Wilder 平滑，等价通达信 SMA(...,N,1)）
- MACD: 12/26/9（DIF/DEA/柱）
- KDJ: 9/3/3
- 布林带 BOLL: 20, 2σ
"""
from __future__ import annotations
import numpy as np
import pandas as pd

MA_PERIODS = [5, 20, 55, 120, 250]


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    """返回带指标列的副本。frame 需含标准列（close/high/low...）。"""
    df = frame.copy().reset_index(drop=True)
    if len(df) == 0:
        return df
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    # 均线
    for n in MA_PERIODS:
        df[f"ma{n}"] = close.rolling(n).mean()

    # RSI(12) —— Wilder 平滑
    df["rsi"] = _rsi_wilder(close, 12)

    # MACD 12/26/9
    dif, dea, hist = _macd(close, 12, 26, 9)
    df["dif"], df["dea"], df["macd_hist"] = dif, dea, hist

    # KDJ 9/3/3
    k, d, j = _kdj(high, low, close, 9, 3, 3)
    df["kdj_k"], df["kdj_d"], df["kdj_j"] = k, d, j

    # 布林带 20,2
    mid = close.rolling(20).mean()
    std = close.rolling(20).std(ddof=0)
    df["boll_mid"] = mid
    df["boll_up"] = mid + 2 * std
    df["boll_low"] = mid - 2 * std
    return df


def _rsi_wilder(close: pd.Series, n: int = 12) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0)
    down = (-delta).clip(lower=0)
    # Wilder 平滑 = EMA(alpha=1/n)
    roll_up = up.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    roll_down = down.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = roll_up / roll_down.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    rsi = rsi.where(roll_down != 0, 100.0)  # 全涨无跌 -> 100
    return rsi


def _macd(close: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    hist = dif - dea  # 通达信柱为 2*(DIF-DEA)，符号/趋势一致，这里取 DIF-DEA
    return dif, dea, hist


def _kdj(high, low, close, n=9, k_period=3, d_period=3):
    low_min = low.rolling(n, min_periods=1).min()
    high_max = high.rolling(n, min_periods=1).max()
    rng = (high_max - low_min).replace(0, np.nan)
    rsv = (close - low_min) / rng * 100
    rsv = rsv.fillna(50.0)
    # K,D 用 Wilder 式递推（SMA(X,M,1)），初值 50
    k = np.empty(len(close)); d = np.empty(len(close))
    prev_k = prev_d = 50.0
    rsv_v = rsv.to_numpy()
    for i in range(len(close)):
        prev_k = (k_period - 1) / k_period * prev_k + 1 / k_period * rsv_v[i]
        prev_d = (d_period - 1) / d_period * prev_d + 1 / d_period * prev_k
        k[i], d[i] = prev_k, prev_d
    j = 3 * k - 2 * d
    return pd.Series(k, index=close.index), pd.Series(d, index=close.index), pd.Series(j, index=close.index)
