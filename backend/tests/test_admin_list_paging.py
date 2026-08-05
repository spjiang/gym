"""管理端列表分页契约。"""

from fastapi.testclient import TestClient


def test_members_page_and_search(client: TestClient, admin_headers: dict):
    gym_id = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13980001101", "name": "分页甲", "merchant_id": gym_id},
    )
    client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13980001102", "name": "分页乙", "merchant_id": gym_id},
    )

    page = client.get("/api/v1/members?page=1&page_size=1", headers=admin_headers)
    assert page.status_code == 200, page.text
    body = page.json()
    assert set(body.keys()) >= {"items", "total", "page", "page_size"}
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert body["total"] >= 2
    assert len(body["items"]) == 1
    assert "acquisition_source" in body["items"][0]

    hit = client.get("/api/v1/members?q=分页甲", headers=admin_headers).json()
    assert hit["total"] >= 1
    assert any(m["name"] == "分页甲" for m in hit["items"])


def test_orders_page_with_member(client: TestClient, admin_headers: dict):
    gym_id = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13980002201", "name": "订单会员", "merchant_id": gym_id},
    ).json()
    order = client.post(
        "/api/v1/orders",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "order_type": "retail",
            "title": "分页订单样例",
            "amount": "12.00",
        },
    ).json()
    assert order["member"]["id"] == member["id"]

    listed = client.get(
        "/api/v1/orders?page=1&page_size=20&q=分页订单",
        headers=admin_headers,
    )
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] >= 1
    row = next(o for o in body["items"] if o["id"] == order["id"])
    assert row["member"]["name"] == "订单会员"
    assert row["member"]["phone"] == "13980002201"


def test_memberships_and_access_events_page(client: TestClient, admin_headers: dict):
    gym_id = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    ms = client.get(f"/api/v1/memberships?merchant_id={gym_id}&page=1&page_size=5", headers=admin_headers)
    assert ms.status_code == 200, ms.text
    body = ms.json()
    assert set(body.keys()) >= {"items", "total", "page", "page_size"}

    ev = client.get("/api/v1/access-events?page=1&page_size=5", headers=admin_headers)
    assert ev.status_code == 200, ev.text
    assert set(ev.json().keys()) >= {"items", "total", "page", "page_size"}


def test_a3_a4_page_contracts(client: TestClient, admin_headers: dict):
    gym_id = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    for path in (
        f"/api/v1/pt-packages?merchant_id={gym_id}&page=1&page_size=5",
        f"/api/v1/group-bookings?merchant_id={gym_id}&page=1&page_size=5",
        f"/api/v1/coupons/member-coupons?merchant_id={gym_id}&page=1&page_size=5",
        f"/api/v1/retail/movements?merchant_id={gym_id}&page=1&page_size=5",
        f"/api/v1/equipment/assets?merchant_id={gym_id}&page=1&page_size=5",
        f"/api/v1/equipment/repairs?merchant_id={gym_id}&page=1&page_size=5",
        "/api/v1/staff?page=1&page_size=5",
        f"/api/v1/notifications?merchant_id={gym_id}&page=1&page_size=5",
        f"/api/v1/orders?merchant_id={gym_id}&order_type=dining&page=1&page_size=5",
    ):
        resp = client.get(path, headers=admin_headers)
        assert resp.status_code == 200, f"{path}: {resp.text}"
        body = resp.json()
        assert set(body.keys()) >= {"items", "total", "page", "page_size"}, path
