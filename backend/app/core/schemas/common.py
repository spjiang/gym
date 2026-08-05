from datetime import datetime
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


class MerchantIn(BaseModel):
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


class MerchantSubsystemsIn(BaseModel):
    subsystem_codes: list[str] = Field(min_length=1)

class StaffCreateIn(BaseModel):
    username: str
    password: str
    display_name: str
    merchant_id: int | None = None
    role_codes: list[str]


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


class MemberLinkIn(BaseModel):
    merchant_id: int


class MemberUpdateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class MemberBrief(BaseModel):
    """列表嵌套用的会员摘要。"""

    id: int
    name: str
    phone: str


class AccessPointIn(BaseModel):
    name: str
    merchant_id: int | None = None
    is_public_area: bool = False


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
    status: str
    pickup_code: str | None = None
    customer_note: str | None = None
    created_at: datetime
    member: MemberBrief | None = None


class OfflinePayIn(BaseModel):
    channel: str = "offline_cash"
    note: str | None = None


class OnlinePayIn(BaseModel):
    pass


class MeOut(BaseModel):
    id: int
    username: str
    display_name: str
    site_id: int
    merchant_id: int | None
    role_codes: list[str]
    permissions: list[str]
