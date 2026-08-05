"""模型门面：统一导出各子系统模型，供 Alembic / 测试注册元数据。"""

from app.systems.platform.models.access import AccessDevice, AccessEvent, AccessGrant, AccessPoint
from app.systems.platform.models.audit import AuditLog
from app.systems.platform.models.commerce import Order, Payment
from app.systems.platform.models.identity import Role, StaffRole, StaffUser
from app.systems.platform.models.member import Member, MerchantMember
from app.systems.platform.models.notification import Notification
from app.systems.platform.models.org import Merchant, MerchantSubsystem, MerchantType, Site
from app.systems.platform.models.otp import MemberOtpChallenge
from app.systems.platform.models.rbac_catalog import MenuDef, PermissionDef, RoleMenu, RolePermission, Subsystem
from app.systems.platform.models.visit import VisitPass
from app.systems.gym.models.coupon import CouponTemplate, MemberCoupon, OrderCouponLink
from app.systems.gym.models.course import (
    Coach,
    GroupBooking,
    GroupCourse,
    GroupSession,
    PtOrderLink,
    PtPackage,
    PtPackageProduct,
    PtPackageProductCoach,
)
from app.systems.gym.models.equipment import EquipmentAsset, EquipmentRepairTicket
from app.systems.gym.models.membership import (
    Membership,
    MembershipOrderLink,
    MembershipProduct,
    MembershipProductAccessPoint,
)
from app.systems.gym.models.retail import (
    ProductCategory,
    RetailOrderItem,
    RetailOrderLink,
    RetailSku,
    StockMovement,
)
from app.systems.catering.models.catering import CateringMenuItem, CateringOrderItem

__all__ = [
    "Site",
    "MerchantType",
    "Merchant",
    "MerchantSubsystem",
    "CateringMenuItem",
    "CateringOrderItem",
    "Subsystem",
    "PermissionDef",
    "MenuDef",
    "RolePermission",
    "RoleMenu",
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
