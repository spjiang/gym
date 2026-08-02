"""导出全部模型，供 Alembic 与应用导入。"""

from app.models.access import AccessDevice, AccessEvent, AccessGrant, AccessPoint
from app.models.audit import AuditLog
from app.models.commerce import Order, Payment
from app.models.identity import Role, StaffRole, StaffUser
from app.models.member import Member, MerchantMember
from app.models.membership import (
    Membership,
    MembershipOrderLink,
    MembershipProduct,
    MembershipProductAccessPoint,
)
from app.models.course import (
    Coach,
    GroupBooking,
    GroupCourse,
    GroupSession,
    PtOrderLink,
    PtPackage,
    PtPackageProduct,
    PtPackageProductCoach,
)
from app.models.retail import (
    ProductCategory,
    RetailOrderItem,
    RetailOrderLink,
    RetailSku,
    StockMovement,
)
from app.models.coupon import CouponTemplate, MemberCoupon, OrderCouponLink
from app.models.otp import MemberOtpChallenge
from app.models.equipment import EquipmentAsset, EquipmentRepairTicket
from app.models.visit import VisitPass
from app.models.notification import Notification
from app.models.org import Merchant, MerchantType, Site

__all__ = [
    "Site",
    "MerchantType",
    "Merchant",
    "StaffUser",
    "Role",
    "StaffRole",
    "Member",
    "MerchantMember",
    "AccessPoint",
    "AccessDevice",
    "AccessGrant",
    "AccessEvent",
    "Order",
    "Payment",
    "AuditLog",
    "MembershipProduct",
    "MembershipProductAccessPoint",
    "Membership",
    "MembershipOrderLink",
    "Coach",
    "PtPackageProduct",
    "PtPackageProductCoach",
    "PtPackage",
    "PtOrderLink",
    "GroupCourse",
    "GroupSession",
    "GroupBooking",
    "ProductCategory",
    "RetailSku",
    "StockMovement",
    "RetailOrderLink",
    "RetailOrderItem",
    "CouponTemplate",
    "MemberCoupon",
    "OrderCouponLink",
    "MemberOtpChallenge",
    "EquipmentAsset",
    "EquipmentRepairTicket",
    "VisitPass",
    "Notification",
]
