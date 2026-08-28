"""官网 CMS 校验、默认值与组装。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.upload_urls import is_stored_image_url
from app.systems.platform.models.org import Site
from app.systems.platform.models.website import WebsiteArticle, WebsiteSettings

CHANNELS = ("news", "jobs", "partners")
STATUSES = ("draft", "published", "archived")
BRAND_KEYS = ("space", "fit", "bar")
DEFAULT_BRAND_TITLES = {"space": "观野SPACE", "fit": "观野FIT", "bar": "观野BAR"}
DEFAULT_DISPLAY_NAME = "观野SPACE"
DEFAULT_SUBHEADLINE = "SPORTS · EVENTS · COMMUNITY"
MAX_GALLERY = 9
LATEST_NEWS = 3


def assert_channel(channel: str | None) -> str:
    value = (channel or "").strip()
    if value not in CHANNELS:
        raise AppError("invalid_channel", "请指定 news / jobs / partners", status_code=400)
    return value


def _blank(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def clip_text(value: str | None, *, limit: int) -> str | None:
    text = _blank(value)
    if text is None:
        return None
    return text[:limit]


def normalize_image(url: str | None, *, field: str) -> str | None:
    text = _blank(url)
    if text is None:
        return None
    if not is_stored_image_url(text):
        raise AppError("invalid_image", f"{field}地址无效，请通过系统上传", status_code=400)
    return text


def normalize_images(urls: list[str] | None, *, field: str, limit: int) -> list[str]:
    out: list[str] = []
    for raw in urls or []:
        url = normalize_image(raw, field=field)
        if url and url not in out:
            out.append(url)
    if len(out) > limit:
        raise AppError("too_many_images", f"{field}最多 {limit} 张", status_code=400)
    return out


def first_site(db: Session) -> Site | None:
    return db.scalar(select(Site).order_by(Site.id.asc()))


def get_settings_row(db: Session, site_id: int) -> WebsiteSettings | None:
    return db.scalar(select(WebsiteSettings).where(WebsiteSettings.site_id == site_id))


def get_or_create_settings(db: Session, site_id: int, *, staff_id: int | None) -> WebsiteSettings:
    row = get_settings_row(db, site_id)
    if row is not None:
        return row
    row = WebsiteSettings(
        site_id=site_id,
        site_json={},
        home_json={},
        brands_json={},
        updated_by_staff_id=staff_id,
    )
    db.add(row)
    db.flush()
    return row


def contact_from_site(site: Site | None) -> dict[str, str | None]:
    if site is None:
        return {"address": None, "service_phone": None, "business_hours": None}
    return {
        "address": site.address,
        "service_phone": site.service_phone,
        "business_hours": site.business_hours,
    }


def normalize_site_json(raw: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(raw or {})
    logo = normalize_image(data.get("logo_url"), field="Logo")
    return {
        "display_name": clip_text(data.get("display_name"), limit=128),
        "seo_title": clip_text(data.get("seo_title"), limit=128),
        "seo_description": clip_text(data.get("seo_description"), limit=255),
        "logo_url": logo,
        "member_web_url": clip_text(data.get("member_web_url"), limit=255),
        "miniprogram_hint": clip_text(data.get("miniprogram_hint"), limit=128),
        "footer_note": clip_text(data.get("footer_note"), limit=255),
        "icp_beian": clip_text(data.get("icp_beian"), limit=64),
    }


def normalize_home_json(raw: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(raw or {})
    out: dict[str, Any] = {
        "hero_image_url": normalize_image(data.get("hero_image_url"), field="主视觉"),
        "headline": clip_text(data.get("headline"), limit=128),
        "subheadline": clip_text(data.get("subheadline"), limit=255),
    }
    for key in ("show_space", "show_fit", "show_bar"):
        if key in data:
            out[key] = bool(data[key])
    return out


def normalize_brand_block(raw: dict[str, Any] | None, *, key: str) -> dict[str, Any]:
    data = dict(raw or {})
    cta_label = clip_text(data.get("cta_label"), limit=32)
    cta_url = clip_text(data.get("cta_url"), limit=255)
    return {
        "title": clip_text(data.get("title"), limit=64),
        "cover_image_url": normalize_image(data.get("cover_image_url"), field=f"{key}封面"),
        "body": (data.get("body") or "").strip() or None,
        "gallery_image_urls": normalize_images(data.get("gallery_image_urls"), field=f"{key}图集", limit=MAX_GALLERY),
        "cta_label": cta_label,
        "cta_url": cta_url,
    }


def normalize_brands_json(raw: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(raw or {})
    return {key: normalize_brand_block(data.get(key), key=key) for key in BRAND_KEYS}


def merge_json(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing or {})
    for key, value in incoming.items():
        if value is None and key not in ("show_space", "show_fit", "show_bar"):
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged


def public_site(site_json: dict[str, Any] | None) -> dict[str, Any]:
    data = site_json or {}
    display = _blank(data.get("display_name")) or DEFAULT_DISPLAY_NAME
    member_url = _blank(data.get("member_web_url")) or _blank(get_settings().member_web_public_url)
    return {
        "display_name": display,
        "seo_title": _blank(data.get("seo_title")) or display,
        "seo_description": data.get("seo_description"),
        "logo_url": data.get("logo_url"),
        "member_web_url": member_url,
        "miniprogram_hint": data.get("miniprogram_hint"),
        "footer_note": data.get("footer_note"),
        "icp_beian": data.get("icp_beian"),
    }


def public_home(home_json: dict[str, Any] | None) -> dict[str, Any]:
    data = home_json or {}
    return {
        "hero_image_url": data.get("hero_image_url"),
        "headline": data.get("headline"),
        "subheadline": _blank(data.get("subheadline")) or DEFAULT_SUBHEADLINE,
        "show_space": data.get("show_space", True) is not False,
        "show_fit": data.get("show_fit", True) is not False,
        "show_bar": data.get("show_bar", True) is not False,
    }


def public_brand(key: str, block: dict[str, Any] | None) -> dict[str, Any]:
    data = block or {}
    cta_label = _blank(data.get("cta_label"))
    cta_url = _blank(data.get("cta_url"))
    return {
        "key": key,
        "title": _blank(data.get("title")) or DEFAULT_BRAND_TITLES[key],
        "cover_image_url": data.get("cover_image_url"),
        "body": data.get("body"),
        "gallery_image_urls": list(data.get("gallery_image_urls") or []),
        "cta_label": cta_label,
        "cta_url": cta_url if cta_label and cta_url else None,
    }


def public_brands(brands_json: dict[str, Any] | None) -> dict[str, Any]:
    data = brands_json or {}
    return {key: public_brand(key, data.get(key)) for key in BRAND_KEYS}


def staff_settings_payload(row: WebsiteSettings | None, site: Site | None) -> dict[str, Any]:
    brands = (row.brands_json if row else None) or {}
    return {
        "site": dict(row.site_json or {}) if row else {},
        "home": dict(row.home_json or {}) if row else {},
        "brands": {key: dict(brands.get(key) or {}) for key in BRAND_KEYS},
        "contact": contact_from_site(site),
    }


def article_public_brief(row: WebsiteArticle) -> dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "summary": row.summary,
        "cover_image_url": row.cover_image_url,
        "published_at": row.published_at,
        "channel": row.channel,
    }


def article_out(row: WebsiteArticle) -> dict[str, Any]:
    return {
        "id": row.id,
        "site_id": row.site_id,
        "channel": row.channel,
        "title": row.title,
        "summary": row.summary,
        "cover_image_url": row.cover_image_url,
        "body": row.body or "",
        "contact_hint": row.contact_hint,
        "status": row.status,
        "published_at": row.published_at,
        "sort_order": row.sort_order,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def load_latest_news(db: Session, site_id: int, *, limit: int = LATEST_NEWS) -> list[WebsiteArticle]:
    stmt = (
        select(WebsiteArticle)
        .where(
            WebsiteArticle.site_id == site_id,
            WebsiteArticle.channel == "news",
            WebsiteArticle.status == "published",
        )
        .order_by(
            WebsiteArticle.sort_order.desc(),
            WebsiteArticle.published_at.desc(),
            WebsiteArticle.id.desc(),
        )
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def mark_published(row: WebsiteArticle) -> None:
    row.status = "published"
    if row.published_at is None:
        row.published_at = datetime.now(timezone.utc)


def require_site_wide(ctx) -> None:
    if not ctx.is_site_wide:
        raise AppError("forbidden", "仅场地级账号可维护官网", status_code=403)
