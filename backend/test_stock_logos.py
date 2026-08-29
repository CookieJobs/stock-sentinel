"""股票 Logo 缓存与 API 测试——使用临时 SQLite，不访问外部图片源。"""
import base64
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))

import database
import data_fetcher
import logo_service
from data_fetcher import DataFetcher
from main import app


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/"
    "ScL5WQAAAABJRU5ErkJggg=="
)
PNG_DATA_URL = "data:image/png;base64," + base64.b64encode(PNG_BYTES).decode()


@pytest.fixture(autouse=True)
def isolated_stock_db(tmp_path, monkeypatch):
    """每个用例使用独立 Logo 缓存，防止读写真实自选库。"""
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


def test_uploaded_png_round_trips_and_invalid_data_is_rejected():
    """取消签名校验会把伪造或非图片上传写入 Logo 缓存。"""
    data, content_type = logo_service.parse_logo_data_url(PNG_DATA_URL)
    logo_service.save_logo("HK", "00700", data, content_type, "manual")

    saved = logo_service.get_logo("HK", "00700")
    assert saved["content"] == PNG_BYTES
    assert saved["content_type"] == "image/png"
    assert saved["source"] == "manual"

    with pytest.raises(ValueError, match="PNG、JPEG 或 WebP"):
        logo_service.parse_logo_data_url("data:image/svg+xml;base64,PHN2Zy8+")
    with pytest.raises(ValueError, match="图片内容与声明格式不一致"):
        logo_service.parse_logo_data_url("data:image/png;base64,SGVsbG8=")
    too_large = b"\x89PNG\r\n\x1a\n" + b"a" * (logo_service.MAX_LOGO_BYTES + 1)
    oversized = "data:image/png;base64," + base64.b64encode(too_large).decode()
    with pytest.raises(ValueError, match="不能超过"):
        logo_service.parse_logo_data_url(oversized)


def test_logo_api_exposes_local_image_and_stock_url():
    """缺少本地 Logo 路由会让前端退回热链或无法更新行内图标。"""
    client = TestClient(app)
    added = client.post("/api/stocks/", json={"ticker": "AAPL", "name": "Apple"})
    assert added.status_code == 201, added.text

    uploaded = client.put(
        "/api/stock-logos",
        json={"market": "US", "ticker": "AAPL", "data_url": PNG_DATA_URL},
    )
    assert uploaded.status_code == 204, uploaded.text

    stock = client.get("/api/stocks/AAPL")
    assert stock.status_code == 200, stock.text
    assert stock.json()["logo_url"].startswith("/api/stock-logos?market=US&ticker=AAPL")

    image = client.get(stock.json()["logo_url"])
    assert image.status_code == 200, image.text
    assert image.headers["content-type"] == "image/png"
    assert image.content == PNG_BYTES


def test_logo_api_rejects_invalid_upload_and_clears_cached_image():
    """忽略上传校验或无法删除缓存会让错误图片长期留在监控页。"""
    client = TestClient(app)
    added = client.post("/api/stocks/", json={"ticker": "00700", "name": "腾讯控股"})
    assert added.status_code == 201, added.text
    assert added.json()["market"] == "HK"

    invalid = client.put(
        "/api/stock-logos",
        json={"market": "HK", "ticker": "00700", "data_url": "data:image/svg+xml;base64,PHN2Zy8+"},
    )
    assert invalid.status_code == 422, invalid.text

    uploaded = client.put(
        "/api/stock-logos",
        json={"market": "HK", "ticker": "00700", "data_url": PNG_DATA_URL},
    )
    assert uploaded.status_code == 204, uploaded.text
    deleted = client.delete("/api/stock-logos?market=HK&ticker=00700")
    assert deleted.status_code == 204, deleted.text
    assert client.get("/api/stock-logos?market=HK&ticker=00700").status_code == 404


def test_deleting_stock_removes_its_cached_logo():
    """若删除自选不清理 Logo，已移除股票的品牌图仍会留在个人数据库。"""
    client = TestClient(app)
    assert client.post("/api/stocks/", json={"ticker": "00700", "name": "腾讯控股"}).status_code == 201
    assert client.put(
        "/api/stock-logos",
        json={"market": "HK", "ticker": "00700", "data_url": PNG_DATA_URL},
    ).status_code == 204

    deleted = client.delete("/api/stocks/00700")

    assert deleted.status_code == 200, deleted.text
    assert client.get("/api/stock-logos?market=HK&ticker=00700").status_code == 404


def test_adding_us_stock_caches_its_finnhub_logo(monkeypatch):
    """移除美股资料中的 Logo 传递或缓存时，新添股票不应继续声称有本地 Logo。"""
    class FakeResponse:
        status_code = 200
        headers = {"content-type": "image/png"}

        def iter_content(self, chunk_size):
            return iter([PNG_BYTES])

        def close(self):
            pass

    monkeypatch.setattr(
        DataFetcher,
        "get_stock_info",
        staticmethod(lambda ticker, api_key="": {
            "ticker": ticker,
            "name": "Apple Inc.",
            "market": "US",
            "logo_url": "https://static.finnhub.io/logo/apple.png",
        }),
    )
    monkeypatch.setattr(
        logo_service,
        "requests",
        SimpleNamespace(get=lambda *args, **kwargs: FakeResponse()),
        raising=False,
    )

    client = TestClient(app)
    added = client.post("/api/stocks/", json={"ticker": "AAPL"})
    assert added.status_code == 201, added.text
    assert added.json()["logo_url"] is not None

    image = client.get(added.json()["logo_url"])
    assert image.status_code == 200, image.text
    assert image.content == PNG_BYTES


def test_finnhub_quote_exposes_profile_logo_to_monitor(monkeypatch):
    """遗漏 profile2.logo 会使后续本地缓存永远没有可下载的来源。"""
    class FakeResponse:
        status_code = 200

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    responses = iter([
        FakeResponse({"c": 100, "dp": 1.5, "pc": 98, "t": 0}),
        FakeResponse({"metric": {}}),
        FakeResponse({"name": "Apple Inc.", "finnhubIndustry": "Technology",
                      "logo": "https://static.finnhub.io/logo/apple.png"}),
    ])
    monkeypatch.setattr(data_fetcher._SESSION, "get", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(DataFetcher, "_get_finnhub_daily_bars", staticmethod(lambda ticker, key: []))

    quote = DataFetcher._get_finnhub_quote("AAPL", "test-key")

    assert quote["logo_url"] == "https://static.finnhub.io/logo/apple.png"


def test_failed_finnhub_logo_cache_does_not_prevent_adding_stock(monkeypatch):
    """若 Logo 下载异常冒泡，非关键图片会阻断用户新增自选。"""
    monkeypatch.setattr(
        DataFetcher,
        "get_stock_info",
        staticmethod(lambda ticker, api_key="": {
            "ticker": ticker,
            "name": "Apple Inc.",
            "market": "US",
            "logo_url": "https://static.finnhub.io/logo/apple.png",
        }),
    )
    monkeypatch.setattr(
        logo_service,
        "cache_finnhub_logo",
        lambda *args: (_ for _ in ()).throw(RuntimeError("temporary image outage")),
    )

    response = TestClient(app).post("/api/stocks/", json={"ticker": "AAPL"})

    assert response.status_code == 201, response.text
    assert response.json()["logo_url"] is None
