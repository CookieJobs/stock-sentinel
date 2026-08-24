"""选股 API（M3 充实版）

POST /api/quant/factors/refresh          - 刷新全 A 股因子库
GET  /api/quant/factors/universe/stats   - universe 统计
GET  /api/quant/factors/list             - 列出所有因子
POST /api/quant/factors/screen           - 选股
GET  /api/quant/factors/industries       - 行业列表
"""
from fastapi import APIRouter, HTTPException

from ..factor_service import (
    refresh_universe, screen, list_factors_meta, get_universe_stats,
)

router = APIRouter(prefix="/factors", tags=["factors"])


@router.get("/health")
def health():
    return {"module": "factors", "status": "ok", "version": "M3"}


@router.get("/list")
def list_factors():
    return {"factors": list_factors_meta()}


@router.get("/universe/stats")
def universe_stats():
    return get_universe_stats()


@router.post("/refresh")
def refresh():
    """刷新全 A 股因子库（拉数据 + 算因子 + 入库）"""
    try:
        n = refresh_universe()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刷新失败: {e}")
    stats = get_universe_stats()
    return {
        "inserted": n,
        "stats": stats,
        "message": f"成功入库 {n} 条因子值；当前 universe = {stats['universe_size']} 只，数据源 = {stats['source']}",
    }


@router.post("/screen")
def screen_stocks(payload: dict):
    """多条件选股

    payload:
    {
      "filters": [{"factor": "pe_ttm", "min": 0, "max": 30}, ...],
      "rank_by": "pe_ttm",       # 排名因子
      "top_n": 20,                # 返回前 N
      "industries": ["银行", "地产"],   # 行业白名单（可选）
      "markets": ["CN"]            # 市场白名单（可选）
    }
    """
    return screen(
        filters=payload.get("filters", []),
        rank_by=payload.get("rank_by"),
        top_n=payload.get("top_n", 20),
        industries=payload.get("industries"),
        markets=payload.get("markets"),
    )


@router.get("/industries")
def list_industries():
    """列出常见行业（前端筛选用，取真实数据去重，空时返回静态兜底列表）"""
    from ..db import get_quant_db
    db = get_quant_db()
    try:
        rows = db.execute(
            "SELECT DISTINCT industry FROM daily_metrics WHERE industry IS NOT NULL "
            "AND trade_date = (SELECT MAX(trade_date) FROM daily_metrics) ORDER BY industry"
        ).fetchall()
    finally:
        db.close()
    industries = [r["industry"] for r in rows]
    if not industries:
        industries = [
            "银行", "白酒", "地产", "汽车", "医药", "半导体", "互联网", "保险",
            "电力", "煤炭", "石油", "钢铁", "有色金属", "化工", "建材",
            "家电", "食品饮料", "纺织服饰", "传媒", "通信", "计算机", "电子",
            "机械设备", "国防军工", "农林牧渔", "环保", "物流", "零售",
        ]
    return {"industries": industries}
