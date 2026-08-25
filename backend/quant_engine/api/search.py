"""股票搜索 API — 按代码/名称（中文/拼音）检索

GET /api/quant/search?q=茅台&limit=10&market=CN
    → {"query": "茅台", "results": [{"ticker", "name", "market", "source"}, ...]}
"""
from fastapi import APIRouter, Query

from ..search_service import search_stocks

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def search(
    q: str = Query(..., min_length=1, max_length=64, description="代码 / 中文名 / 拼音关键词"),
    limit: int = Query(10, ge=1, le=20),
    market: str = Query(None, pattern="^(CN|HK|US)$", description="可选，限定市场"),
):
    """搜索股票（东财 suggest 优先，本地库降级）"""
    return {
        "query": q,
        "results": search_stocks(q, limit=limit, market=market),
    }
