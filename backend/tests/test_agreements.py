"""购买协议：后台维护、会员读取、未启用则不能买。"""

from fastapi.testclient import TestClient

from app.core.config import get_settings


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def _bar_id(client: TestClient, headers: dict) -> int:
    merchants = client.get("/api/v1/merchants", headers=headers).json()
    return next(m["id"] for m in merchants if "catering" in (m.get("subsystem_codes") or []))


def _member_headers(client: TestClient, phone: str) -> dict:
    assert client.post("/api/v1/member/auth/otp/send", json={"phone": phone}).status_code == 200
    verify = client.post(
        "/api/v1/member/auth/otp/verify",
        json={"phone": phone, "code": get_settings().member_otp_mock_code},
    )
    assert verify.status_code == 200, verify.text
    return {"Authorization": f"Bearer {verify.json()['access_token']}"}


def enable_agreement(
    client: TestClient,
    headers: dict,
    merchant_id: int,
    scene: str,
    *,
    title: str = "观野FIT会员协议",
    content: str = "请遵守场馆规则。",
) -> dict:
    created = client.post(
        "/api/v1/agreements",
        headers=headers,
        json={
            "merchant_id": merchant_id,
            "scene": scene,
            "title": title,
            "content": content,
            "is_enabled": True,
        },
    )
    if created.status_code == 409:
        listed = client.get(
            "/api/v1/agreements",
            headers=headers,
            params={"merchant_id": merchant_id, "scene": scene},
        )
        assert listed.status_code == 200, listed.text
        row = next(x for x in listed.json()["items"] if x["scene"] == scene)
        patched = client.patch(
            f"/api/v1/agreements/{row['id']}",
            headers=headers,
            json={"title": title, "content": content, "is_enabled": True},
        )
        assert patched.status_code == 200, patched.text
        return patched.json()
    assert created.status_code == 200, created.text
    return created.json()


def test_admin_agreement_unique_and_member_read(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    created = enable_agreement(client, admin_headers, gym_id, "membership", content="会籍条款正文")
    assert created["title"] == "观野FIT会员协议"
    assert created["scene"] == "membership"
    assert created["is_enabled"] is True
    assert "code" not in created

    dup = client.post(
        "/api/v1/agreements",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "scene": "membership",
            "title": "重复",
            "content": "另一份",
            "is_enabled": True,
        },
    )
    assert dup.status_code == 409
    assert dup.json()["code"] == "conflict"

    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13880002001", "name": "协议会员", "merchant_id": gym_id},
    ).json()
    mheaders = _member_headers(client, member["phone"])
    got = client.get(
        "/api/v1/member/agreements",
        headers=mheaders,
        params={"merchant_id": gym_id, "scene": "membership"},
    )
    assert got.status_code == 200, got.text
    body = got.json()
    assert set(body.keys()) == {"id", "title", "content"}
    assert body["title"] == "观野FIT会员协议"
    assert body["content"] == "会籍条款正文"
    assert "is_enabled" not in body

    client.patch(
        f"/api/v1/agreements/{created['id']}",
        headers=admin_headers,
        json={"is_enabled": False},
    )
    hidden = client.get(
        "/api/v1/member/agreements",
        headers=mheaders,
        params={"merchant_id": gym_id, "scene": "membership"},
    )
    assert hidden.status_code == 400
    assert hidden.json()["code"] == "agreement_required"


def test_membership_purchase_requires_enabled_agreement(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    point = client.post(
        "/api/v1/access-points",
        headers=admin_headers,
        json={"name": "协议门", "merchant_id": gym_id},
    ).json()
    product = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "协议月卡",
            "product_type": "term",
            "price": "99.00",
            "duration_days": 30,
            "access_point_ids": [point["id"]],
            "is_active": True,
        },
    ).json()
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13880002002", "name": "购卡协议", "merchant_id": gym_id},
    ).json()
    mheaders = _member_headers(client, member["phone"])

    blocked = client.post(
        "/api/v1/member/orders/membership",
        headers=mheaders,
        json={"merchant_id": gym_id, "product_id": product["id"]},
    )
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "agreement_required"

    enable_agreement(client, admin_headers, gym_id, "membership")
    ok = client.post(
        "/api/v1/member/orders/membership",
        headers=mheaders,
        json={"merchant_id": gym_id, "product_id": product["id"]},
    )
    assert ok.status_code == 200, ok.text


def test_dining_checkout_requires_enabled_agreement(client: TestClient, admin_headers: dict):
    bar_id = _bar_id(client, admin_headers)
    item = client.post(
        "/api/v1/catering/menu-items",
        headers=admin_headers,
        json={"merchant_id": bar_id, "name": "协议饮品", "category": "饮品", "price": "18.00"},
    ).json()
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13880002003", "name": "点餐协议", "merchant_id": bar_id},
    ).json()
    mheaders = _member_headers(client, member["phone"])
    blocked = client.post(
        "/api/v1/member/catering/checkout",
        headers=mheaders,
        json={"merchant_id": bar_id, "items": [{"menu_item_id": item["id"], "quantity": 1}]},
    )
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "agreement_required"

    enable_agreement(client, admin_headers, bar_id, "dining", title="观野BAR点餐须知")
    ok = client.post(
        "/api/v1/member/catering/checkout",
        headers=mheaders,
        json={"merchant_id": bar_id, "items": [{"menu_item_id": item["id"], "quantity": 1}]},
    )
    assert ok.status_code == 200, ok.text
