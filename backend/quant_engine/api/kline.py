"""K 线 API（M0 占位，M1 充实）"""
from fastapi import APIRouter

router = APIRouter(prefix="/kline", tags=["kline"])


@router.get("/health")
def health():
    return {"module": "kline", "status": "ok", "todo": "M1 实现"}


@router.get("/{ticker}")
def get_kline(ticker: str, market: str = "CN", period: str = "1d",
              start: str = None, end: str = None, adj: str = "qfq"):
    """获取 K 线数据"""
    # M1 实现：调用 data_source.get_kline
    # M0 仅返回占位
    return {
        "ticker": ticker.upper(),
        "market": market,
        "period": period,
        "start": start,
        "end": end,
        "adj": adj,
        "rows": [],
        "message": "M1 实现：调用 quant_engine.data_source.get_kline",
    }
