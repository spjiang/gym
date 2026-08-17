"""线上支付 Provider 接口与策略实现。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.systems.platform.services.payment_settings import EffectivePaymentSettings, resolve_payment_settings
from app.systems.platform.services.wechat_pay import create_wechat_prepay


@dataclass
class OnlinePayResult:
    ok: bool
    message: str
    provider_ref: str | None = None
    pay_scene: str | None = None
    jsapi_params: dict | None = None
    mweb_url: str | None = None
    dry_run: bool = False
    immediate_capture: bool = False  # True=管理端代收立即入账


class OnlinePaymentProvider(ABC):
    @abstractmethod
    def create_payment(
        self,
        *,
        order_id: int,
        amount: str,
        title: str,
        out_trade_no: str,
        pay_scene: str = "miniprogram",
        openid: str | None = None,
        client_ip: str | None = None,
        return_url: str | None = None,
        staff_capture: bool = False,
    ) -> OnlinePayResult:
        raise NotImplementedError


class UnconfiguredProvider(OnlinePaymentProvider):
    def create_payment(self, **kwargs) -> OnlinePayResult:
        raise AppError(
            "online_payment_unconfigured",
            "线上支付通道未配置，请在综合经营「京东支付」中启用 mock/jdpay",
            status_code=503,
        )


class MockProvider(OnlinePaymentProvider):
    def create_payment(
        self,
        *,
        order_id: int,
        amount: str,
        title: str,
        out_trade_no: str,
        pay_scene: str = "miniprogram",
        openid: str | None = None,
        client_ip: str | None = None,
        return_url: str | None = None,
        staff_capture: bool = False,
    ) -> OnlinePayResult:
        return OnlinePayResult(
            ok=True,
            message="模拟支付成功",
            provider_ref=f"mock-{order_id}",
            pay_scene=pay_scene,
            immediate_capture=True,
            dry_run=False,
        )


class WechatProvider(OnlinePaymentProvider):
    def __init__(self, cfg: EffectivePaymentSettings):
        self.cfg = cfg

    def _ensure_basic_credentials(self) -> None:
        missing = []
        if not (self.cfg.mp_app_id or self.cfg.oa_app_id):
            missing.append("app_id")
        if not self.cfg.mch_id:
            missing.append("mch_id")
        if not self.cfg.api_v3_key:
            missing.append("api_v3_key")
        if missing:
            raise AppError(
                "wechat_unconfigured",
                f"微信支付凭证缺失: {', '.join(missing)}",
                status_code=503,
            )

    def create_payment(
        self,
        *,
        order_id: int,
        amount: str,
        title: str,
        out_trade_no: str,
        pay_scene: str = "miniprogram",
        openid: str | None = None,
        client_ip: str | None = None,
        return_url: str | None = None,
        staff_capture: bool = False,
    ) -> OnlinePayResult:
        self._ensure_basic_credentials()
        if staff_capture and self.cfg.dry_run:
            return OnlinePayResult(
                ok=True,
                message="微信干跑代收成功",
                provider_ref=f"wx-dryrun-staff-{order_id}",
                pay_scene=pay_scene,
                immediate_capture=True,
                dry_run=True,
            )
        if staff_capture and not self.cfg.dry_run:
            raise AppError(
                "use_offline_or_member_pay",
                "真实微信支付请由会员端调起；管理端请用线下收款或开启 DRY_RUN",
                status_code=400,
            )

        prepay = create_wechat_prepay(
            self.cfg,
            out_trade_no=out_trade_no,
            amount=Decimal(amount),
            title=title,
            pay_scene=pay_scene,
            openid=openid,
            client_ip=client_ip,
            return_url=return_url,
        )
        return OnlinePayResult(
            ok=True,
            message="预下单成功" if not prepay.dry_run else "微信干跑预下单成功",
            provider_ref=prepay.provider_ref,
            pay_scene=pay_scene,
            jsapi_params=prepay.jsapi_params,
            mweb_url=prepay.mweb_url,
            dry_run=prepay.dry_run,
            immediate_capture=False,
        )


def _env_wechat_cfg() -> EffectivePaymentSettings:
    env = get_settings()
    return EffectivePaymentSettings(
        mode="wechat",
        dry_run=bool(env.wechat_dry_run),
        mp_app_id=env.wechat_app_id or "",
        mp_app_secret="",
        oa_app_id=env.wechat_app_id or "",
        oa_app_secret="",
        mch_id=env.wechat_mch_id or "",
        api_v3_key=env.wechat_api_key or "",
        mch_serial_no="",
        mch_private_key="",
        notify_url=env.wechat_notify_url or "",
        h5_return_url=env.member_web_public_url or "",
        source="env",
    )


def get_online_provider(db: Session | None = None, site_id: int | None = None) -> OnlinePaymentProvider:
    if db is not None and site_id is not None:
        cfg = resolve_payment_settings(db, site_id)
        mode = (cfg.mode or "unconfigured").lower()
        if mode == "mock":
            return MockProvider()
        if mode in {"wechat", "jdpay"}:
            return WechatProvider(cfg)
        return UnconfiguredProvider()

    mode = get_settings().online_payment_mode.lower()
    if mode == "mock":
        return MockProvider()
    if mode in {"wechat", "jdpay"}:
        return WechatProvider(_env_wechat_cfg())
    return UnconfiguredProvider()
