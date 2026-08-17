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
    assert any(x["id"] == sku_id for x in low["items"])

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
    assert client.get("/api/v1/orders", headers=admin_headers).json()["items"]
    still = next(o for o in client.get("/api/v1/orders", headers=admin_headers).json()["items"] if o["id"] == order_id)
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
    sku_after = next(s for s in after["items"] if s["id"] == sku_id)
    assert sku_after["stock_qty"] == 8  # 10 - 2

    refund = client.post(f"/api/v1/orders/{order_id}/refund", headers=admin_headers)
    assert refund.status_code == 200
    assert refund.json()["status"] == "refunded"
    after2 = next(
        s
        for s in client.get(f"/api/v1/retail/skus?merchant_id={gym_id}", headers=admin_headers).json()["items"]
        if s["id"] == sku_id
    )
    assert after2["stock_qty"] == 10


def test_sku_search_detail_and_patch(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    cat = client.post(
        "/api/v1/retail/categories",
        headers=admin_headers,
        json={"merchant_id": gym_id, "name": "饮品检索"},
    ).json()
    sku = client.post(
        "/api/v1/retail/skus",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "category_id": cat["id"],
            "name": "电解质水检索",
            "price": "8.00",
            "unit": "瓶",
            "barcode": "6901234567890",
            "low_stock_threshold": 5,
        },
    )
    assert sku.status_code == 200, sku.text
    sku_id = sku.json()["id"]

    by_name = client.get(
        f"/api/v1/retail/skus?merchant_id={gym_id}&q=电解质",
        headers=admin_headers,
    )
    assert by_name.status_code == 200
    assert any(x["id"] == sku_id for x in by_name.json()["items"])

    by_barcode = client.get(
        f"/api/v1/retail/skus?merchant_id={gym_id}&q=6901234567890",
        headers=admin_headers,
    )
    assert any(x["id"] == sku_id for x in by_barcode.json()["items"])

    by_cat = client.get(
        f"/api/v1/retail/skus?merchant_id={gym_id}&category_id={cat['id']}",
        headers=admin_headers,
    )
    assert any(x["id"] == sku_id for x in by_cat.json()["items"])

    miss = client.get(
        f"/api/v1/retail/skus?merchant_id={gym_id}&q=不存在的商品xyz",
        headers=admin_headers,
    )
    assert all(x["id"] != sku_id for x in miss.json()["items"])

    detail = client.get(f"/api/v1/retail/skus/{sku_id}", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["name"] == "电解质水检索"
    assert detail.json()["barcode"] == "6901234567890"

    patched = client.patch(
        f"/api/v1/retail/skus/{sku_id}",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "电解质水检索",
            "price": "9.50",
            "unit": "瓶",
            "barcode": "6901234567890",
            "category_id": cat["id"],
            "low_stock_threshold": 8,
            "is_active": True,
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["price"] == "9.50"
    assert patched.json()["low_stock_threshold"] == 8


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


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc``\x00\x00"
        b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def test_sku_remark_and_images(client: TestClient, admin_headers: dict, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        gym_id = _gym_id(client, admin_headers)
        uploaded = client.post(
            "/api/v1/uploads",
            headers=admin_headers,
            files={"file": ("sku.png", _png_bytes(), "image/png")},
        )
        assert uploaded.status_code == 200, uploaded.text
        url = uploaded.json()["url"]

        created = client.post(
            "/api/v1/retail/skus",
            headers=admin_headers,
            json={
                "merchant_id": gym_id,
                "name": "蛋白棒备注图",
                "price": "12.00",
                "unit": "根",
                "remark": "冷藏陈列，临期先出",
                "image_urls": [url, url],
            },
        )
        assert created.status_code == 200, created.text
        body = created.json()
        assert body["remark"] == "冷藏陈列，临期先出"
        assert body["image_urls"] == [url]

        bad = client.patch(
            f"/api/v1/retail/skus/{body['id']}",
            headers=admin_headers,
            json={
                "merchant_id": gym_id,
                "name": "蛋白棒备注图",
                "price": "12.00",
                "image_urls": ["https://evil.example/a.png"],
            },
        )
        assert bad.status_code == 400
        assert bad.json()["code"] == "invalid_image"

        too_many = client.patch(
            f"/api/v1/retail/skus/{body['id']}",
            headers=admin_headers,
            json={
                "merchant_id": gym_id,
                "name": "蛋白棒备注图",
                "price": "12.00",
                "image_urls": [f"/api/v1/files/{i:032x}.png" for i in range(10)],
            },
        )
        assert too_many.status_code == 400
        assert too_many.json()["code"] == "too_many_images"

        patched = client.patch(
            f"/api/v1/retail/skus/{body['id']}",
            headers=admin_headers,
            json={
                "merchant_id": gym_id,
                "name": "蛋白棒备注图",
                "price": "12.00",
                "remark": "  ",
                "image_urls": [],
            },
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["remark"] is None
        assert patched.json()["image_urls"] == []
    finally:
        get_settings.cache_clear()
