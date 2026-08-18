"""会员展示头像：会员自助上传、员工代传。"""

from fastapi.testclient import TestClient

from app.core.config import get_settings


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc``\x00\x00"
        b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def _member_headers(client: TestClient, phone: str) -> dict:
    send = client.post("/api/v1/member/auth/otp/send", json={"phone": phone})
    assert send.status_code == 200, send.text
    verify = client.post(
        "/api/v1/member/auth/otp/verify",
        json={"phone": phone, "code": get_settings().member_otp_mock_code},
    )
    assert verify.status_code == 200, verify.text
    return {"Authorization": f"Bearer {verify.json()['access_token']}"}


def test_member_uploads_and_clears_avatar(client: TestClient, admin_headers: dict, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        gym_id = _gym_id(client, admin_headers)
        member = client.post(
            "/api/v1/members",
            headers=admin_headers,
            json={"phone": "13881110001", "name": "头像会员", "merchant_id": gym_id},
        ).json()
        mheaders = _member_headers(client, member["phone"])

        uploaded = client.post(
            "/api/v1/member/avatar",
            headers=mheaders,
            files={"file": ("avatar.png", _png_bytes(), "image/png")},
        )
        assert uploaded.status_code == 200, uploaded.text
        url = uploaded.json()["avatar_url"]
        assert url.startswith("/api/v1/files/")
        fetched = client.get(url)
        assert fetched.status_code == 200
        assert fetched.content.startswith(b"\x89PNG")

        me = client.get("/api/v1/member/me", headers=mheaders).json()
        assert me["avatar_url"] == url

        listed = client.get("/api/v1/members", headers=admin_headers).json()["items"]
        row = next(x for x in listed if x["id"] == member["id"])
        assert row["avatar_url"] == url

        # 小程序常见：Content-Type 不是标准 image/*
        again = client.post(
            "/api/v1/member/avatar",
            headers=mheaders,
            files={"file": ("avatar.bin", _png_bytes(), "application/octet-stream")},
        )
        assert again.status_code == 200, again.text

        pdf = client.post(
            "/api/v1/member/avatar",
            headers=mheaders,
            files={"file": ("x.pdf", b"%PDF-1.4 dummy", "application/pdf")},
        )
        assert pdf.status_code == 400

        cleared = client.delete("/api/v1/member/avatar", headers=mheaders)
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["avatar_url"] is None
    finally:
        get_settings.cache_clear()


def test_staff_uploads_member_avatar(client: TestClient, admin_headers: dict, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        gym_id = _gym_id(client, admin_headers)
        member = client.post(
            "/api/v1/members",
            headers=admin_headers,
            json={"phone": "13881110002", "name": "代传头像", "merchant_id": gym_id},
        ).json()
        uploaded = client.post(
            f"/api/v1/members/{member['id']}/avatar",
            headers=admin_headers,
            files={"file": ("avatar.png", _png_bytes(), "image/png")},
        )
        assert uploaded.status_code == 200, uploaded.text
        assert uploaded.json()["avatar_url"]

        cleared = client.delete(f"/api/v1/members/{member['id']}/avatar", headers=admin_headers)
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["avatar_url"] is None
    finally:
        get_settings.cache_clear()
