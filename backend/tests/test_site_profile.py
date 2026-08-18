"""场地门户资料：观野SPACE 介绍与会员端读取。"""

from fastapi.testclient import TestClient


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc``\x00\x00"
        b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _member_headers(client: TestClient, phone: str) -> dict:
    from app.core.config import get_settings

    send = client.post("/api/v1/member/auth/otp/send", json={"phone": phone})
    assert send.status_code == 200, send.text
    verify = client.post(
        "/api/v1/member/auth/otp/verify",
        json={"phone": phone, "code": get_settings().member_otp_mock_code},
    )
    assert verify.status_code == 200, verify.text
    return {"Authorization": f"Bearer {verify.json()['access_token']}"}


def test_site_profile_save_and_member_portal(client: TestClient, admin_headers: dict, tmp_path, monkeypatch):
    from app.core.config import get_settings

    got = client.get("/api/v1/site/profile", headers=admin_headers)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["name"]

    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        uploaded = client.post(
            "/api/v1/uploads",
            headers=admin_headers,
            files={"file": ("cover.png", _png_bytes(), "image/png")},
        )
        assert uploaded.status_code == 200, uploaded.text
        url = uploaded.json()["url"]

        saved = client.put(
            "/api/v1/site/profile",
            headers=admin_headers,
            json={
                "name": "观野SPACE",
                "tagline": "运动 · 夜生活 · 社区",
                "description": "回龙观公园综合经营场地。",
                "address": "北京市昌平区回龙观公园",
                "service_phone": "010-88881001",
                "business_hours": "06:00–24:00",
                "cover_image_url": url,
                "banner_image_urls": [url],
                "gallery_image_urls": [url],
            },
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["service_phone"] == "010-88881001"
        assert saved.json()["banner_image_urls"] == [url]

        bad = client.put(
            "/api/v1/site/profile",
            headers=admin_headers,
            json={
                "name": "观野SPACE",
                "cover_image_url": "https://example.com/a.jpg",
                "banner_image_urls": [],
                "gallery_image_urls": [],
            },
        )
        assert bad.status_code == 400
    finally:
        get_settings.cache_clear()

    merchants = client.get("/api/v1/merchants", headers=admin_headers).json()
    gym_id = merchants[0]["id"]
    client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13880000901", "name": "门户会员", "merchant_id": gym_id},
    )
    portal = client.get("/api/v1/member/site", headers=_member_headers(client, "13880000901"))
    assert portal.status_code == 200, portal.text
    data = portal.json()
    assert data["name"] == "观野SPACE"
    assert data["address"]
    assert data["service_phone"] == "010-88881001"
    assert data["cover_image_url"]
