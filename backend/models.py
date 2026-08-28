"""Pydantic 数据模型"""
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class StockResponse(BaseModel):
    id: Optional[int] = None
    ticker: str
    name: Optional[str] = ""
    market: Optional[str] = "US"
    threshold: Optional[float] = 15.0
    alert_enabled: bool = False
    current_price: Optional[float] = None
    change_pct: Optional[float] = None
    ah_change_pct: Optional[float] = None        # 盘后涨跌幅（美股专属）
    ah_change_label: Optional[str] = None        # 盘后/夜盘 标签
    sector: Optional[str] = None                # 行业板块
    week52_high: Optional[float] = None
    week52_low: Optional[float] = None
    week52_high_date: Optional[str] = None
    week52_low_date: Optional[str] = None
    drawdown: Optional[float] = None
    drawdown_windows: Optional[Dict[str, Dict[str, Any]]] = None
    distance_low_pct: Optional[float] = None
    pe_ratio: Optional[float] = None
    market_status: Optional[str] = "未知"
    last_updated: Optional[str] = None
    created_at: Optional[str] = None


class AddStockRequest(BaseModel):
    ticker: str
    name: Optional[str] = None
    threshold: Optional[float] = 15.0
    alert_enabled: bool = False


class UpdateStockRequest(BaseModel):
    name: Optional[str] = None
    threshold: Optional[float] = None
    alert_enabled: Optional[bool] = None
    current_price: Optional[float] = None
    change_pct: Optional[float] = None
    sector: Optional[str] = None
    week52_high: Optional[float] = None
    week52_low: Optional[float] = None
    week52_high_date: Optional[str] = None
    week52_low_date: Optional[str] = None
    drawdown: Optional[float] = None
    distance_low_pct: Optional[float] = None
    pe_ratio: Optional[float] = None
    market_status: Optional[str] = None


class StockGroupNameRequest(BaseModel):
    name: str


class StockGroupResponse(BaseModel):
    id: int
    name: str
    stock_ids: list[int] = Field(default_factory=list)
    stock_count: int = 0
    created_at: Optional[str] = None


class StockIdBatchRequest(BaseModel):
    stock_ids: list[int] = Field(min_length=1)
