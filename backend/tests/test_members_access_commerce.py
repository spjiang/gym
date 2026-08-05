"""会员、门禁、交易测试。"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def test_member_unique_and_multi_merchant(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    types = client.get("/api/v1/merchant-types", headers=admin_headers).json()
    bar = next(t for t in types if t["code"] == "bar")
    bar_m = client.post(
        "/api/v1/merchants",
        headers=admin_headers,
        json={"merchant_type_id": bar["id"], "name": "酒吧B", "status": "active"},
    ).json()

    empty = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "", "name": "", "merchant_id": gym_id},
    )
    assert empty.status_code == 422

    r = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13900000001", "name": "张三", "merchant_id": gym_id},
    )
    assert r.status_code == 200
    mid = r.json()["id"]

    r = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13900000001", "name": "重名", "merchant_id": gym_id},
    )
    assert r.status_code == 409

    r = client.post(
        f"/api/v1/members/{mid}/merchants",
        headers=admin_headers,
        json={"merchant_id": bar_m["id"]},
    )
    assert r.status_code == 200
    assert set(r.json()["merchant_ids"]) == {gym_id, bar_m["id"]}


def test_member_delete(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    created = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13900000088", "name": "待删", "merchant_id": gym_id},
    )
    assert created.status_code == 200
    mid = created.json()["id"]

    deleted = client.delete(f"/api/v1/members/{mid}", headers=admin_headers)
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True

    listed = client.get("/api/v1/members", headers=admin_headers).json()["items"]
    assert all(m["id"] != mid for m in listed)


def test_access_grant_verify_revoke_heartbeat(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13900000011", "name": "李四", "merchant_id": gym_id},
    ).json()
    point = client.post(
        "/api/v1/access-points",
        headers=admin_headers,
        json={"name": "正门", "merchant_id": gym_id},
    ).json()
    device = client.post(
        "/api/v1/devices",
        headers=admin_headers,
        json={"access_point_id": point["id"], "device_code": "pad-001", "api_key": "secret-key"},
    ).json()

    now = datetime.now(timezone.utc)
    grant = client.post(
        "/api/v1/grants",
        headers=admin_headers,
        json={
            "member_id": member["id"],
            "access_point_id": point["id"],
            "merchant_id": gym_id,
            "valid_from": (now - timedelta(hours=1)).isoformat(),
            "valid_until": (now + timedelta(days=30)).isoformat(),
        },
    ).json()

    dheaders = {"X-Device-Code": "pad-001", "X-Device-Key": "secret-key"}
    hb = client.post("/api/v1/device/heartbeat", headers=dheaders)
    assert hb.status_code == 200

    ok = client.post(
        "/api/v1/device/access/verify",
        headers=dheaders,
        json={"member_id": member["id"]},
    )
    assert ok.status_code == 200
    assert ok.json()["allowed"] is True

    # 过期授权
    expired_member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13900000012", "name": "过期", "merchant_id": gym_id},
    ).json()
    client.post(
        "/api/v1/grants",
        headers=admin_headers,
        json={
            "member_id": expired_member["id"],
            "access_point_id": point["id"],
            "merchant_id": gym_id,
            "valid_from": (now - timedelta(days=10)).isoformat(),
            "valid_until": (now - timedelta(days=1)).isoformat(),
        },
    )
    expired = client.post(
        "/api/v1/device/access/verify",
        headers=dheaders,
        json={"member_id": expired_member["id"]},
    )
    assert expired.json()["allowed"] is False

    # 撤销后拒绝
    client.post(f"/api/v1/grants/{grant['id']}/revoke", headers=admin_headers)
    denied = client.post(
        "/api/v1/device/access/verify",
        headers=dheaders,
        json={"member_id": member["id"]},
    )
    assert denied.json()["allowed"] is False

    devices = client.get("/api/v1/devices", headers=admin_headers).json()
    assert any(d["device_code"] == "pad-001" and d["is_online"] for d in devices)
    assert device["id"]


def test_order_offline_refund_and_online_unconfigured(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    order = client.post(
        "/api/v1/orders",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "order_type": "retail",
            "title": "蛋白粉",
            "amount": "99.00",
        },
    ).json()
    assert order["status"] == "pending"

    online = client.post(f"/api/v1/orders/{order['id']}/pay/online", headers=admin_headers, json={})
    assert online.status_code == 503

    paid = client.post(
        f"/api/v1/orders/{order['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"

    refunded = client.post(f"/api/v1/orders/{order['id']}/refund", headers=admin_headers)
    assert refunded.status_code == 200
    assert refunded.json()["status"] == "refunded"
