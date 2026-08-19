"""事件日历 API — 分红送转 / 限售解禁"""
from fastapi import APIRouter

from .. import events_service

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
def get_events(start: str, end: str, event_type: str | None = None, limit: int = 300):
    """查询事件日历：GET /api/quant/events?start=2026-08-20&end=2026-09-20[&event_type=dividend]"""
    return {
        "start": start,
        "end": end,
        "events": events_service.list_events(start, end, event_type, limit),
    }


@router.post("/refresh")
def refresh_events(start: str, end: str):
    """拉取区间内事件并入库：POST /api/quant/events/refresh?start=...&end=..."""
    result = events_service.refresh_events(start, end)
    if result.get("error"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=result["error"])
    return result
