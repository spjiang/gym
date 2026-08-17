"""会籍卡种、办卡履约与门禁联动测试。"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def _prepare_point_and_member(client: TestClient, headers: dict, gym_id: int):
    member = client.post(
        "/api/v1/members",
        headers=headers,
        json={"phone": "13700000001", "name": "会籍会员", "merchant_id": gym_id},
    ).json()
    point = client.post(
        "/api/v1/access-points",
        headers=headers,
        json={"name": "会籍门", "merchant_id": gym_id},
    ).json()
    client.post(
        "/api/v1/devices",
        headers=headers,
        json={"access_point_id": point["id"], "device_code": "mem-pad", "api_key": "mem-key"},
    )
    return member, point


def test_product_requires_access_points_to_activate(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    r = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "月卡",
            "product_type": "term",
            "price": "299.00",
            "duration_days": 30,
            "access_point_ids": [],
            "is_active": True,
        },
    )
    assert r.status_code == 400


def test_update_membership_product(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    _, point = _prepare_point_and_member(client, admin_headers, gym_id)
    created = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "月卡草稿",
            "product_type": "term",
            "price": "299.00",
            "duration_days": 30,
            "access_point_ids": [point["id"]],
            "is_active": False,
        },
    )
    assert created.status_code == 200, created.text
    product_id = created.json()["id"]
    patched = client.patch(
        f"/api/v1/membership-products/{product_id}",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "标准月卡",
            "product_type": "term",
            "price": "329.00",
            "duration_days": 31,
            "access_point_ids": [point["id"]],
            "is_active": True,
            "is_trial": True,
        },
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["name"] == "标准月卡"
    assert body["price"] == "329.00"
    assert body["duration_days"] == 31
    assert body["is_active"] is True
    assert body["is_trial"] is True


def test_create_product_and_purchase_flow(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    member, point = _prepare_point_and_member(client, admin_headers, gym_id)

    product = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "季卡",
            "product_type": "term",
            "price": "799.00",
            "duration_days": 90,
            "access_point_ids": [point["id"]],
            "is_active": True,
        },
    )
    assert product.status_code == 200, product.text
    product_id = product.json()["id"]

    order = client.post(
        "/api/v1/memberships/purchase",
        headers=admin_headers,
        json={"member_id": member["id"], "product_id": product_id, "merchant_id": gym_id},
    )
    assert order.status_code == 200, order.text
    assert order.json()["order_type"] == "membership"
    assert order.json()["status"] == "pending"
    order_id = order.json()["id"]

    paid = client.post(
        f"/api/v1/orders/{order_id}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"

    memberships = client.get(
        f"/api/v1/memberships?merchant_id={gym_id}&member_id={member['id']}",
        headers=admin_headers,
    ).json()["items"]
    assert len(memberships) == 1
    assert memberships[0]["status"] == "active"
    membership_id = memberships[0]["id"]

    # 通行放行
    ok = client.post(
        "/api/v1/device/access/verify",
        headers={"X-Device-Code": "mem-pad", "X-Device-Key": "mem-key"},
        json={"member_id": member["id"]},
    )
    assert ok.json()["allowed"] is True

    # 续卡延期
    ends_before = memberships[0]["ends_at"]
    renew_order = client.post(
        "/api/v1/memberships/renew",
        headers=admin_headers,
        json={"membership_id": membership_id, "product_id": product_id},
    )
    assert renew_order.status_code == 200
    client.post(
        f"/api/v1/orders/{renew_order.json()['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    after = client.get(
        f"/api/v1/memberships?merchant_id={gym_id}&member_id={member['id']}",
        headers=admin_headers,
    ).json()["items"][0]
    assert after["ends_at"] > ends_before

    # 编辑到期日
    new_end = (datetime.now(timezone.utc) + timedelta(days=120)).date().isoformat()
    patched_m = client.patch(
        f"/api/v1/memberships/{membership_id}",
        headers=admin_headers,
        json={"ends_at": f"{new_end}T23:59:59", "status": "active"},
    )
    assert patched_m.status_code == 200, patched_m.text
    assert patched_m.json()["ends_at"][:10] == new_end
    assert patched_m.json()["status"] == "active"

    noted = client.patch(
        f"/api/v1/memberships/{membership_id}",
        headers=admin_headers,
        json={"remark": "前台备注：周末只练团课"},
    )
    assert noted.status_code == 200, noted.text
    assert noted.json()["remark"] == "前台备注：周末只练团课"

    other = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13700000002", "name": "改挂会员", "merchant_id": gym_id},
    ).json()
    other_product = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "月卡纠错",
            "product_type": "term",
            "price": "299.00",
            "duration_days": 30,
            "access_point_ids": [point["id"]],
            "is_active": True,
        },
    ).json()
    reassigned = client.patch(
        f"/api/v1/memberships/{membership_id}",
        headers=admin_headers,
        json={"member_id": other["id"], "product_id": other_product["id"]},
    )
    assert reassigned.status_code == 200, reassigned.text
    assert reassigned.json()["member_id"] == other["id"]
    assert reassigned.json()["product_id"] == other_product["id"]

    gym_admin = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "mem_gym_admin",
            "password": "Admin@123456",
            "display_name": "店长",
            "merchant_id": gym_id,
            "role_codes": ["gym_admin"],
        },
    ).json()
    assert gym_admin.get("id")
    token = client.post(
        "/api/v1/auth/login",
        json={"username": "mem_gym_admin", "password": "Admin@123456"},
    )
    assert token.status_code == 200, token.text
    ops_headers = {"Authorization": f"Bearer {token.json()['access_token']}"}
    denied_identity = client.patch(
        f"/api/v1/memberships/{membership_id}",
        headers=ops_headers,
        json={"member_id": member["id"]},
    )
    assert denied_identity.status_code == 403

    # 停卡后拒绝
    freeze = client.post(f"/api/v1/memberships/{membership_id}/freeze", headers=admin_headers)
    assert freeze.status_code == 200
    assert freeze.json()["status"] == "frozen"
    denied = client.post(
        "/api/v1/device/access/verify",
        headers={"X-Device-Code": "mem-pad", "X-Device-Key": "mem-key"},
        json={"member_id": member["id"]},
    )
    assert denied.json()["allowed"] is False


def test_list_membership_products_filters(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    _, point = _prepare_point_and_member(client, admin_headers, gym_id)
    term = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "检索年卡",
            "product_type": "term",
            "price": "2000.00",
            "duration_days": 365,
            "access_point_ids": [point["id"]],
            "is_active": True,
            "is_trial": False,
        },
    )
    assert term.status_code == 200, term.text
    trial = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "检索体验周卡",
            "product_type": "term",
            "price": "39.00",
            "duration_days": 7,
            "access_point_ids": [point["id"]],
            "is_active": True,
            "is_trial": True,
        },
    )
    assert trial.status_code == 200, trial.text
    count = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "检索次卡",
            "product_type": "count",
            "price": "399.00",
            "session_count": 10,
            "access_point_ids": [],
            "is_active": False,
        },
    )
    assert count.status_code == 200, count.text
    term_id = term.json()["id"]
    trial_id = trial.json()["id"]
    count_id = count.json()["id"]

    by_name = client.get(
        f"/api/v1/membership-products?merchant_id={gym_id}&q=体验周卡",
        headers=admin_headers,
    )
    assert by_name.status_code == 200
    assert {x["id"] for x in by_name.json()["items"]} == {trial_id}

    by_id = client.get(
        f"/api/v1/membership-products?merchant_id={gym_id}&q={term_id}",
        headers=admin_headers,
    )
    assert any(x["id"] == term_id for x in by_id.json()["items"])

    by_type = client.get(
        f"/api/v1/membership-products?merchant_id={gym_id}&product_type=count",
        headers=admin_headers,
    )
    ids = {x["id"] for x in by_type.json()["items"]}
    assert count_id in ids
    assert term_id not in ids

    inactive = client.get(
        f"/api/v1/membership-products?merchant_id={gym_id}&is_active=false",
        headers=admin_headers,
    )
    assert count_id in {x["id"] for x in inactive.json()["items"]}
    assert term_id not in {x["id"] for x in inactive.json()["items"]}

    trials = client.get(
        f"/api/v1/membership-products?merchant_id={gym_id}&is_trial=true",
        headers=admin_headers,
    )
    assert {x["id"] for x in trials.json()["items"]} == {trial_id}

    by_point = client.get(
        f"/api/v1/membership-products?merchant_id={gym_id}&access_point_id={point['id']}",
        headers=admin_headers,
    )
    point_ids = {x["id"] for x in by_point.json()["items"]}
    assert {term_id, trial_id} <= point_ids
    assert count_id not in point_ids

    cheap = client.get(
        f"/api/v1/membership-products?merchant_id={gym_id}&price_max=50",
        headers=admin_headers,
    )
    assert {x["id"] for x in cheap.json()["items"]} == {trial_id}
