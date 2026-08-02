"""私教课包履约。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models.commerce import Order
from app.models.course import PtOrderLink, PtPackage, PtPackageProduct, PtPackageStatus
from app.services.audit import write_audit


def _now() -> datetime:
    return datetime.now(timezone.utc)


def fulfill_pt_package_order(
    db: Session, order: Order, *, actor_staff_id: int | None = None
) -> PtPackage | None:
    """支付成功后履约私教课包；失败记录 fulfill_error，不抛出以保留支付事实。"""
    if order.order_type != "pt_package":
        return None

    link = db.scalar(select(PtOrderLink).where(PtOrderLink.order_id == order.id))
    if link is None:
        return None
    if link.fulfilled_package_id is not None:
        return db.get(PtPackage, link.fulfilled_package_id)

    try:
        product = db.get(PtPackageProduct, link.product_id)
        if product is None or not product.is_active:
            raise AppError("product_inactive", "课包商品不可用", status_code=400)
        if product.session_count <= 0 or product.valid_days <= 0:
            raise AppError("invalid_product", "课包商品配置无效", status_code=400)

        now = _now()
        pkg = PtPackage(
            merchant_id=order.merchant_id,
            member_id=link.member_id,
            product_id=product.id,
            status=PtPackageStatus.ACTIVE.value,
            remaining_sessions=product.session_count,
            starts_at=now,
            ends_at=now + timedelta(days=product.valid_days),
        )
        db.add(pkg)
        db.flush()
        link.fulfilled_package_id = pkg.id
        link.fulfill_error = None
        write_audit(
            db,
            action="pt.fulfill",
            target_type="pt_package",
            target_id=pkg.id,
            summary=f"履约课包 product={product.id} sessions={product.session_count}",
            actor_staff_id=actor_staff_id,
            site_id=order.site_id,
            merchant_id=order.merchant_id,
        )
        return pkg
    except Exception as exc:  # noqa: BLE001 — 履约失败需落库可追踪
        link.fulfill_error = str(exc)[:250]
        return None


def consume_pt_package(db: Session, package: PtPackage, *, actor_staff_id: int | None = None) -> PtPackage:
    """核销一节私教课，默认扣 1 课时。"""
    now = _now()
    if package.status != PtPackageStatus.ACTIVE.value:
        raise AppError("package_unavailable", "课包不可用", status_code=400)
    if package.ends_at is not None:
        ends = package.ends_at
        if ends.tzinfo is None:
            ends = ends.replace(tzinfo=timezone.utc)
        if ends < now:
            package.status = PtPackageStatus.EXPIRED.value
            raise AppError("package_expired", "课包已过期", status_code=400)
    if package.remaining_sessions <= 0:
        package.status = PtPackageStatus.EXHAUSTED.value
        raise AppError("no_sessions", "剩余课时不足", status_code=400)

    package.remaining_sessions -= 1
    if package.remaining_sessions <= 0:
        package.status = PtPackageStatus.EXHAUSTED.value
        package.remaining_sessions = 0

    write_audit(
        db,
        action="pt.consume",
        target_type="pt_package",
        target_id=package.id,
        summary=f"核销 1 课时，剩余 {package.remaining_sessions}",
        actor_staff_id=actor_staff_id,
        site_id=None,
        merchant_id=package.merchant_id,
    )
    return package
