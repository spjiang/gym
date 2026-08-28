"""品牌官网：公开只读与后台 CMS。"""

from fastapi.testclient import TestClient


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc``\x00\x00"
        b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_public_website_readable_without_token(client: TestClient):
    r = client.get("/api/v1/public/website")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["site"]["display_name"] == "观野SPACE"
    assert "contact" in body
    assert body["latest_news"] == []


def test_staff_settings_requires_auth(client: TestClient):
    assert client.get("/api/v1/website/settings").status_code == 401


def test_merchant_staff_cannot_write_website(client: TestClient, admin_headers: dict):
    merchants = client.get("/api/v1/merchants", headers=admin_headers).json()
    gym_id = merchants[0]["id"]
    created = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "web_gym_admin",
            "password": "Merchant@123",
            "display_name": "官网越权测",
            "merchant_id": gym_id,
            "role_codes": ["gym_admin"],
        },
    )
    assert created.status_code == 200, created.text
    headers = _login(client, "web_gym_admin", "Merchant@123")
    r = client.put(
        "/api/v1/website/settings",
        headers=headers,
        json={"home": {"headline": "不该成功"}},
    )
    assert r.status_code == 403


def test_draft_hidden_until_publish_then_archive(client: TestClient, admin_headers: dict):
    created = client.post(
        "/api/v1/website/articles",
        headers=admin_headers,
        json={"channel": "news", "title": "开业公告", "summary": "摘要", "body": "正文"},
    )
    assert created.status_code == 200, created.text
    art_id = created.json()["id"]
    assert created.json()["status"] == "draft"

    listed = client.get("/api/v1/public/website/articles?channel=news")
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"] == []
    assert client.get(f"/api/v1/public/website/articles/{art_id}").status_code == 404

    pub = client.post(f"/api/v1/website/articles/{art_id}/publish", headers=admin_headers)
    assert pub.status_code == 200, pub.text
    assert pub.json()["status"] == "published"
    assert pub.json()["published_at"]

    home = client.get("/api/v1/public/website")
    assert any(n["id"] == art_id for n in home.json()["latest_news"])
    detail = client.get(f"/api/v1/public/website/articles/{art_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["title"] == "开业公告"

    arch = client.post(f"/api/v1/website/articles/{art_id}/archive", headers=admin_headers)
    assert arch.status_code == 200, arch.text
    assert client.get(f"/api/v1/public/website/articles/{art_id}").status_code == 404


def test_contact_from_site_profile_hero_does_not_change_cover(
    client: TestClient, admin_headers: dict, tmp_path, monkeypatch
):
    from app.core.config import get_settings

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

        saved_site = client.put(
            "/api/v1/site/profile",
            headers=admin_headers,
            json={
                "name": "观野SPACE",
                "service_phone": "010-88881001",
                "address": "北京市昌平区回龙观公园",
                "business_hours": "06:00–24:00",
                "cover_image_url": url,
                "banner_image_urls": [],
                "gallery_image_urls": [],
            },
        )
        assert saved_site.status_code == 200, saved_site.text
        cover_before = saved_site.json()["cover_image_url"]

        saved_web = client.put(
            "/api/v1/website/settings",
            headers=admin_headers,
            json={"home": {"hero_image_url": url, "headline": "园区开放"}},
        )
        assert saved_web.status_code == 200, saved_web.text

        public = client.get("/api/v1/public/website")
        assert public.status_code == 200, public.text
        assert public.json()["contact"]["service_phone"] == "010-88881001"
        assert public.json()["home"]["headline"] == "园区开放"
        assert public.json()["home"]["hero_image_url"] == url

        site_again = client.get("/api/v1/site/profile", headers=admin_headers)
        assert site_again.json()["cover_image_url"] == cover_before
    finally:
        get_settings.cache_clear()


def test_invalid_image_and_missing_channel(client: TestClient, admin_headers: dict):
    bad = client.put(
        "/api/v1/website/settings",
        headers=admin_headers,
        json={"home": {"hero_image_url": "https://example.com/a.jpg"}},
    )
    assert bad.status_code == 400

    missing = client.get("/api/v1/public/website/articles")
    assert missing.status_code == 400
    invalid = client.get("/api/v1/public/website/articles?channel=blog")
    assert invalid.status_code == 400
