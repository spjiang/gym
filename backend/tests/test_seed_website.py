"""官网 Demo 种子：主视觉、品牌页与已发布文章。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.seed_website import seed_official_website
from app.systems.platform.models.org import Site


def test_seed_official_website_fills_public_pages(client):
    from app.core import db as db_module

    db = db_module.SessionLocal()
    try:
        site = db.scalars(select(Site)).first()
        assert site is not None
        seed_official_website(db, site=site)
        db.commit()
    finally:
        db.close()

    home = client.get("/api/v1/public/website")
    assert home.status_code == 200, home.text
    body = home.json()
    assert body["home"]["hero_image_url"]
    assert body["home"]["hero_image_url"].endswith(".jpg")
    assert body["home"]["headline"] == "在回龙观，遇见运动与夜色"
    assert body["brands"]["fit"]["cover_image_url"]
    assert len(body["brands"]["bar"]["gallery_image_urls"]) >= 6
    assert body["brands"]["space"]["body"] and len(body["brands"]["space"]["body"]) > 400
    assert "晨曦坤泽" in (body["site"]["footer_note"] or "")
    assert len(body["latest_news"]) == 3

    news = client.get("/api/v1/public/website/articles?channel=news")
    assert news.status_code == 200, news.text
    assert news.json()["total"] >= 6
    jobs = client.get("/api/v1/public/website/articles?channel=jobs")
    assert jobs.json()["total"] >= 4
    partners = client.get("/api/v1/public/website/articles?channel=partners")
    assert partners.json()["total"] >= 3
    detail = client.get(f"/api/v1/public/website/articles/{news.json()['items'][0]['id']}")
    assert detail.status_code == 200
    assert detail.json()["cover_image_url"]


def test_second_seed_does_not_overwrite_staff_edits_or_republish(client, admin_headers):
    from sqlalchemy import select

    from app.core import db as db_module
    from app.seed_website import seed_official_website
    from app.systems.platform.models.org import Site
    from app.systems.platform.models.website import WebsiteArticle

    db = db_module.SessionLocal()
    try:
        site = db.scalars(select(Site)).first()
        assert site is not None
        seed_official_website(db, site=site)
        db.commit()
    finally:
        db.close()

    saved = client.put(
        "/api/v1/website/settings",
        headers=admin_headers,
        json={"home": {"headline": "运营改过的标题"}},
    )
    assert saved.status_code == 200, saved.text

    listed = client.get("/api/v1/website/articles?channel=jobs", headers=admin_headers)
    art_id = listed.json()["items"][0]["id"]
    archived = client.post(f"/api/v1/website/articles/{art_id}/archive", headers=admin_headers)
    assert archived.status_code == 200, archived.text

    db = db_module.SessionLocal()
    try:
        site = db.scalars(select(Site)).first()
        seed_official_website(db, site=site)
        db.commit()
        row = db.get(WebsiteArticle, art_id)
        assert row is not None
        assert row.status == "archived"
    finally:
        db.close()

    home = client.get("/api/v1/public/website")
    assert home.json()["home"]["headline"] == "运营改过的标题"
