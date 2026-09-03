"""FastAPI 应用入口。"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.audit_middleware import AuditMiddleware
from app.core.config import get_settings
from app.core.health import collect_readiness
from app.core.member_web_url import is_local_member_web_url
from app.core.errors import register_exception_handlers
from app.core.request_id_middleware import RequestIdMiddleware
from app.systems.catering.api import catering, member_catering
from app.systems.gym.api import (
    activity,
    coach_self,
    commission,
    coupons,
    course,
    equipment,
    member_activity,
    membership,
    pt_appointment,
    retail,
    sales,
)
from app.systems.platform.api import (
    access,
    agreements,
    audit_logs,
    ai_analysis,
    auth,
    commerce,
    device,
    member_auth,
    member_portal,
    member_promotion,
    members,
    notifications,
    org,
    ops,
    payment_notify,
    payment_reconcile,
    payment_settings,
    payouts,
    promoters,
    promotion,
    reports,
    public_website,
    site_profile,
    sms,
    website,
    staff,
    uploads,
    visits,
)
from app.systems.platform.api import navigation as platform_navigation
from app.systems.platform.api import rbac as platform_rbac
from app.core.file_migrate import migrate_local_uploads
from app.core.object_store import ensure_buckets
from app.systems.platform.services.sync_queue import ensure_worker


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.app_env == "production" and is_local_member_web_url():
        logging.getLogger(__name__).warning(
            "MEMBER_WEB_PUBLIC_URL 仍为本地地址，推广码/获客/桌码等外链将不可用于线上"
        )
    ensure_buckets()
    migrate_local_uploads()
    ensure_worker()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Gym Platform API", version="0.1.0", lifespan=lifespan)
    register_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(AuditMiddleware)
    app.add_middleware(RequestIdMiddleware)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/.well-known/acme-challenge/{token}")
    def acme_challenge(token: str):
        """供 Let's Encrypt HTTP-01 校验；申请 api 源站证书时使用。"""
        import re
        from pathlib import Path

        from fastapi.responses import PlainTextResponse

        if not re.fullmatch(r"[A-Za-z0-9_-]+", token):
            return PlainTextResponse("bad token", status_code=400)
        path = Path(settings.upload_dir) / ".well-known" / "acme-challenge" / token
        if not path.is_file():
            return PlainTextResponse("not found", status_code=404)
        return PlainTextResponse(path.read_text(encoding="utf-8").strip())

    @app.get("/ready")
    def ready():
        from fastapi.responses import JSONResponse

        data = collect_readiness()
        status_code = 200 if data["status"] != "fail" else 503
        return JSONResponse(
            status_code=status_code,
            content={"status": data["status"], "checks": data["checks"]},
        )

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(member_auth.router, prefix="/api/v1")
    app.include_router(member_portal.router, prefix="/api/v1")
    app.include_router(member_activity.router, prefix="/api/v1")
    app.include_router(org.router, prefix="/api/v1")
    app.include_router(staff.router, prefix="/api/v1")
    app.include_router(members.router, prefix="/api/v1")
    app.include_router(access.router, prefix="/api/v1")
    app.include_router(device.router, prefix="/api/v1")
    app.include_router(commerce.router, prefix="/api/v1")
    app.include_router(catering.router, prefix="/api/v1")
    app.include_router(member_catering.router, prefix="/api/v1")
    app.include_router(reports.router, prefix="/api/v1")
    app.include_router(membership.router, prefix="/api/v1")
    app.include_router(course.router, prefix="/api/v1")
    app.include_router(retail.router, prefix="/api/v1")
    app.include_router(coupons.router, prefix="/api/v1")
    app.include_router(equipment.router, prefix="/api/v1")
    app.include_router(activity.router, prefix="/api/v1")
    app.include_router(pt_appointment.router, prefix="/api/v1")
    app.include_router(commission.router, prefix="/api/v1")
    app.include_router(sales.router, prefix="/api/v1")
    app.include_router(promoters.public_router, prefix="/api/v1")
    app.include_router(promotion.router, prefix="/api/v1")
    app.include_router(payouts.router, prefix="/api/v1")
    app.include_router(coach_self.router, prefix="/api/v1")
    app.include_router(member_promotion.router, prefix="/api/v1")
    app.include_router(visits.router, prefix="/api/v1")
    app.include_router(notifications.router, prefix="/api/v1")
    app.include_router(notifications.member_router, prefix="/api/v1")
    app.include_router(platform_rbac.router, prefix="/api/v1")
    app.include_router(platform_navigation.router, prefix="/api/v1")
    app.include_router(payment_settings.router, prefix="/api/v1")
    app.include_router(site_profile.router, prefix="/api/v1")
    app.include_router(website.router, prefix="/api/v1")
    app.include_router(public_website.router, prefix="/api/v1")
    app.include_router(agreements.router, prefix="/api/v1")
    app.include_router(sms.router, prefix="/api/v1")
    app.include_router(uploads.router, prefix="/api/v1")
    app.include_router(payment_notify.router, prefix="/api/v1")
    app.include_router(payment_reconcile.router, prefix="/api/v1")
    app.include_router(audit_logs.router, prefix="/api/v1")
    app.include_router(ops.router, prefix="/api/v1")
    app.include_router(ai_analysis.router, prefix="/api/v1")
    return app


app = create_app()
