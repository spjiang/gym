from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginIn(BaseModel):
    username: str
    password: str


class MerchantTypeIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None


class MerchantTypeOut(ORMModel):
    id: int
    code: str
    name: str
    description: str | None


class MerchantTypePatch(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None


class MerchantContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    phone: str = Field(min_length=5, max_length=32)
    title: str | None = Field(default=None, max_length=64)
    kind: str = "other"
    remark: str | None = Field(default=None, max_length=255)
    sort_order: int = 0


class MerchantContactOut(ORMModel):
    id: int
    merchant_id: int
    name: str
    phone: str
    title: str | None
    kind: str
    remark: str | None
    sort_order: int


class MerchantProfileMixin(BaseModel):
    """商户证照与经营档案（创建/编辑共用）。"""

    legal_name: str | None = Field(default=None, max_length=128)
    credit_code: str | None = Field(default=None, max_length=32)
    license_no: str | None = Field(default=None, max_length=64)
    license_image_url: str | None = Field(default=None, max_length=512)
    legal_person: str | None = Field(default=None, max_length=64)
    registered_address: str | None = Field(default=None, max_length=255)
    business_address: str | None = Field(default=None, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=32)
    contact_email: str | None = Field(default=None, max_length=128)
    business_hours: str | None = Field(default=None, max_length=128)
    description: str | None = None
    lease_starts_on: date | None = None
    lease_ends_on: date | None = None
    contacts: list[MerchantContactIn] | None = None


class MerchantIn(MerchantProfileMixin):
    merchant_type_id: int
    name: str = Field(min_length=1, max_length=128)
    status: str = "preparing"
    site_id: int | None = None
    # 关联业态子系统：gym / catering（可多选）；空则按商户类型默认
    subsystem_codes: list[str] | None = None


class MerchantOut(ORMModel):
    id: int
    site_id: int
    merchant_type_id: int
    name: str
    status: str
    created_at: datetime
    subsystem_codes: list[str] = []
    legal_name: str | None = None
    credit_code: str | None = None
    license_no: str | None = None
    license_image_url: str | None = None
    legal_person: str | None = None
    registered_address: str | None = None
    business_address: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    business_hours: str | None = None
    description: str | None = None
    lease_starts_on: date | None = None
    lease_ends_on: date | None = None
    lease_days_total: int | None = None
    lease_days_remaining: int | None = None
    lease_progress: int | None = None
    lease_state: str = "unset"
    contacts: list[MerchantContactOut] = []
    has_license: bool = False
    emergency_contact_count: int = 0


class MerchantPatch(MerchantProfileMixin):
    merchant_type_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=128)
    status: str | None = None
    subsystem_codes: list[str] | None = None


class MerchantSubsystemsIn(BaseModel):
    subsystem_codes: list[str] = Field(min_length=1)

class StaffCreateIn(BaseModel):
    username: str
    password: str = Field(min_length=6, max_length=64)
    display_name: str
    merchant_id: int | None = None
    role_codes: list[str]


class StaffUpdateIn(BaseModel):
    display_name: str | None = None
    password: str | None = Field(default=None, min_length=6, max_length=64)
    merchant_id: int | None = None
    role_codes: list[str] | None = None
    is_active: bool | None = None


class PasswordResetIn(BaseModel):
    """超管重置员工或会员登录密码。"""

    password: str = Field(min_length=6, max_length=64)


class StaffOut(ORMModel):
    id: int
    site_id: int
    merchant_id: int | None
    username: str
    display_name: str
    is_active: bool
    role_codes: list[str] = []


class RoleAssignIn(BaseModel):
    role_codes: list[str]


class MemberCreateIn(BaseModel):
    phone: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    merchant_id: int | None = None
    password: str | None = Field(default=None, min_length=6, max_length=64)


class MemberOut(ORMModel):
    id: int
    site_id: int
    phone: str
    name: str
    face_status: str
    created_at: datetime
    merchant_ids: list[int] = []
    acquisition_source: str = "platform"
    first_merchant_id: int | None = None
    first_merchant_name: str | None = None
    has_password: bool = False


class MemberLinkIn(BaseModel):
    merchant_id: int


class MemberUpdateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class MemberImportErrorOut(BaseModel):
    row: int
    phone: str | None = None
    name: str | None = None
    message: str


class MemberImportOut(BaseModel):
    merchant_id: int
    merchant_name: str
    total_rows: int
    created: int
    linked: int
    skipped: int
    failed: int
    errors: list[MemberImportErrorOut] = []


class MemberBrief(BaseModel):
    """列表嵌套用的会员摘要。"""

    id: int
    name: str
    phone: str


class AccessPointIn(BaseModel):
    name: str
    merchant_id: int | None = None
    is_public_area: bool = False


class AccessPointPatch(BaseModel):
    name: str | None = None
    merchant_id: int | None = None
    is_public_area: bool | None = None


class DevicePatch(BaseModel):
    access_point_id: int | None = None
    device_code: str | None = None
    api_key: str | None = None


class GrantPatch(BaseModel):
    access_point_id: int | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    revoked: bool | None = None


class AccessPointOut(ORMModel):
    id: int
    site_id: int
    merchant_id: int | None
    name: str
    is_public_area: bool


class DeviceRegisterIn(BaseModel):
    access_point_id: int
    device_code: str
    api_key: str


class DeviceOut(ORMModel):
    id: int
    access_point_id: int
    device_code: str
    is_online: bool
    last_seen_at: datetime | None


class GrantIn(BaseModel):
    member_id: int
    access_point_id: int
    merchant_id: int | None = None
    valid_from: datetime
    valid_until: datetime


class GrantOut(ORMModel):
    id: int
    member_id: int
    access_point_id: int
    merchant_id: int | None
    valid_from: datetime
    valid_until: datetime
    revoked: bool


class VerifyIn(BaseModel):
    member_id: int


class VerifyOut(BaseModel):
    allowed: bool
    reason: str | None = None
    event_id: int


class OrderCreateIn(BaseModel):
    merchant_id: int | None = None
    member_id: int | None = None
    order_type: str = "retail"
    title: str
    amount: Decimal


class OrderOut(ORMModel):
    id: int
    site_id: int
    merchant_id: int
    member_id: int | None
    order_type: str
    title: str
    amount: Decimal
    refunded_amount: Decimal = Decimal("0")
    status: str
    pickup_code: str | None = None
    customer_note: str | None = None
    created_at: datetime
    member: MemberBrief | None = None


class OfflinePayIn(BaseModel):
    channel: str = "offline_cash"
    note: str | None = None


class OnlinePayIn(BaseModel):
    note: str | None = None
    pay_scene: str = "miniprogram"
    client_ip: str | None = None
    return_url: str | None = None


class MeOut(BaseModel):
    id: int
    username: str
    display_name: str
    site_id: int
    merchant_id: int | None
    role_codes: list[str]
    permissions: list[str]
