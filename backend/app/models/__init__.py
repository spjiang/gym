"""模型门面：统一导出各子系统模型，供 Alembic / 测试注册元数据。"""

from app.systems.platform.models.access import AccessDevice, AccessEvent, AccessGrant, AccessPoint
from app.systems.platform.models.agreement import LegalAgreement
from app.systems.platform.models.audit import AuditLog
from app.systems.platform.models.commerce import Order, Payment
from app.systems.platform.models.identity import Role, StaffRole, StaffUser
from app.systems.platform.models.member import Member, MerchantMember
from app.systems.platform.models.notification import Notification
from app.systems.platform.models.org import Merchant, MerchantContact, MerchantSubsystem, MerchantType, Site
from app.systems.platform.models.payment_settings import (
    MemberWechatBinding,
    PaymentIntent,
    RefundIntent,
    SitePaymentSettings,
)
from app.systems.platform.models.payout import Payout, PayoutItem
from app.systems.platform.models.promoter import PromoterCode
from app.systems.platform.models.rebate import (
    MemberRebateAccount,
    MemberRebateLedger,
    SitePromotionSettings,
)
from app.systems.platform.models.rbac_catalog import MenuDef, PermissionDef, RoleMenu, RolePermission, Subsystem
from app.systems.platform.models.sms import SiteSmsSettings, SmsTemplate
from app.systems.platform.models.visit import VisitPass
from app.systems.gym.models.activity import Activity, ActivityRegistration
from app.systems.gym.models.appointment import PtAppointment
from app.systems.gym.models.commission import CommissionRecord, CommissionRule
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
    MembershipConsumption,
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
from app.systems.catering.models.catering import (
    CateringMenuCategory,
    CateringMenuItem,
    CateringOrderItem,
    CateringTable,
)

__all__ = [
    "Site",
    "MerchantType",
    "Merchant",
    "MerchantContact",
    "MerchantSubsystem",
    "CateringMenuCategory",
    "CateringMenuItem",
    "CateringOrderItem",
    "CateringTable",
    "Subsystem",
    "PermissionDef",
    "MenuDef",
    "RolePermission",
    "RoleMenu",
    "LegalAgreement",
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
    "MembershipConsumption",
    "MembershipOrderLink",
    "Coach",
    "PtPackageProduct",
    "PtPackageProductCoach",
    "PtPackage",
    "PtOrderLink",
    "GroupCourse",
    "GroupSession",
    "GroupBooking",
    "PtAppointment",
    "Activity",
    "ActivityRegistration",
    "CommissionRule",
    "CommissionRecord",
    "PromoterCode",
    "SitePromotionSettings",
    "MemberRebateAccount",
    "MemberRebateLedger",
    "Payout",
    "PayoutItem",
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
    "SiteSmsSettings",
    "SmsTemplate",
    "Notification",
    "SitePaymentSettings",
    "MemberWechatBinding",
    "PaymentIntent",
    "RefundIntent",
]
