#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pydantic 数据模型"""

from pydantic import BaseModel


class StockChange(BaseModel):
    """库存变动请求"""
    delta: float
    note: str = ""
    is_purchase: bool = False
    price: float = 0
