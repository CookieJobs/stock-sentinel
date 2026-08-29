"""StockSentinel 后端 — FastAPI 入口"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# 绕过系统代理直连数据源（系统代理可能不稳定或限速）
for _key in ("NO_PROXY", "no_proxy"):
    _existing = os.environ.get(_key, "")
    _suffix = ",push2.eastmoney.com,push2his.eastmoney.com,finnhub.io"
    os.environ[_key] = (_existing + _suffix) if _existing else "push2.eastmoney.com,push2his.eastmoney.com,finnhub.io"

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from database import init_db
from models import (
    StockResponse,
    AddStockRequest,
    UpdateStockRequest,
    StockGroupNameRequest,
    StockGroupResponse,
    StockIdBatchRequest,
)
from monitor import StockMonitor
from stock_groups import StockGroupService
from alerter import StockAlerter
from briefing import BriefingScheduler, list_briefings, get_latest_briefing, get_briefing
from quant_engine.db import init_quant_db
from quant_engine.api import api_router

monitor = StockMonitor()
stock_groups = StockGroupService()
alerter = StockAlerter()
briefing_scheduler = BriefingScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_quant_db()  # 量化引擎表
    monitor.start_auto_refresh()
    alerter.start()
    briefing_scheduler.start()
    yield
    alerter.stop()
    briefing_scheduler.stop()
    monitor.stop_auto_refresh()


app = FastAPI(title="StockSentinel", version="0.3.0-quant-mvp", lifespan=lifespan)

# 量化引擎 API 路由（/api/quant/*）
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "StockSentinel"}


# ── Stock API ───────────────────────────────────────────────

@app.get("/api/stocks/", response_model=list[StockResponse])
def get_all_stocks():
    """获取所有监控股票"""
    return monitor.get_all_stocks()


@app.get("/api/stocks/{ticker}", response_model=StockResponse)
def get_stock(ticker: str):
    """获取单只股票详情"""
    stock = monitor.get_stock_by_ticker(ticker.upper())
    if not stock:
        raise HTTPException(status_code=404, detail="股票未找到")
    return stock


@app.post("/api/stocks/", response_model=StockResponse, status_code=201)
def add_stock(req: AddStockRequest):
    """添加股票到监控列表"""
    try:
        stock = monitor.add_stock(
            req.ticker,
            req.threshold,
            req.alert_enabled,
            name=req.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not stock:
        raise HTTPException(status_code=409, detail="股票已存在或获取数据失败")
    return stock


@app.put("/api/stocks/{ticker}", response_model=StockResponse)
def update_stock(ticker: str, req: UpdateStockRequest):
    """更新股票设置"""
    try:
        stock = monitor.update_stock(ticker, **req.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not stock:
        raise HTTPException(status_code=404, detail="股票未找到")
    return stock


@app.delete("/api/stocks/{ticker}")
def delete_stock(ticker: str):
    """删除股票"""
    ok = monitor.delete_stock(ticker)
    if not ok:
        raise HTTPException(status_code=404, detail="股票未找到")
    return {"detail": "已删除"}


@app.post("/api/stocks/bulk-delete")
def bulk_delete_stocks(req: StockIdBatchRequest):
    """从整个监控列表删除选中股票，并清理其全部分组归属。"""
    try:
        deleted_ids = monitor.delete_stocks_by_ids(req.stock_ids)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"deleted_stock_ids": deleted_ids, "deleted_count": len(deleted_ids)}


# ── Stock Group API ─────────────────────────────────────────

@app.get("/api/stock-groups/", response_model=list[StockGroupResponse])
def get_stock_groups():
    """获取全部自选分组及其成员数量。"""
    return stock_groups.list_groups()


@app.post("/api/stock-groups/", response_model=StockGroupResponse, status_code=201)
def create_stock_group(req: StockGroupNameRequest):
    """创建一个自定义股票分组。"""
    try:
        return stock_groups.create_group(req.name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.put("/api/stock-groups/{group_id}", response_model=StockGroupResponse)
def rename_stock_group(group_id: int, req: StockGroupNameRequest):
    """重命名分组。"""
    try:
        return stock_groups.rename_group(group_id, req.name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/stock-groups/{group_id}/stocks", response_model=StockGroupResponse)
def add_stocks_to_group(group_id: int, req: StockIdBatchRequest):
    """将多只股票加入分组，已有归属不重复创建。"""
    try:
        return stock_groups.add_stocks(group_id, req.stock_ids)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.delete("/api/stock-groups/{group_id}/stocks", response_model=StockGroupResponse)
def remove_stocks_from_group(group_id: int, req: StockIdBatchRequest):
    """只将股票移出当前分组。"""
    try:
        return stock_groups.remove_stocks(group_id, req.stock_ids)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.delete("/api/stock-groups/{group_id}")
def delete_stock_group(group_id: int):
    """删除分组，不删除其中的股票。"""
    if not stock_groups.delete_group(group_id):
        raise HTTPException(status_code=404, detail="分组未找到")
    return {"detail": "分组已删除"}


@app.post("/api/stocks/refresh")
def refresh_all():
    """启动后台刷新所有股票数据，返回 task_id 供轮询进度"""
    return monitor.start_refresh_all()


@app.get("/api/stocks/refresh/progress")
def refresh_progress(task_id: str):
    """查询刷新进度"""
    progress = monitor.get_refresh_progress(task_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="任务未找到或已过期")
    return progress


@app.get("/api/stocks/{ticker}/refresh")
def refresh_one(ticker: str):
    """刷新单只股票，返回成功/失败状态"""
    result = monitor.refresh_one_with_status(ticker)
    if result["success"]:
        return result
    raise HTTPException(status_code=502, detail=result["error"])


@app.get("/api/auto_refresh/status")
def auto_refresh_status():
    """查询自动刷新状态"""
    return {
        "last_refresh": monitor.get_last_auto_refresh(),
        "enabled": True,
    }


# ── Alert API ───────────────────────────────────────────────

@app.get("/api/alerts/")
def get_alerts():
    """获取所有未读告警"""
    return alerter.unread.get_all()


@app.get("/api/alerts/count")
def get_alert_count():
    """获取未读告警数量"""
    return {"count": alerter.unread.count()}


@app.post("/api/alerts/clear")
def clear_alerts():
    """清除所有未读告警"""
    alerter.unread.clear_all()
    return {"detail": "已清除"}


@app.post("/api/alerts/check")
def trigger_alert_check():
    """手动触发一次告警检查"""
    alerter.trigger_check()
    return {"detail": "触发成功"}


@app.get("/api/alerts/history")
def get_alert_history(limit: int = 50):
    """获取历史告警记录"""
    return alerter.unread.get_history(limit)


@app.delete("/api/alerts/history/{alert_id}")
def delete_alert_history(alert_id: int):
    """删除单条历史告警"""
    ok = alerter.unread.delete_history(alert_id)
    if not ok:
        raise HTTPException(status_code=404, detail="记录未找到")
    return {"detail": "已删除"}


@app.delete("/api/alerts/history")
def clear_alert_history():
    """清除所有历史告警"""
    alerter.unread.clear_history()
    return {"detail": "已清除所有历史"}


# ── Briefing API ────────────────────────────────────────────

@app.get("/api/briefings/")
def get_briefings():
    """获取简报历史列表"""
    return list_briefings()


@app.get("/api/briefings/latest")
def get_briefing_latest():
    """获取最新简报全文"""
    briefing = get_latest_briefing()
    if not briefing:
        raise HTTPException(status_code=404, detail="暂无简报")
    return briefing


@app.get("/api/briefings/{briefing_id}")
def get_briefing_by_id(briefing_id: int):
    """按 id 获取单条简报"""
    briefing = get_briefing(briefing_id)
    if not briefing:
        raise HTTPException(status_code=404, detail="简报未找到")
    return briefing


@app.post("/api/briefings/generate")
def generate_briefing():
    """手动立即生成当日简报"""
    result = briefing_scheduler.generator.generate()
    if not result.get("briefing"):
        raise HTTPException(status_code=500, detail="简报生成失败")
    return result


# ── Price History API ────────────────────────────────────────

@app.get("/api/history/{ticker}")
def get_price_history(ticker: str, days: int = 30, window: str = "1y"):
    """查询单只股票的历史行情序列（回撤趋势图数据源）"""
    try:
        return monitor.get_price_history(ticker, days, window)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# ── 静态文件托管（必须放在所有 /api 路由之后，避免遮蔽 API）──

_DEV_MODE = os.environ.get("DEV_MODE", "").lower() == "true"
static_dir = Path(__file__).parent / "static"

if _DEV_MODE:
    from starlette.responses import RedirectResponse

    @app.get("/{full_path:path}")
    async def redirect_to_dev(full_path: str):
        """Dev mode: redirect non-API visits to Vite dev server"""
        return RedirectResponse(url="http://localhost:5173")

    # Also mount assets from build if available
    if (static_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

elif static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve frontend SPA — fallback to index.html"""
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"detail": "Frontend not built"}


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
