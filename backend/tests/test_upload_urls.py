"""公开图 URL 规则与旧路径改写。"""

from app.core.config import get_settings
from app.core.upload_urls import is_stored_image_url, rewrite_legacy_image_text, rewrite_stored_value


def test_legacy_relative_image_is_accepted():
    name = f"{'a' * 32}.jpg"
    assert is_stored_image_url(f"/api/v1/files/{name}")


def test_current_public_url_is_accepted():
    get_settings.cache_clear()
    name = f"{'b' * 32}.png"
    base = get_settings().file_public_base_url.rstrip("/")
    assert is_stored_image_url(f"{base}/{name}")


def test_foreign_and_pdf_are_rejected_as_images():
    assert not is_stored_image_url("https://example.com/a.jpg")
    assert not is_stored_image_url(f"/api/v1/files/{'c' * 32}.pdf")


def test_rewrite_legacy_in_text_and_json_leaves_pdf():
    get_settings.cache_clear()
    img = f"{'d' * 32}.webp"
    pdf = f"{'e' * 32}.pdf"
    legacy = f"/api/v1/files/{img}"
    base = get_settings().file_public_base_url.rstrip("/")
    assert rewrite_legacy_image_text(legacy) == f"{base}/{img}"
    assert rewrite_legacy_image_text(f"封面 ![]({legacy})") == f"封面 ![]({base}/{img})"
    assert rewrite_legacy_image_text(f"/api/v1/files/{pdf}") == f"/api/v1/files/{pdf}"
    payload = {"cover": legacy, "files": [legacy], "note": f"/api/v1/files/{pdf}"}
    assert rewrite_stored_value(payload) == {
        "cover": f"{base}/{img}",
        "files": [f"{base}/{img}"],
        "note": f"/api/v1/files/{pdf}",
    }


def test_rewrite_file_domain_and_media_path_to_current_base():
    get_settings.cache_clear()
    name = f"{'a' * 32}.jpg"
    base = get_settings().file_public_base_url.rstrip("/")
    assert is_stored_image_url(f"/media/{name}")
    assert is_stored_image_url(f"https://file.guanyespace.com/{name}")
    assert is_stored_image_url(f"https://file.guanyespace.com/public/{name}")
    assert rewrite_legacy_image_text(f"https://file.guanyespace.com/{name}") == f"{base}/{name}"
    assert rewrite_legacy_image_text(f"https://file.guanyespace.com/public/{name}") == f"{base}/{name}"
    assert rewrite_legacy_image_text(f"/media/{name}") == f"{base}/{name}"
