"""StockSentinel 后端 — FastAPI 入口"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from contextlib import asynccontextmanager

from database import init_db
from models import StockResponse, AddStockRequest, UpdateStockRequest
from monitor import StockMonitor
from alerter import StockAlerter

monitor = StockMonitor()
alerter = StockAlerter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    monitor.start_auto_refresh()
    alerter.start()
    yield
    alerter.stop()
    monitor.stop_auto_refresh()


app = FastAPI(title="StockSentinel", version="0.2.0", lifespan=lifespan)

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
    stock = monitor.add_stock(req.ticker, req.threshold)
    if not stock:
        raise HTTPException(status_code=409, detail="股票已存在或获取数据失败")
    return stock


@app.put("/api/stocks/{ticker}", response_model=StockResponse)
def update_stock(ticker: str, req: UpdateStockRequest):
    """更新股票设置"""
    stock = monitor.update_stock(ticker, **req.model_dump(exclude_none=True))
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


@app.get("/api/stocks/{ticker}/refresh", response_model=StockResponse)
def refresh_one(ticker: str):
    """刷新单只股票"""
    stock = monitor.refresh_one(ticker)
    if not stock:
        raise HTTPException(status_code=404, detail="股票未找到")
    return stock


@app.get("/api/auto_refresh/status")
def auto_refresh_status():
    """查询自动刷新状态"""
    return {
        "last_refresh": monitor.get_last_auto_refresh(),
        "enabled": True,
    }


# Serve frontend static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve frontend SPA — fallback to index.html"""
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"detail": "Frontend not built"}


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
