"""FastAPI 应用入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    access,
    auth,
    catering,
    commerce,
    course,
    coupons,
    device,
    equipment,
    member_auth,
    member_portal,
    members,
    membership,
    notifications,
    org,
    reports,
    retail,
    staff,
    visits,
)
from app.config import get_settings
from app.errors import register_exception_handlers
from app.services.sync_queue import ensure_worker


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
    app.include_router(reports.router, prefix="/api/v1")
    app.include_router(membership.router, prefix="/api/v1")
    app.include_router(course.router, prefix="/api/v1")
    app.include_router(retail.router, prefix="/api/v1")
    app.include_router(coupons.router, prefix="/api/v1")
    app.include_router(equipment.router, prefix="/api/v1")
    app.include_router(visits.router, prefix="/api/v1")
    app.include_router(notifications.router, prefix="/api/v1")
    app.include_router(notifications.member_router, prefix="/api/v1")
    return app


app = create_app()
