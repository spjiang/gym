"""活动管理与报名签到测试。"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def _member(client: TestClient, headers: dict, gym_id: int, phone: str, name: str) -> dict:
    return client.post(
        "/api/v1/members",
        headers=headers,
        json={"phone": phone, "name": name, "merchant_id": gym_id},
    ).json()


def _activity_payload(gym_id: int, name: str, **overrides) -> dict:
    starts = datetime.now(timezone.utc) + timedelta(days=3)
    payload = {
        "merchant_id": gym_id,
        "name": name,
        "category": "赛事",
        "location": "多功能厅",
        "starts_at": starts.isoformat(),
        "ends_at": (starts + timedelta(hours=2)).isoformat(),
        "register_ends_at": (starts - timedelta(hours=1)).isoformat(),
        "capacity": 2,
        "price": "0",
    }
    payload.update(overrides)
    return payload


def test_free_activity_register_and_checkin(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    created = client.post(
        "/api/v1/activities",
        headers=admin_headers,
        json=_activity_payload(gym_id, "会员开放日"),
    )
    assert created.status_code == 200, created.text
    activity = created.json()
    assert activity["status"] == "draft"
    assert activity["requires_payment"] is False

    member = _member(client, admin_headers, gym_id, "13530000001", "活动会员")
    early = client.post(
        "/api/v1/activity-registrations",
        headers=admin_headers,
        json={"activity_id": activity["id"], "member_id": member["id"]},
    )
    assert early.status_code == 400
    assert early.json()["code"] == "activity_not_open"

    published = client.post(f"/api/v1/activities/{activity['id']}/publish", headers=admin_headers)
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"

    reg = client.post(
        "/api/v1/activity-registrations",
        headers=admin_headers,
        json={"activity_id": activity["id"], "member_id": member["id"], "note": "现场登记"},
    )
    assert reg.status_code == 200, reg.text
    # 免费活动直接确认，无需生成订单
    assert reg.json()["order"] is None
    registration = reg.json()["registration"]
    assert registration["status"] == "confirmed"
    assert registration["member"]["name"] == "活动会员"

    dup = client.post(
        "/api/v1/activity-registrations",
        headers=admin_headers,
        json={"activity_id": activity["id"], "member_id": member["id"]},
    )
    assert dup.status_code == 409
    assert dup.json()["code"] == "already_registered"

    checkin = client.post(
        f"/api/v1/activity-registrations/{registration['id']}/checkin",
        headers=admin_headers,
    )
    assert checkin.status_code == 200, checkin.text
    assert checkin.json()["status"] == "attended"
    assert checkin.json()["checked_in_at"]

    again = client.post(
        f"/api/v1/activity-registrations/{registration['id']}/checkin",
        headers=admin_headers,
    )
    assert again.status_code == 400
    assert again.json()["code"] == "already_checked_in"

    detail = client.get(f"/api/v1/activities/{activity['id']}", headers=admin_headers)
    assert detail.json()["registered_count"] == 1
    assert detail.json()["attended_count"] == 1
    assert detail.json()["remaining_capacity"] == 1


def test_paid_activity_requires_payment_before_checkin(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    activity = client.post(
        "/api/v1/activities",
        headers=admin_headers,
        json=_activity_payload(gym_id, "搏击体验课", price="88.00", capacity=1),
    ).json()
    assert activity["requires_payment"] is True
    client.post(f"/api/v1/activities/{activity['id']}/publish", headers=admin_headers)

    member = _member(client, admin_headers, gym_id, "13530000002", "付费会员")
    reg = client.post(
        "/api/v1/activity-registrations",
        headers=admin_headers,
        json={"activity_id": activity["id"], "member_id": member["id"]},
    )
    assert reg.status_code == 200, reg.text
    registration = reg.json()["registration"]
    order = reg.json()["order"]
    assert registration["status"] == "pending"
    assert order["order_type"] == "activity"
    assert order["amount"] == "88.00"

    too_early = client.post(
        f"/api/v1/activity-registrations/{registration['id']}/checkin",
        headers=admin_headers,
    )
    assert too_early.status_code == 400
    assert too_early.json()["code"] == "invalid_state"

    paid = client.post(
        f"/api/v1/orders/{order['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text

    listed = client.get(
        f"/api/v1/activity-registrations?merchant_id={gym_id}&activity_id={activity['id']}",
        headers=admin_headers,
    ).json()["items"]
    assert listed[0]["status"] == "confirmed"

    # 名额已满
    other = _member(client, admin_headers, gym_id, "13530000003", "候补会员")
    full = client.post(
        "/api/v1/activity-registrations",
        headers=admin_headers,
        json={"activity_id": activity["id"], "member_id": other["id"]},
    )
    assert full.status_code == 409
    assert full.json()["code"] == "activity_full"

    blocked = client.post(
        f"/api/v1/activity-registrations/{registration['id']}/cancel",
        headers=admin_headers,
    )
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "order_paid"

    checkin = client.post(
        f"/api/v1/activity-registrations/{registration['id']}/checkin",
        headers=admin_headers,
    )
    assert checkin.status_code == 200, checkin.text
    assert checkin.json()["status"] == "attended"


def test_activity_cancel_releases_registrations(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    activity = client.post(
        "/api/v1/activities",
        headers=admin_headers,
        json=_activity_payload(gym_id, "户外拉练", capacity=0),
    ).json()
    client.post(f"/api/v1/activities/{activity['id']}/publish", headers=admin_headers)
    member = _member(client, admin_headers, gym_id, "13530000004", "拉练会员")
    reg = client.post(
        "/api/v1/activity-registrations",
        headers=admin_headers,
        json={"activity_id": activity["id"], "member_id": member["id"]},
    ).json()["registration"]

    cancelled = client.post(f"/api/v1/activities/{activity['id']}/cancel", headers=admin_headers)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"

    rows = client.get(
        f"/api/v1/activity-registrations?activity_id={activity['id']}",
        headers=admin_headers,
    ).json()["items"]
    assert [r["id"] for r in rows] == [reg["id"]]
    assert rows[0]["status"] == "cancelled"

    frozen = client.patch(
        f"/api/v1/activities/{activity['id']}",
        headers=admin_headers,
        json={"name": "改名"},
    )
    assert frozen.status_code == 400
    assert frozen.json()["code"] == "invalid_state"


def test_activity_validation_rules(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    starts = datetime.now(timezone.utc) + timedelta(days=1)
    bad_window = client.post(
        "/api/v1/activities",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "时间错乱",
            "starts_at": starts.isoformat(),
            "ends_at": (starts - timedelta(hours=1)).isoformat(),
        },
    )
    assert bad_window.status_code == 400
    assert bad_window.json()["code"] == "invalid_time"

    activity = client.post(
        "/api/v1/activities",
        headers=admin_headers,
        json=_activity_payload(gym_id, "名额校验活动", capacity=2),
    ).json()
    client.post(f"/api/v1/activities/{activity['id']}/publish", headers=admin_headers)
    member = _member(client, admin_headers, gym_id, "13530000005", "名额会员")
    client.post(
        "/api/v1/activity-registrations",
        headers=admin_headers,
        json={"activity_id": activity["id"], "member_id": member["id"]},
    )
    shrink = client.patch(
        f"/api/v1/activities/{activity['id']}",
        headers=admin_headers,
        json={"capacity": 0},
    )
    assert shrink.status_code == 200, shrink.text
    assert shrink.json()["capacity"] == 0

    closed = client.post(f"/api/v1/activities/{activity['id']}/close", headers=admin_headers)
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    republish = client.post(f"/api/v1/activities/{activity['id']}/publish", headers=admin_headers)
    assert republish.status_code == 200
    assert republish.json()["status"] == "published"


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc``\x00\x00"
        b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def test_activity_cover_and_share_link(client: TestClient, admin_headers: dict, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        gym_id = _gym_id(client, admin_headers)
        uploaded = client.post(
            "/api/v1/uploads",
            headers=admin_headers,
            files={"file": ("poster.png", _png_bytes(), "image/png")},
        )
        assert uploaded.status_code == 200, uploaded.text
        url = uploaded.json()["url"]

        created = client.post(
            "/api/v1/activities",
            headers=admin_headers,
            json=_activity_payload(gym_id, "海报活动", cover_url=url),
        )
        assert created.status_code == 200, created.text
        assert created.json()["cover_url"] == url

        bad = client.patch(
            f"/api/v1/activities/{created.json()['id']}",
            headers=admin_headers,
            json={"cover_url": "https://example.com/a.jpg"},
        )
        assert bad.status_code == 400

        cleared = client.patch(
            f"/api/v1/activities/{created.json()['id']}",
            headers=admin_headers,
            json={"cover_url": None},
        )
        assert cleared.status_code == 200
        assert cleared.json()["cover_url"] is None

        link = client.get(
            f"/api/v1/activities/{created.json()['id']}/share-link",
            headers=admin_headers,
        )
        assert link.status_code == 200, link.text
        assert f"/m/{gym_id}/gym/activities/{created.json()['id']}" in link.json()["url"]
    finally:
        get_settings.cache_clear()


def _publish_paid_activity(client: TestClient, headers: dict, gym_id: int, name: str, *, capacity: int = 1) -> dict:
    activity = client.post(
        "/api/v1/activities",
        headers=headers,
        json=_activity_payload(gym_id, name, price="88.00", capacity=capacity),
    ).json()
    client.post(f"/api/v1/activities/{activity['id']}/publish", headers=headers)
    return activity


def _register_and_pay(
    client: TestClient, headers: dict, activity_id: int, member_id: int
) -> dict:
    reg = client.post(
        "/api/v1/activity-registrations",
        headers=headers,
        json={"activity_id": activity_id, "member_id": member_id},
    )
    assert reg.status_code == 200, reg.text
    order = reg.json()["order"]
    paid = client.post(
        f"/api/v1/orders/{order['id']}/pay/offline",
        headers=headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text
    return reg.json()["registration"]


def test_attended_activity_refund_requires_force(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    activity = _publish_paid_activity(client, admin_headers, gym_id, "已签到禁退")
    member = _member(client, admin_headers, gym_id, "13530000021", "签到后退")
    registration = _register_and_pay(client, admin_headers, activity["id"], member["id"])
    checkin = client.post(
        f"/api/v1/activity-registrations/{registration['id']}/checkin",
        headers=admin_headers,
    )
    assert checkin.status_code == 200, checkin.text

    blocked = client.post(
        f"/api/v1/orders/{registration['order_id']}/refund",
        headers=admin_headers,
        json={"channel": "offline_cash", "reason": "已签到仍想退"},
    )
    assert blocked.status_code == 400, blocked.text
    assert blocked.json()["code"] == "activity_attended"

    forced = client.post(
        f"/api/v1/orders/{registration['order_id']}/refund",
        headers=admin_headers,
        json={"channel": "offline_cash", "reason": "超管强制", "force": True},
    )
    assert forced.status_code == 200, forced.text
    assert forced.json()["status"] == "refunded"

    rows = client.get(
        f"/api/v1/activity-registrations?activity_id={activity['id']}",
        headers=admin_headers,
    ).json()["items"]
    assert rows[0]["status"] == "attended"
    detail = client.get(f"/api/v1/activities/{activity['id']}", headers=admin_headers).json()
    assert detail["registered_count"] == 1
    assert detail["remaining_capacity"] == 0


def test_no_show_releases_capacity_and_allows_reregister(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    activity = _publish_paid_activity(client, admin_headers, gym_id, "缺席让座", capacity=1)
    member = _member(client, admin_headers, gym_id, "13530000022", "缺席会员")
    other = _member(client, admin_headers, gym_id, "13530000023", "候补会员")
    registration = _register_and_pay(client, admin_headers, activity["id"], member["id"])

    marked = client.post(
        f"/api/v1/activity-registrations/{registration['id']}/no-show",
        headers=admin_headers,
    )
    assert marked.status_code == 200, marked.text
    assert marked.json()["status"] == "no_show"

    detail = client.get(f"/api/v1/activities/{activity['id']}", headers=admin_headers).json()
    assert detail["registered_count"] == 0
    assert detail["remaining_capacity"] == 1

    again = client.post(
        "/api/v1/activity-registrations",
        headers=admin_headers,
        json={"activity_id": activity["id"], "member_id": member["id"]},
    )
    assert again.status_code == 200, again.text
    assert again.json()["order"] is None
    assert again.json()["registration"]["status"] == "confirmed"
    assert again.json()["registration"]["order_id"] == registration["order_id"]

    full = client.post(
        "/api/v1/activity-registrations",
        headers=admin_headers,
        json={"activity_id": activity["id"], "member_id": other["id"]},
    )
    assert full.status_code == 409
    assert full.json()["code"] == "activity_full"


def test_stale_pending_hold_released_on_activity_query(client: TestClient, admin_headers: dict):
    from datetime import datetime, timedelta, timezone

    from app.core import db as db_module
    from app.systems.platform.models.commerce import Order

    gym_id = _gym_id(client, admin_headers)
    activity = _publish_paid_activity(client, admin_headers, gym_id, "超时占坑")
    member = _member(client, admin_headers, gym_id, "13530000024", "占坑会员")
    reg = client.post(
        "/api/v1/activity-registrations",
        headers=admin_headers,
        json={"activity_id": activity["id"], "member_id": member["id"]},
    )
    assert reg.status_code == 200, reg.text
    order_id = reg.json()["order"]["id"]
    assert client.get(f"/api/v1/activities/{activity['id']}", headers=admin_headers).json()[
        "remaining_capacity"
    ] == 0

    db = db_module.SessionLocal()
    try:
        order = db.get(Order, order_id)
        assert order is not None
        order.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()
    finally:
        db.close()

    detail = client.get(f"/api/v1/activities/{activity['id']}", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["remaining_capacity"] == 1
    assert detail.json()["registered_count"] == 0
