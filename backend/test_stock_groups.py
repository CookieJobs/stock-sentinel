"""股票监控分组接口测试——使用临时数据库，不触发外部行情请求。"""
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
    """每个用例使用独立数据库，避免污染真实监控列表。"""
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


def test_creates_a_trimmed_group_and_lists_its_member_count():
    """缺少分组 API 或未清洗名称时，用户无法建立可用分组。"""
    client = TestClient(app)

    created = client.post("/api/stock-groups/", json={"name": "  长期持有  "})

    assert created.status_code == 201, created.text
    assert created.json()["name"] == "长期持有"
    assert created.json()["stock_ids"] == []
    assert created.json()["stock_count"] == 0
    assert client.get("/api/stock-groups/").json() == [created.json()]


def test_adds_the_same_stock_to_multiple_groups_idempotently():
    """分组若不是多对多或重复写入会膨胀计数，用户无法按主题交叉归类。"""
    client = TestClient(app)
    stock = client.post("/api/stocks/", json={"ticker": "AAPL", "name": "苹果"}).json()
    long_term = client.post("/api/stock-groups/", json={"name": "长期"}).json()
    technology = client.post("/api/stock-groups/", json={"name": "科技"}).json()

    first_add = client.post(
        f"/api/stock-groups/{long_term['id']}/stocks",
        json={"stock_ids": [stock["id"]]},
    )
    repeated_add = client.post(
        f"/api/stock-groups/{long_term['id']}/stocks",
        json={"stock_ids": [stock["id"]]},
    )
    second_group_add = client.post(
        f"/api/stock-groups/{technology['id']}/stocks",
        json={"stock_ids": [stock["id"]]},
    )

    assert first_add.status_code == 200, first_add.text
    assert repeated_add.status_code == 200, repeated_add.text
    assert second_group_add.status_code == 200, second_group_add.text
    groups = {group["name"]: group for group in client.get("/api/stock-groups/").json()}
    assert groups["长期"]["stock_ids"] == [stock["id"]]
    assert groups["科技"]["stock_ids"] == [stock["id"]]


def test_removing_a_member_or_a_group_keeps_the_monitored_stock():
    """“移出分组”和“删除分组”不能误删整个监控列表的股票。"""
    client = TestClient(app)
    stock = client.post("/api/stocks/", json={"ticker": "AAPL"}).json()
    primary = client.post("/api/stock-groups/", json={"name": "重点"}).json()
    backup = client.post("/api/stock-groups/", json={"name": "备选"}).json()
    for group in (primary, backup):
        assert client.post(
            f"/api/stock-groups/{group['id']}/stocks",
            json={"stock_ids": [stock["id"]]},
        ).status_code == 200

    removed = client.request(
        "DELETE",
        f"/api/stock-groups/{primary['id']}/stocks",
        json={"stock_ids": [stock["id"]]},
    )
    deleted_group = client.delete(f"/api/stock-groups/{primary['id']}")

    assert removed.status_code == 200, removed.text
    assert deleted_group.status_code == 200, deleted_group.text
    assert client.get("/api/stocks/").json()[0]["id"] == stock["id"]
    assert client.get("/api/stock-groups/").json() == [{
        "id": backup["id"],
        "name": "备选",
        "stock_ids": [stock["id"]],
        "stock_count": 1,
        "created_at": backup["created_at"],
    }]


def test_bulk_delete_removes_selected_stocks_from_every_group():
    """全局“删除自选”必须删股票并自动清理所有分组成员关系。"""
    client = TestClient(app)
    apple = client.post("/api/stocks/", json={"ticker": "AAPL"}).json()
    microsoft = client.post("/api/stocks/", json={"ticker": "MSFT"}).json()
    group = client.post("/api/stock-groups/", json={"name": "美股"}).json()
    assert client.post(
        f"/api/stock-groups/{group['id']}/stocks",
        json={"stock_ids": [apple["id"], microsoft["id"]]},
    ).status_code == 200

    deleted = client.post("/api/stocks/bulk-delete", json={"stock_ids": [apple["id"]]})

    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"deleted_stock_ids": [apple["id"]], "deleted_count": 1}
    assert [stock["id"] for stock in client.get("/api/stocks/").json()] == [microsoft["id"]]
    assert client.get("/api/stock-groups/").json()[0]["stock_ids"] == [microsoft["id"]]


def test_group_validation_rename_and_atomic_member_validation():
    """分组名称应唯一可改名，错误股票 ID 不得造成部分加入。"""
    client = TestClient(app)
    stock = client.post("/api/stocks/", json={"ticker": "AAPL"}).json()
    group = client.post("/api/stock-groups/", json={"name": "核心"}).json()

    empty = client.post("/api/stock-groups/", json={"name": "   "})
    duplicate = client.post("/api/stock-groups/", json={"name": "核心"})
    renamed = client.put(f"/api/stock-groups/{group['id']}", json={"name": "  核心持仓 "})
    invalid_members = client.post(
        f"/api/stock-groups/{group['id']}/stocks",
        json={"stock_ids": [stock["id"], 99999]},
    )

    assert empty.status_code == 422, empty.text
    assert duplicate.status_code == 422, duplicate.text
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "核心持仓"
    assert invalid_members.status_code == 404, invalid_members.text
    assert client.get("/api/stock-groups/").json()[0]["stock_ids"] == []
