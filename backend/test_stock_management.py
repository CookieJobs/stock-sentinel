"""股票监控新增接口测试 —— 使用临时数据库且屏蔽外部行情。

运行：python -m pytest backend/test_stock_management.py -q
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))

import database
from data_fetcher import DataFetcher
from main import app


@pytest.fixture(autouse=True)
def isolated_stock_db(tmp_path, monkeypatch):
    """每个用例都走独立 SQLite 库，行情请求确定性返回无数据。"""
    original_db_path = database.DB_PATH
    database.DB_PATH = tmp_path / "sentinel_test.db"
    database.init_db()
    monkeypatch.setattr(
        DataFetcher,
        "get_stock_info",
        staticmethod(lambda ticker, api_key="": None),
    )
    try:
        yield
    finally:
        database.DB_PATH = original_db_path


@pytest.mark.parametrize(
    ("submitted_ticker", "expected_ticker", "expected_market", "display_name"),
    [
        ("600519.SS", "600519", "CN", "贵州茅台"),
        ("700.HK", "00700", "HK", "腾讯控股"),
    ],
)
def test_add_stock_api_normalizes_market_suffix_and_keeps_manual_name(
    submitted_ticker, expected_ticker, expected_market, display_name
):
    """缺少规范化或忽略 name 时，会写入错误代码/市场或丢失显示名。"""
    response = TestClient(app).post(
        "/api/stocks/",
        json={"ticker": submitted_ticker, "name": display_name},
    )

    assert response.status_code == 201, response.text
    assert response.json()["ticker"] == expected_ticker
    assert response.json()["market"] == expected_market
    assert response.json()["name"] == display_name

    db = database.get_db()
    try:
        row = db.execute("SELECT ticker, name, market FROM stocks").fetchone()
    finally:
        db.close()
    assert tuple(row) == (expected_ticker, display_name, expected_market)


def test_add_stock_api_detects_duplicate_after_ticker_normalization():
    """只按原始字符串判重时，600519.SS 和 600519 会被重复加入。"""
    client = TestClient(app)
    first = client.post("/api/stocks/", json={"ticker": "600519.SS"})
    second = client.post("/api/stocks/", json={"ticker": "600519"})

    assert first.status_code == 201, first.text
    assert second.status_code == 409, second.text
    assert len(client.get("/api/stocks/").json()) == 1


@pytest.mark.parametrize("ticker", ["AAPL.SS", "0000012.HK", ""])
def test_add_stock_api_rejects_malformed_exchange_suffixes(ticker):
    """后缀代码格式不合法时不能写入没有行情的错误监控项。"""
    response = TestClient(app).post("/api/stocks/", json={"ticker": ticker})

    assert response.status_code == 422, response.text
    assert TestClient(app).get("/api/stocks/").json() == []
