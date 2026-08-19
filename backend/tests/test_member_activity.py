"""会员端活动浏览与自助报名。"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from tests.test_agreements import enable_agreement


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def _member_login(client: TestClient, phone: str) -> dict:
    from app.core.config import get_settings

    send = client.post("/api/v1/member/auth/otp/send", json={"phone": phone})
    assert send.status_code == 200, send.text
    code = get_settings().member_otp_mock_code
    verify = client.post("/api/v1/member/auth/otp/verify", json={"phone": phone, "code": code})
    assert verify.status_code == 200, verify.text
    return {"Authorization": f"Bearer {verify.json()['access_token']}"}


def _payload(gym_id: int, name: str, **overrides) -> dict:
    starts = datetime.now(timezone.utc) + timedelta(days=2)
    body = {
        "merchant_id": gym_id,
        "name": name,
        "category": "赛事",
        "location": "多功能厅",
        "starts_at": starts.isoformat(),
        "ends_at": (starts + timedelta(hours=2)).isoformat(),
        "register_ends_at": (starts - timedelta(hours=1)).isoformat(),
        "capacity": 8,
        "price": "0",
    }
    body.update(overrides)
    return body


def test_member_can_see_and_join_published_activity(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13530000081", "name": "自助报名", "merchant_id": gym_id},
    ).json()
    mheaders = _member_login(client, member["phone"])

    draft = client.post(
        "/api/v1/activities",
        headers=admin_headers,
        json=_payload(gym_id, "会员不可见草稿"),
    ).json()
    hidden = client.get(
        f"/api/v1/member/activities?merchant_id={gym_id}",
        headers=mheaders,
    )
    assert hidden.status_code == 200, hidden.text
    assert all(x["id"] != draft["id"] for x in hidden.json())

    published = client.post(
        "/api/v1/activities",
        headers=admin_headers,
        json=_payload(gym_id, "夏季体测"),
    ).json()
    client.post(f"/api/v1/activities/{published['id']}/publish", headers=admin_headers)

    listed = client.get(
        f"/api/v1/member/activities?merchant_id={gym_id}",
        headers=mheaders,
    )
    assert listed.status_code == 200, listed.text
    hit = next(x for x in listed.json() if x["id"] == published["id"])
    assert hit["name"] == "夏季体测"
    assert hit["can_register"] is True
    assert hit["already_registered"] is False

    home = client.get(f"/api/v1/member/home?merchant_id={gym_id}", headers=mheaders)
    assert home.status_code == 200, home.text
    assert any(x["id"] == published["id"] for x in home.json()["activities"])

    enable_agreement(client, admin_headers, gym_id, "activity")
    joined = client.post(
        "/api/v1/member/activity-registrations",
        headers=mheaders,
        json={"merchant_id": gym_id, "activity_id": published["id"]},
    )
    assert joined.status_code == 200, joined.text
    assert joined.json()["order"] is None
    assert joined.json()["registration"]["status"] == "confirmed"

    detail = client.get(f"/api/v1/member/activities/{published['id']}", headers=mheaders)
    assert detail.status_code == 200
    assert detail.json()["already_registered"] is True
    assert detail.json()["can_register"] is False

    dup = client.post(
        "/api/v1/member/activity-registrations",
        headers=mheaders,
        json={"merchant_id": gym_id, "activity_id": published["id"]},
    )
    assert dup.status_code == 409

    paid_act = client.post(
        "/api/v1/activities",
        headers=admin_headers,
        json=_payload(gym_id, "付费体验", price="68.00"),
    ).json()
    client.post(f"/api/v1/activities/{paid_act['id']}/publish", headers=admin_headers)
    paid = client.post(
        "/api/v1/member/activity-registrations",
        headers=mheaders,
        json={"merchant_id": gym_id, "activity_id": paid_act["id"]},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["registration"]["status"] == "pending"
    assert paid.json()["order"]["order_type"] == "activity"

    mine = client.get(
        f"/api/v1/member/activity-registrations?merchant_id={gym_id}",
        headers=mheaders,
    )
    assert mine.status_code == 200
    assert {x["activity_id"] for x in mine.json()} >= {published["id"], paid_act["id"]}
