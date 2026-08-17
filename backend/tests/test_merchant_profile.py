"""商户基础档案：证照、多联系人、租赁有效期、上传与权限。"""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.systems.platform.services.merchant_lease import lease_metrics


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc``\x00\x00"
        b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def test_site_admin_saves_license_and_contacts(client: TestClient, admin_headers: dict):
    types = client.get("/api/v1/merchant-types", headers=admin_headers).json()
    gym = next(t for t in types if t["code"] == "gym")
    created = client.post(
        "/api/v1/merchants",
        headers=admin_headers,
        json={
            "merchant_type_id": gym["id"],
            "name": "档案测试店",
            "status": "preparing",
            "legal_name": "北京档案测试有限公司",
            "credit_code": "91110108MA01TEST1X",
            "license_no": "91110108MA01TEST1X",
            "legal_person": "张三",
            "registered_address": "北京市昌平区回龙观",
            "business_address": "综合场地一层",
            "contact_phone": "010-88880000",
            "contact_email": "shop@example.com",
            "business_hours": "08:00-22:00",
            "description": "测试档案",
            "contacts": [
                {"name": "店长", "phone": "13800001111", "title": "店长", "kind": "primary"},
                {"name": "值班A", "phone": "13800001112", "title": "值班", "kind": "emergency"},
                {"name": "值班B", "phone": "13800001113", "title": "安保", "kind": "emergency"},
            ],
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["has_license"] is True
    assert body["emergency_contact_count"] == 2
    assert body["credit_code"] == "91110108MA01TEST1X"
    assert [c["kind"] for c in body["contacts"]] == ["primary", "emergency", "emergency"]

    mid = body["id"]
    bad = client.patch(
        f"/api/v1/merchants/{mid}",
        headers=admin_headers,
        json={"credit_code": "123"},
    )
    assert bad.status_code == 400

    patched = client.patch(
        f"/api/v1/merchants/{mid}",
        headers=admin_headers,
        json={
            "contacts": [
                {"name": "新店长", "phone": "13800002222", "kind": "primary", "title": "店长"},
                {"name": "紧急", "phone": "13800002223", "kind": "emergency"},
            ]
        },
    )
    assert patched.status_code == 200, patched.text
    assert len(patched.json()["contacts"]) == 2
    assert patched.json()["contacts"][0]["name"] == "新店长"


def test_merchant_admin_can_edit_own_profile_only(client: TestClient, admin_headers: dict):
    merchants = client.get("/api/v1/merchants", headers=admin_headers).json()
    gym = merchants[0]
    other = merchants[1] if len(merchants) > 1 else None
    staff = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "profile_admin",
            "password": "Merchant@1",
            "display_name": "档案管理员",
            "merchant_id": gym["id"],
            "role_codes": ["gym_admin"],
        },
    )
    assert staff.status_code == 200, staff.text
    token = client.post(
        "/api/v1/auth/login", json={"username": "profile_admin", "password": "Merchant@1"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ok = client.patch(
        f"/api/v1/merchants/{gym['id']}",
        headers=headers,
        json={
            "legal_name": "本店可改",
            "contacts": [{"name": "本店联系人", "phone": "13900000001", "kind": "emergency"}],
            "status": "disabled",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["legal_name"] == "本店可改"
    assert ok.json()["status"] == gym["status"]
    assert ok.json()["emergency_contact_count"] == 1
    assert ok.json()["lease_ends_on"] == gym.get("lease_ends_on")

    lease_denied = client.patch(
        f"/api/v1/merchants/{gym['id']}",
        headers=headers,
        json={"lease_starts_on": "2020-01-01", "lease_ends_on": "2020-12-31"},
    )
    assert lease_denied.status_code == 200
    assert lease_denied.json()["lease_starts_on"] == gym.get("lease_starts_on")
    assert lease_denied.json()["lease_ends_on"] == gym.get("lease_ends_on")

    if other is not None:
        denied = client.patch(
            f"/api/v1/merchants/{other['id']}",
            headers=headers,
            json={"legal_name": "跨店"},
        )
        assert denied.status_code == 403


def test_lease_metrics_states():
    today = date(2026, 8, 16)
    unset = lease_metrics(None, None, today=today)
    assert unset["lease_state"] == "unset"
    assert unset["lease_progress"] is None

    active = lease_metrics(date(2025, 1, 1), date(2026, 12, 31), today=today)
    assert active["lease_state"] == "active"
    assert active["lease_days_remaining"] == (date(2026, 12, 31) - today).days
    assert 0 < active["lease_progress"] < 100

    expiring = lease_metrics(date(2026, 1, 1), today + timedelta(days=10), today=today)
    assert expiring["lease_state"] == "expiring"
    assert expiring["lease_days_remaining"] == 10

    expired = lease_metrics(date(2025, 1, 1), date(2026, 8, 1), today=today)
    assert expired["lease_state"] == "expired"
    assert expired["lease_progress"] == 0

    upcoming = lease_metrics(date(2026, 9, 1), date(2027, 8, 31), today=today)
    assert upcoming["lease_state"] == "not_started"


def test_site_admin_saves_lease_period(client: TestClient, admin_headers: dict):
    types = client.get("/api/v1/merchant-types", headers=admin_headers).json()
    gym = next(t for t in types if t["code"] == "gym")
    today = date.today()
    starts = (today - timedelta(days=100)).isoformat()
    ends = (today + timedelta(days=265)).isoformat()
    created = client.post(
        "/api/v1/merchants",
        headers=admin_headers,
        json={
            "merchant_type_id": gym["id"],
            "name": "租期测试店",
            "status": "active",
            "lease_starts_on": starts,
            "lease_ends_on": ends,
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["lease_starts_on"] == starts
    assert body["lease_ends_on"] == ends
    assert body["lease_state"] == "active"
    assert body["lease_days_remaining"] == 265
    assert body["lease_days_total"] == 365
    assert body["lease_progress"] == 73

    bad = client.patch(
        f"/api/v1/merchants/{body['id']}",
        headers=admin_headers,
        json={"lease_starts_on": ends, "lease_ends_on": starts},
    )
    assert bad.status_code == 400

    listed = client.get("/api/v1/merchants", headers=admin_headers).json()
    row = next(m for m in listed if m["id"] == body["id"])
    assert row["lease_days_remaining"] == 265


def test_upload_license_image(client: TestClient, admin_headers: dict, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        resp = client.post(
            "/api/v1/uploads",
            headers=admin_headers,
            files={"file": ("license.png", _png_bytes(), "image/png")},
        )
        assert resp.status_code == 200, resp.text
        url = resp.json()["url"]
        assert url.startswith("/api/v1/files/")
        fetched = client.get(url)
        assert fetched.status_code == 200
        assert fetched.content.startswith(b"\x89PNG")
    finally:
        get_settings.cache_clear()
