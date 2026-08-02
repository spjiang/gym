"""零售库存与收银测试。"""

from fastapi.testclient import TestClient


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def test_stock_and_retail_flow(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    cat = client.post(
        "/api/v1/retail/categories",
        headers=admin_headers,
        json={"merchant_id": gym_id, "name": "补给"},
    )
    assert cat.status_code == 200, cat.text

    sku = client.post(
        "/api/v1/retail/skus",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "category_id": cat.json()["id"],
            "name": "蛋白粉",
            "price": "199.00",
            "unit": "罐",
            "low_stock_threshold": 2,
        },
    )
    assert sku.status_code == 200, sku.text
    sku_id = sku.json()["id"]
    assert sku.json()["stock_qty"] == 0

    inn = client.post(
        f"/api/v1/retail/skus/{sku_id}/stock/in",
        headers=admin_headers,
        json={"quantity": 5, "note": "首批"},
    )
    assert inn.status_code == 200
    assert inn.json()["stock_qty"] == 5

    bad_out = client.post(
        f"/api/v1/retail/skus/{sku_id}/stock/out",
        headers=admin_headers,
        json={"quantity": 99},
    )
    assert bad_out.status_code == 400
    assert bad_out.json()["code"] == "insufficient_stock"

    adj = client.post(
        f"/api/v1/retail/skus/{sku_id}/stock/adjust",
        headers=admin_headers,
        json={"target_qty": 2, "note": "盘点"},
    )
    assert adj.status_code == 200
    assert adj.json()["stock_qty"] == 2

    low = client.get(
        f"/api/v1/retail/skus?merchant_id={gym_id}&low_stock=true",
        headers=admin_headers,
    ).json()
    assert any(x["id"] == sku_id for x in low)

    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13520000001", "name": "零售客", "merchant_id": gym_id},
    ).json()

    order = client.post(
        "/api/v1/retail/orders",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "items": [{"sku_id": sku_id, "quantity": 2}],
        },
    )
    assert order.status_code == 200, order.text
    assert order.json()["order_type"] == "retail"
    order_id = order.json()["id"]

    # 先把库存手动出光，支付应失败
    client.post(
        f"/api/v1/retail/skus/{sku_id}/stock/out",
        headers=admin_headers,
        json={"quantity": 2},
    )
    deny_pay = client.post(
        f"/api/v1/orders/{order_id}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    assert deny_pay.status_code == 400
    assert deny_pay.json()["code"] == "insufficient_stock"
    assert client.get(f"/api/v1/orders", headers=admin_headers).json()
    still = next(o for o in client.get("/api/v1/orders", headers=admin_headers).json() if o["id"] == order_id)
    assert still["status"] == "pending"

    # 补货后再付
    client.post(
        f"/api/v1/retail/skus/{sku_id}/stock/in",
        headers=admin_headers,
        json={"quantity": 10},
    )
    paid = client.post(
        f"/api/v1/orders/{order_id}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"
    after = client.get(f"/api/v1/retail/skus?merchant_id={gym_id}", headers=admin_headers).json()
    sku_after = next(s for s in after if s["id"] == sku_id)
    assert sku_after["stock_qty"] == 8  # 10 - 2

    refund = client.post(f"/api/v1/orders/{order_id}/refund", headers=admin_headers)
    assert refund.status_code == 200
    assert refund.json()["status"] == "refunded"
    after2 = next(
        s
        for s in client.get(f"/api/v1/retail/skus?merchant_id={gym_id}", headers=admin_headers).json()
        if s["id"] == sku_id
    )
    assert after2["stock_qty"] == 10


def test_inactive_sku_cannot_sell(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    sku = client.post(
        "/api/v1/retail/skus",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "停用商品",
            "price": "10.00",
            "low_stock_threshold": 0,
        },
    ).json()
    client.post(f"/api/v1/retail/skus/{sku['id']}/stock/in", headers=admin_headers, json={"quantity": 1})
    client.post(f"/api/v1/retail/skus/{sku['id']}/deactivate", headers=admin_headers)
    r = client.post(
        "/api/v1/retail/orders",
        headers=admin_headers,
        json={"merchant_id": gym_id, "items": [{"sku_id": sku["id"], "quantity": 1}]},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "sku_inactive"
