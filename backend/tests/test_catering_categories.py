"""餐饮菜单分类：独立维护，菜品挂分类而非自由文本。"""

from fastapi.testclient import TestClient


def _bar_id(client: TestClient, headers: dict) -> int:
    merchants = client.get("/api/v1/merchants", headers=headers).json()
    bar = next((m for m in merchants if "catering" in (m.get("subsystem_codes") or [])), None)
    assert bar is not None, "种子应包含餐饮商户"
    return bar["id"]


def test_catering_category_crud_and_menu_link(client: TestClient, admin_headers: dict):
    mid = _bar_id(client, admin_headers)

    drinks = client.post(
        "/api/v1/catering/categories",
        headers=admin_headers,
        json={"merchant_id": mid, "name": "特调饮品", "sort_order": 20},
    )
    assert drinks.status_code == 200, drinks.text
    drinks_id = drinks.json()["id"]
    assert drinks.json()["name"] == "特调饮品"
    assert drinks.json()["is_active"] is True

    snacks = client.post(
        "/api/v1/catering/categories",
        headers=admin_headers,
        json={"merchant_id": mid, "name": "下酒小食", "sort_order": 10},
    )
    assert snacks.status_code == 200, snacks.text
    snacks_id = snacks.json()["id"]

    dup = client.post(
        "/api/v1/catering/categories",
        headers=admin_headers,
        json={"merchant_id": mid, "name": "特调饮品"},
    )
    assert dup.status_code == 409

    listed = client.get(
        "/api/v1/catering/categories",
        headers=admin_headers,
        params={"merchant_id": mid, "page": 1, "page_size": 100},
    )
    assert listed.status_code == 200, listed.text
    names = [x["name"] for x in listed.json()["items"] if x["id"] in {drinks_id, snacks_id}]
    assert names == ["下酒小食", "特调饮品"]

    item = client.post(
        "/api/v1/catering/menu-items",
        headers=admin_headers,
        json={
            "merchant_id": mid,
            "name": "分类挂载气泡水",
            "category_id": drinks_id,
            "price": "28.00",
        },
    )
    assert item.status_code == 200, item.text
    assert item.json()["category_id"] == drinks_id
    assert item.json()["category"] == "特调饮品"

    by_name = client.post(
        "/api/v1/catering/menu-items",
        headers=admin_headers,
        json={"merchant_id": mid, "name": "同名分类鸡翅", "category": "下酒小食", "price": "32.00"},
    )
    assert by_name.status_code == 200, by_name.text
    assert by_name.json()["category_id"] == snacks_id
    assert by_name.json()["category"] == "下酒小食"

    renamed = client.patch(
        f"/api/v1/catering/categories/{drinks_id}",
        headers=admin_headers,
        json={"merchant_id": mid, "name": "气泡与咖啡", "sort_order": 20},
    )
    assert renamed.status_code == 200, renamed.text
    refreshed = client.get(
        "/api/v1/catering/menu-items",
        headers=admin_headers,
        params={"merchant_id": mid, "q": "分类挂载气泡水"},
    )
    assert refreshed.json()["items"][0]["category"] == "气泡与咖啡"

    off = client.post(
        f"/api/v1/catering/categories/{drinks_id}/deactivate",
        headers=admin_headers,
        params={"merchant_id": mid},
    )
    assert off.status_code == 200, off.text
    assert off.json()["is_active"] is False

    missing = client.post(
        "/api/v1/catering/menu-items",
        headers=admin_headers,
        json={"merchant_id": mid, "name": "无效分类菜", "category_id": 999999, "price": "10.00"},
    )
    assert missing.status_code == 400
    assert missing.json()["code"] == "invalid_category"
