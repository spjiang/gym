"""超管重置员工/会员密码，以及会员密码登录。"""

from fastapi.testclient import TestClient


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def _create_staff(
    client: TestClient,
    headers: dict,
    *,
    username: str,
    password: str,
    merchant_id: int | None,
    role_codes: list[str],
) -> dict:
    r = client.post(
        "/api/v1/staff",
        headers=headers,
        json={
            "username": username,
            "password": password,
            "display_name": username,
            "merchant_id": merchant_id,
            "role_codes": role_codes,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_site_admin_resets_staff_and_member_password(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    staff = _create_staff(
        client,
        admin_headers,
        username="pwd_staff",
        password="OldStaff@1",
        merchant_id=gym_id,
        role_codes=["gym_ops"],
    )
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13881110001", "name": "改密会员", "merchant_id": gym_id},
    ).json()
    assert member["has_password"] is False

    reset_staff = client.post(
        f"/api/v1/staff/{staff['id']}/password",
        headers=admin_headers,
        json={"password": "NewStaff@1"},
    )
    assert reset_staff.status_code == 200, reset_staff.text
    assert client.post("/api/v1/auth/login", json={"username": "pwd_staff", "password": "OldStaff@1"}).status_code == 401
    assert _login(client, "pwd_staff", "NewStaff@1")

    reset_member = client.post(
        f"/api/v1/members/{member['id']}/password",
        headers=admin_headers,
        json={"password": "NewMember@1"},
    )
    assert reset_member.status_code == 200, reset_member.text
    login = client.post(
        "/api/v1/member/auth/password",
        json={"phone": "13881110001", "password": "NewMember@1"},
    )
    assert login.status_code == 200, login.text
    me = client.get("/api/v1/member/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.status_code == 200
    assert me.json()["id"] == member["id"]

    listed = client.get("/api/v1/members", headers=admin_headers, params={"q": "13881110001"}).json()
    assert listed["items"][0]["has_password"] is True


def test_merchant_admin_can_reset_own_scope_only(client: TestClient, admin_headers: dict):
    merchants = client.get("/api/v1/merchants", headers=admin_headers).json()
    gym_id = merchants[0]["id"]
    types = client.get("/api/v1/merchant-types", headers=admin_headers).json()
    bar = next(t for t in types if t["code"] == "bar")
    other = client.post(
        "/api/v1/merchants",
        headers=admin_headers,
        json={
            "merchant_type_id": bar["id"],
            "name": "改密酒吧",
            "status": "active",
            "subsystem_codes": ["catering"],
        },
    ).json()

    admin = _create_staff(
        client,
        admin_headers,
        username="pwd_madmin",
        password="Merchant@1",
        merchant_id=gym_id,
        role_codes=["gym_admin"],
    )
    peer = _create_staff(
        client,
        admin_headers,
        username="pwd_peer",
        password="Peer@1234",
        merchant_id=gym_id,
        role_codes=["gym_ops"],
    )
    foreign = _create_staff(
        client,
        admin_headers,
        username="pwd_bar",
        password="Bar@12345",
        merchant_id=other["id"],
        role_codes=["bar_admin"],
    )
    site_admins = client.get("/api/v1/staff", headers=admin_headers, params={"q": "admin"}).json()["items"]
    site_admin_id = next(s["id"] for s in site_admins if "site_admin" in s["role_codes"])

    own_member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13881110002", "name": "本店会员", "merchant_id": gym_id},
    ).json()
    other_member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13881110003", "name": "他店会员", "merchant_id": other["id"]},
    ).json()

    mheaders = _login(client, "pwd_madmin", "Merchant@1")

    assert (
        client.post(
            f"/api/v1/staff/{peer['id']}/password",
            headers=mheaders,
            json={"password": "PeerNew@1"},
        ).status_code
        == 200
    )
    assert _login(client, "pwd_peer", "PeerNew@1")

    assert (
        client.post(
            f"/api/v1/staff/{foreign['id']}/password",
            headers=mheaders,
            json={"password": "Hack@123"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/staff/{site_admin_id}/password",
            headers=mheaders,
            json={"password": "Hack@123"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/staff/{admin['id']}/password",
            headers=mheaders,
            json={"password": "SelfNew@1"},
        ).status_code
        == 200
    )

    assert (
        client.post(
            f"/api/v1/members/{own_member['id']}/password",
            headers=mheaders,
            json={"password": "OwnMem@1"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/members/{other_member['id']}/password",
            headers=mheaders,
            json={"password": "Hack@123"},
        ).status_code
        == 403
    )
    ok = client.post(
        "/api/v1/member/auth/password",
        json={"phone": "13881110002", "password": "OwnMem@1"},
    )
    assert ok.status_code == 200, ok.text


def test_front_desk_cannot_reset_member_password(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    _create_staff(
        client,
        admin_headers,
        username="pwd_front",
        password="Front@123",
        merchant_id=gym_id,
        role_codes=["gym_ops"],
    )
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={
            "phone": "13881110004",
            "name": "前台不可改",
            "merchant_id": gym_id,
            "password": "Keep@123",
        },
    ).json()
    assert member["has_password"] is True

    front = _login(client, "pwd_front", "Front@123")
    denied = client.post(
        f"/api/v1/members/{member['id']}/password",
        headers=front,
        json={"password": "Steal@123"},
    )
    assert denied.status_code == 403
    create_denied = client.post(
        "/api/v1/members",
        headers=front,
        json={
            "phone": "13881110005",
            "name": "前台设密",
            "merchant_id": gym_id,
            "password": "Steal@123",
        },
    )
    assert create_denied.status_code == 403

    bad = client.post(
        "/api/v1/member/auth/password",
        json={"phone": "13881110004", "password": "wrong-pass"},
    )
    assert bad.status_code == 401
    unset = client.post(
        "/api/v1/member/auth/password",
        json={"phone": "13900009999", "password": "Keep@123"},
    )
    assert unset.status_code == 401
