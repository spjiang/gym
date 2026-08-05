"""线上支付 Provider 接口与策略实现。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.config import get_settings
from app.core.errors import AppError


@dataclass
class OnlinePayResult:
    ok: bool
    message: str
    provider_ref: str | None = None


class OnlinePaymentProvider(ABC):
    @abstractmethod
    def create_payment(self, *, order_id: int, amount: str, title: str) -> OnlinePayResult:
        raise NotImplementedError


class UnconfiguredProvider(OnlinePaymentProvider):
    def create_payment(self, *, order_id: int, amount: str, title: str) -> OnlinePayResult:
        raise AppError(
            "online_payment_unconfigured",
            "线上支付通道未配置，请使用线下登记或切换 ONLINE_PAYMENT_MODE=mock/wechat",
            status_code=503,
        )


class MockProvider(OnlinePaymentProvider):
    def create_payment(self, *, order_id: int, amount: str, title: str) -> OnlinePayResult:
        return OnlinePayResult(ok=True, message="模拟支付成功", provider_ref=f"mock-{order_id}")


class WechatProvider(OnlinePaymentProvider):
    """微信支付适配：校验商户凭证；DRY_RUN 下返回可测成功，真实联调需关闭 DRY_RUN 并接 API。"""

    def create_payment(self, *, order_id: int, amount: str, title: str) -> OnlinePayResult:
        s = get_settings()
        missing = [
            name
            for name, val in (
                ("WECHAT_APP_ID", s.wechat_app_id),
                ("WECHAT_MCH_ID", s.wechat_mch_id),
                ("WECHAT_API_KEY", s.wechat_api_key),
            )
            if not val
        ]
        if missing:
            raise AppError(
                "wechat_unconfigured",
                f"微信支付凭证缺失: {', '.join(missing)}",
                status_code=503,
            )
        if s.wechat_dry_run:
            return OnlinePayResult(
                ok=True,
                message="微信干跑成功（未调用真实下单接口）",
                provider_ref=f"wx-dryrun-{order_id}",
            )
        # 真实联调入口：此处应调用微信统一下单；当前仓库默认要求 DRY_RUN，避免误打生产
        raise AppError(
            "wechat_live_disabled",
            "已配置微信凭证但 WECHAT_DRY_RUN=false 时需接入正式下单 SDK；请先保持 DRY_RUN=true 或完成 SDK 对接",
            status_code=501,
        )


def get_online_provider() -> OnlinePaymentProvider:
    mode = get_settings().online_payment_mode.lower()
    if mode == "mock":
        return MockProvider()
    if mode == "wechat":
        return WechatProvider()
    return UnconfiguredProvider()
