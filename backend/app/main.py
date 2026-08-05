"""FastAPI 应用入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.systems.catering.api import catering, member_catering
from app.systems.gym.api import coupons, course, equipment, membership, retail
from app.systems.platform.api import (
    access,
    auth,
    commerce,
    device,
    member_auth,
    member_portal,
    members,
    notifications,
    org,
    payment_notify,
    payment_reconcile,
    payment_settings,
    reports,
    staff,
    visits,
)
from app.systems.platform.api import navigation as platform_navigation
from app.systems.platform.api import rbac as platform_rbac
from app.systems.platform.services.sync_queue import ensure_worker


@asynccontextmanager
async def lifespan(_: FastAPI):
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
    )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(member_auth.router, prefix="/api/v1")
    app.include_router(member_portal.router, prefix="/api/v1")
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
    app.include_router(visits.router, prefix="/api/v1")
    app.include_router(notifications.router, prefix="/api/v1")
    app.include_router(notifications.member_router, prefix="/api/v1")
    app.include_router(platform_rbac.router, prefix="/api/v1")
    app.include_router(platform_navigation.router, prefix="/api/v1")
    app.include_router(payment_settings.router, prefix="/api/v1")
    app.include_router(payment_notify.router, prefix="/api/v1")
    app.include_router(payment_reconcile.router, prefix="/api/v1")
    return app


app = create_app()
