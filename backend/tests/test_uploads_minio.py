"""上传进 MinIO：公开图、PDF 鉴权、旧路径 302。"""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.object_store import PRIVATE_BUCKET, PUBLIC_BUCKET, object_exists, remove_object
from tests.conftest import fetch_public_url


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc``\x00\x00"
        b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def test_upload_image_returns_public_url_and_legacy_redirects(
    client: TestClient, admin_headers: dict
):
    resp = client.post(
        "/api/v1/uploads",
        headers=admin_headers,
        files={"file": ("a.png", _png_bytes(), "image/png")},
    )
    assert resp.status_code == 200, resp.text
    url = resp.json()["url"]
    filename = resp.json()["filename"]
    base = get_settings().file_public_base_url.rstrip("/")
    assert url == f"{base}/{filename}"
    try:
        fetched = fetch_public_url(url)
        assert fetched.status_code == 200
        assert fetched.content.startswith(b"\x89PNG")
        legacy = client.get(f"/api/v1/files/{filename}", follow_redirects=False)
        assert legacy.status_code == 302
        assert legacy.headers["location"] == url
    finally:
        if object_exists(PUBLIC_BUCKET, filename):
            remove_object(PUBLIC_BUCKET, filename)


def test_pdf_stays_private(client: TestClient, admin_headers: dict):
    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n"
    doc = client.post(
        "/api/v1/uploads",
        headers=admin_headers,
        files={"file": ("a.pdf", pdf, "application/pdf")},
    )
    assert doc.status_code == 200, doc.text
    url = doc.json()["url"]
    filename = doc.json()["filename"]
    assert url == f"/api/v1/files/{filename}"
    try:
        assert client.get(url).status_code == 401
        ok = client.get(url, headers=admin_headers)
        assert ok.status_code == 200
        assert ok.content.startswith(b"%PDF")
    finally:
        if object_exists(PRIVATE_BUCKET, filename):
            remove_object(PRIVATE_BUCKET, filename)
