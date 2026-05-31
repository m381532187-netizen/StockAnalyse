# -*- coding: utf-8 -*-
"""特征层：把指标/K线转成打分所需的"测量值"。

打分阈值（<50%、<30 等）放在打分层；本层只做**识别/测量**与形态判定。
形态判定阈值集中在 PARAMS，便于调参（见 CLAUDE.md §6、§9 待办）。
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

from .datasource import StockData
from .indicators import add_indicators

# ---- 可调参数（v1 默认，见 CLAUDE.md §6/§9）----
PARAMS = {
    "peak_lookback": 120,        # 前期高点查找窗口（交易日，≈半年）
    "rise_lookback": 250,        # 从高点往前找上涨起点的最大回看窗口
    "weak_rise_pct": 0.08,       # 上涨腿幅度 <8% 视为"无有效前期上涨"（顶部/下跌结构），打分会标注
    "price_tol": 0.015,          # 价格"贴近"容差 ±1.5%
    "triple_tol": 0.02,          # 三重支撑重合容差 ±2%
    "fib_day_tol": 2,            # 斐波那契天数容差 ±2 天
    "vol_surge": 1.5,            # 放量倍数
    "vol_floor": 0.6,            # 地量/缩量倍数（< avg×该值）
    "doji_body": 0.25,           # 十字星实体占振幅比例上限
    "divergence_lookback": 60,   # 底背离回溯窗口
    "vp_window": 10,             # 量价配合观察窗口
}
FIBS = [5, 8, 13, 21, 34, 55, 89]
RETR_RATIOS = [0.382, 0.500, 0.618, 0.786]


# ============ 工具 ============
def _last(s, i=-1):
    try:
        return float(s.iloc[i])
    except Exception:
        return float("nan")


def _round_level(p: float) -> float:
    """最近整数关口。"""
    for hi, step in [(5, 0.5), (20, 1), (50, 5), (200, 10), (1000, 50)]:
        if p < hi:
            return round(p / step) * step
    return round(p / 100) * 100


# ============ 前期高低点检测 ============
def _select_peak_trough(high: np.ndarray, low: np.ndarray, n: int):
    """前期高点 = 半年窗口内最高高点（直观、稳健，不会被小波动误选）。
    上涨起点 = 制造该高点的那段上涨的最低点：上涨腿从『上一次价格达到该高位之后』算起，
    从而在顶部/下跌结构里也能取到一段干净的上涨腿（避免把更早的更高点并入）。"""
    lb = PARAMS["peak_lookback"]
    start = max(0, n - lb)
    peak_pos = start + int(np.argmax(high[start:]))
    peak_price = high[peak_pos]
    # 往前找最近一次 high ≥ 前期高点 的位置，上涨腿从其之后开始
    seg_start = 0
    for i in range(peak_pos - 1, -1, -1):
        if high[i] >= peak_price:
            seg_start = i + 1
            break
    seg_start = max(seg_start, peak_pos - PARAMS["rise_lookback"])
    if peak_pos > seg_start:
        trough_pos = seg_start + int(np.argmin(low[seg_start:peak_pos + 1]))
    else:
        trough_pos = peak_pos
    return peak_pos, trough_pos


# ============ 维度一：时间 ============
def time_features(day: pd.DataFrame) -> dict:
    n = len(day)
    high = day["high"].to_numpy(); low = day["low"].to_numpy()
    peak_pos, trough_pos = _select_peak_trough(high, low, n)

    adjust_days = (n - 1) - peak_pos      # 调整天数（交易日）
    rise_days = peak_pos - trough_pos     # 上涨天数（交易日）

    peak_price = float(day.iloc[peak_pos]["high"])
    trough_price = float(day.iloc[trough_pos]["low"])
    rise_pct = (peak_price - trough_price) / trough_price if trough_price > 0 else 0.0
    weak_rise = rise_pct < PARAMS["weak_rise_pct"]   # 无有效前期上涨（顶部/下跌结构）

    # 斐波那契命中
    nearest_fib = min(FIBS, key=lambda f: abs(f - adjust_days))
    fib_dist = abs(nearest_fib - adjust_days)

    # 黄金比例时间关系
    ratio = adjust_days / rise_days if rise_days > 0 else float("nan")
    gr_dist = min(abs(ratio - 0.618), abs(ratio - 1.618)) if ratio == ratio else float("nan")

    # 15 天小周期
    cyc_mod = adjust_days % 15 if adjust_days > 0 else 99
    cyc_dist = min(cyc_mod, 15 - cyc_mod)

    return {
        "peak_date": day.iloc[peak_pos]["dt"], "peak_price": peak_price,
        "trough_date": day.iloc[trough_pos]["dt"], "trough_price": trough_price,
        "current_date": day.iloc[-1]["dt"], "current_price": float(day.iloc[-1]["close"]),
        "adjust_days": adjust_days, "rise_days": rise_days,
        "rise_pct": rise_pct, "weak_rise": weak_rise,
        "nearest_fib": nearest_fib, "fib_dist": fib_dist,
        "time_ratio": ratio, "gr_dist": gr_dist,
        "cycle15_dist": cyc_dist,
    }


# ============ 维度二：空间 ============
def space_features(day_ind: pd.DataFrame, week_ind: pd.DataFrame, tf: dict) -> dict:
    high, low = tf["peak_price"], tf["trough_price"]
    rise = high - low
    cur = tf["current_price"]

    # 黄金分割回撤位（从高点向下）
    retr = {r: high - rise * r for r in RETR_RATIOS}
    retr_hit = None; best = 1e9
    for r, price in retr.items():
        d = abs(cur - price) / cur
        if d < best:
            best, retr_hit = d, r
    retr_dist = best
    # 各档"是否达到"：当前价是否已回撤到该档位（含以下）
    retr_reached = {r: cur <= price for r, price in retr.items()}

    # 均线支撑（日线 + 周线），贴近容差内即命中
    last = day_ind.iloc[-1]
    ma_support = {}
    for n in [5, 20, 55, 120, 250]:
        v = last.get(f"ma{n}", float("nan"))
        if v == v and v > 0:
            ma_support[f"日{n}"] = {"value": float(v), "hit": abs(cur - v) / v <= PARAMS["price_tol"]}
    if len(week_ind):
        wlast = week_ind.iloc[-1]
        for n in [5, 20, 55]:
            v = wlast.get(f"ma{n}", float("nan"))
            if v == v and v > 0:
                ma_support[f"周{n}"] = {"value": float(v), "hit": abs(cur - v) / v <= PARAMS["price_tol"]}

    # 三档支撑
    second = _chip_dense_price(day_ind, tf)
    third = _round_level(cur)
    supports = {
        "第一支撑(前低)": {"value": low, "hit": abs(cur - low) / cur <= PARAMS["price_tol"]},
        "第二支撑(筹码密集)": {"value": second, "hit": abs(cur - second) / cur <= PARAMS["price_tol"]},
        "第三支撑(整数关口)": {"value": third, "hit": abs(cur - third) / cur <= PARAMS["price_tol"]},
    }

    # 三重支撑重合：黄金位价、命中的某均线价、命中的某支撑价 三者价位落在 ±triple_tol
    gold_price = retr[retr_hit]
    ma_prices = [m["value"] for m in ma_support.values() if m["hit"]]
    sup_prices = [s["value"] for s in supports.values() if s["hit"]]
    triple = False
    if ma_prices and sup_prices and retr_dist <= PARAMS["price_tol"]:
        for mp in ma_prices:
            for sp in sup_prices:
                if (abs(gold_price - mp) / cur <= PARAMS["triple_tol"]
                        and abs(gold_price - sp) / cur <= PARAMS["triple_tol"]
                        and abs(mp - sp) / cur <= PARAMS["triple_tol"]):
                    triple = True
    return {
        "high": high, "low": low, "rise": rise, "current": cur,
        "retr_levels": retr, "retr_hit": retr_hit, "retr_dist": retr_dist,
        "retr_reached": retr_reached,
        "ma_support": ma_support, "supports": supports, "triple_overlap": triple,
    }


def _chip_dense_price(day_ind: pd.DataFrame, tf: dict) -> float:
    """筹码密集区：按成交量加权的价格直方图峰值。"""
    seg = day_ind.tail(PARAMS["rise_lookback"])
    prices = ((seg["high"] + seg["low"] + seg["close"]) / 3).to_numpy()
    vols = seg["volume"].to_numpy()
    if len(prices) < 5 or np.nansum(vols) == 0:
        return tf["current_price"]
    bins = np.linspace(prices.min(), prices.max(), 31)
    idx = np.clip(np.digitize(prices, bins) - 1, 0, len(bins) - 2)
    acc = np.zeros(len(bins) - 1)
    for i, v in zip(idx, vols):
        acc[i] += (0 if v != v else v)
    b = int(acc.argmax())
    return float((bins[b] + bins[b + 1]) / 2)


# ============ 维度三：量价 ============
def volume_features(day_ind: pd.DataFrame, turnover_threshold: float) -> dict:
    n = len(day_ind)
    vol = day_ind["volume"].to_numpy()
    cur_vol = float(vol[-1])
    ma5_vol = float(np.nanmean(vol[-6:-1])) if n >= 6 else float(np.nanmean(vol[:-1]) if n > 1 else cur_vol)
    shrink_ratio = cur_vol / ma5_vol if ma5_vol and ma5_vol == ma5_vol else float("nan")
    turnover = _last(day_ind["turnover"])  # 百分比；港股可能 NaN

    patterns = _kline_patterns(day_ind, ma5_vol)
    vp = _volume_price_match(day_ind)
    return {
        "current_vol": cur_vol, "ma5_vol": ma5_vol, "shrink_ratio": shrink_ratio,
        "turnover": turnover, "turnover_threshold": turnover_threshold,
        "patterns": patterns, "vp_match": vp,
    }


def _kline_patterns(day: pd.DataFrame, avg_vol: float) -> dict:
    o, h, l, c = (day["open"].to_numpy(), day["high"].to_numpy(),
                  day["low"].to_numpy(), day["close"].to_numpy())
    v = day["volume"].to_numpy()
    last = -1
    rng = max(h[last] - l[last], 1e-9)
    body = abs(c[last] - o[last])
    recent_low = np.nanmin(l[-20:]) if len(l) >= 20 else np.nanmin(l)

    放量阳线 = c[last] > o[last] and v[last] > PARAMS["vol_surge"] * avg_vol
    阳包阴 = (len(c) >= 2 and c[-2] < o[-2] and c[last] > o[last]
              and c[last] >= o[-2] and o[last] <= c[-2])
    地量十字星 = body / rng < PARAMS["doji_body"] and v[last] < PARAMS["vol_floor"] * avg_vol
    缩量横盘 = False
    if len(c) >= 5:
        seg_rng = (np.nanmax(h[-5:]) - np.nanmin(l[-5:])) / np.nanmean(c[-5:])
        缩量横盘 = seg_rng < 0.03 and np.nanmean(v[-3:]) < avg_vol
    底部堆量 = False
    if len(v) >= 3:
        near_bottom = abs(c[last] - recent_low) / c[last] < 0.05
        堆量 = v[-1] >= v[-2] >= v[-3] and v[-1] > avg_vol
        底部堆量 = near_bottom and 堆量
    return {"放量阳线": bool(放量阳线), "阳包阴": bool(阳包阴),
            "地量十字星": bool(地量十字星), "缩量横盘": bool(缩量横盘),
            "底部堆量": bool(底部堆量)}


def _volume_price_match(day: pd.DataFrame) -> dict:
    w = PARAMS["vp_window"]
    seg = day.tail(w + 1).reset_index(drop=True)
    if len(seg) < 4:
        return {"上涨放量": False, "下跌缩量": False}
    chg = seg["close"].diff()
    vol = seg["volume"]
    up_vol = vol[chg > 0].mean()
    down_vol = vol[chg < 0].mean()
    上涨放量 = up_vol == up_vol and down_vol == down_vol and up_vol > down_vol
    下跌缩量 = down_vol == down_vol and down_vol < vol.mean()
    return {"上涨放量": bool(上涨放量), "下跌缩量": bool(下跌缩量)}


# ============ 维度四：技术指标 ============
def tech_features(frames_ind: dict) -> dict:
    out = {}
    for tf_key in ["day", "60min", "15min"]:
        df = frames_ind.get(tf_key)
        out[tf_key] = _tf_signals(df) if df is not None and len(df) else None
    # KDJ / 布林 取日线
    day = frames_ind.get("day")
    out["kdj"] = _kdj_signal(day)
    out["boll"] = _boll_signal(day)
    return out


def _tf_signals(df: pd.DataFrame) -> dict:
    rsi = df["rsi"]
    rsi_val = _last(rsi)
    rsi_up = (len(rsi) >= 3 and rsi.iloc[-1] > rsi.iloc[-2] and rsi.iloc[-2] <= rsi.iloc[-3])
    hist = df["macd_hist"]
    绿柱缩短 = len(hist) >= 2 and hist.iloc[-1] < 0 and hist.iloc[-1] > hist.iloc[-2]
    金叉 = False
    if len(hist) >= 3:
        for i in (-1, -2):
            if hist.iloc[i] > 0 and hist.iloc[i - 1] <= 0:
                金叉 = True
    底背离 = _bottom_divergence(df)
    return {"rsi": rsi_val, "rsi_below30": rsi_val < 30 if rsi_val == rsi_val else False,
            "rsi_turn_up": bool(rsi_up), "绿柱缩短": bool(绿柱缩短),
            "金叉": bool(金叉), "底背离": bool(底背离)}


def _bottom_divergence(df: pd.DataFrame) -> bool:
    lb = min(PARAMS["divergence_lookback"], len(df))
    if lb < 20:
        return False
    seg = df.tail(lb).reset_index(drop=True)
    half = lb // 2
    p1 = seg["low"].iloc[:half].min(); i1 = seg["low"].iloc[:half].idxmin()
    p2 = seg["low"].iloc[half:].min(); i2 = seg["low"].iloc[half:].idxmin()
    d1 = seg["dif"].iloc[i1]; d2 = seg["dif"].iloc[i2]
    return bool(p2 < p1 and d2 > d1)  # 价创新低、DIF 抬高


def _kdj_signal(day: pd.DataFrame) -> dict:
    if day is None or len(day) < 3:
        return {"j_below0_turn": False, "j": float("nan")}
    j = day["kdj_j"]
    recent_min = j.tail(10).min()
    turn = j.iloc[-1] > j.iloc[-2]
    return {"j": _last(j), "j_below0_turn": bool(recent_min < 0 and turn)}


def _boll_signal(day: pd.DataFrame) -> dict:
    if day is None or len(day) < 21:
        return {"break_then_back": False}
    seg = day.tail(10).reset_index(drop=True)
    broke = (seg["close"] < seg["boll_low"]).any()
    back = seg["close"].iloc[-1] > seg["boll_low"].iloc[-1]
    return {"break_then_back": bool(broke and back)}


# ============ 顶层 ============
def compute_features(sd: StockData) -> dict:
    day_ind = add_indicators(sd.frame("day"))
    week_ind = add_indicators(sd.frame("week"))
    frames_ind = {
        "day": day_ind,
        "60min": add_indicators(sd.frame("60min")),
        "15min": add_indicators(sd.frame("15min")),
    }
    tf = time_features(sd.frame("day"))
    sf = space_features(day_ind, week_ind, tf)
    vf = volume_features(day_ind, sd.turnover_threshold_pct)
    techf = tech_features(frames_ind)
    return {"meta": {"code": sd.code, "name": sd.name, "market": sd.market,
                     "is_large_cap": sd.is_large_cap, "float_mktcap": sd.float_mktcap},
            "time": tf, "space": sf, "volume": vf, "tech": techf}
