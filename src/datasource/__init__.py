# -*- coding: utf-8 -*-
"""数据源层：统一入口 get_stock_data。"""
from .base import get_stock_data, StockData, detect_market, STD_COLS, FRAME_KEYS

__all__ = ["get_stock_data", "StockData", "detect_market", "STD_COLS", "FRAME_KEYS"]
