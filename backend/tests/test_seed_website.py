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
