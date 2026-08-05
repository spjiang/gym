"""微信支付 APIv3：JSAPI / H5 下单与回调验签（支持 DRY_RUN）。"""

from __future__ import annotations

import base64
import json
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from app.core.errors import AppError
from app.systems.platform.services.payment_settings import EffectivePaymentSettings


@dataclass
class WechatPrepayResult:
    provider_ref: str
    prepay_id: str | None
    jsapi_params: dict | None
    mweb_url: str | None
    dry_run: bool


def _amount_fen(amount: Decimal | str) -> int:
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1")))


def _sign_message(private_key_pem: str, message: str) -> str:
    key = serialization.load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
    signature = key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode("utf-8")


def _authorization(cfg: EffectivePaymentSettings, method: str, path: str, body: str) -> str:
    if not cfg.mch_private_key or not cfg.mch_serial_no or not cfg.mch_id:
        raise AppError("wechat_unconfigured", "缺少商户私钥或证书序列号", status_code=503)
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    message = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body}\n"
    sig = _sign_message(cfg.mch_private_key, message)
    return (
        f'WECHATPAY2-SHA256-RSA2048 mchid="{cfg.mch_id}",'
        f'nonce_str="{nonce}",signature="{sig}",timestamp="{timestamp}",serial_no="{cfg.mch_serial_no}"'
    )


def _jsapi_pay_sign(cfg: EffectivePaymentSettings, *, app_id: str, prepay_id: str) -> dict:
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    package = f"prepay_id={prepay_id}"
    message = f"{app_id}\n{timestamp}\n{nonce}\n{package}\n"
    pay_sign = _sign_message(cfg.mch_private_key, message)
    return {
        "appId": app_id,
        "timeStamp": timestamp,
        "nonceStr": nonce,
        "package": package,
        "signType": "RSA",
        "paySign": pay_sign,
    }


def create_wechat_prepay(
    cfg: EffectivePaymentSettings,
    *,
    out_trade_no: str,
    amount: Decimal | str,
    title: str,
    pay_scene: str,
    openid: str | None,
    client_ip: str | None,
    return_url: str | None,
) -> WechatPrepayResult:
    if cfg.mode != "wechat":
        raise AppError("online_payment_unconfigured", "当前未启用微信支付", status_code=503)

    missing = []
    if not cfg.mch_id:
        missing.append("mch_id")
    if not cfg.api_v3_key:
        missing.append("api_v3_key")
    if pay_scene in ("miniprogram", "jsapi_h5") and not openid:
        raise AppError("openid_required", "JSAPI 支付需要先绑定微信 openid", status_code=400)
    if missing:
        raise AppError("wechat_unconfigured", f"微信支付凭证缺失: {', '.join(missing)}", status_code=503)

    if cfg.dry_run:
        prepay_id = f"dryrun-{out_trade_no}"
        app_id = cfg.mp_app_id if pay_scene == "miniprogram" else (cfg.oa_app_id or cfg.mp_app_id)
        if pay_scene == "mweb":
            return WechatPrepayResult(
                provider_ref=f"wx-dryrun-{out_trade_no}",
                prepay_id=None,
                jsapi_params=None,
                mweb_url=f"{(return_url or cfg.h5_return_url or 'http://localhost:8081').rstrip('/')}/pay/dry-run?out_trade_no={out_trade_no}",
                dry_run=True,
            )
        # dry_run JSAPI：不要求真实私钥也可联调
        jsapi = {
            "appId": app_id or "wx_dry_run",
            "timeStamp": str(int(time.time())),
            "nonceStr": uuid.uuid4().hex,
            "package": f"prepay_id={prepay_id}",
            "signType": "RSA",
            "paySign": "DRY_RUN",
        }
        return WechatPrepayResult(
            provider_ref=f"wx-dryrun-{out_trade_no}",
            prepay_id=prepay_id,
            jsapi_params=jsapi,
            mweb_url=None,
            dry_run=True,
        )

    if not cfg.mch_private_key or not cfg.mch_serial_no:
        raise AppError(
            "wechat_unconfigured",
            "真实支付需配置商户 API 私钥与证书序列号",
            status_code=503,
        )
    if not cfg.notify_url:
        raise AppError("wechat_unconfigured", "请配置支付回调 notify_url", status_code=503)

    description = (title or "订单支付")[:127]
    base_body: dict = {
        "mchid": cfg.mch_id,
        "out_trade_no": out_trade_no,
        "description": description,
        "notify_url": cfg.notify_url,
        "amount": {"total": _amount_fen(amount), "currency": "CNY"},
    }

    if pay_scene == "miniprogram":
        path = "/v3/pay/transactions/jsapi"
        app_id = cfg.mp_app_id
        body = {**base_body, "appid": app_id, "payer": {"openid": openid}}
    elif pay_scene == "jsapi_h5":
        path = "/v3/pay/transactions/jsapi"
        app_id = cfg.oa_app_id or cfg.mp_app_id
        body = {**base_body, "appid": app_id, "payer": {"openid": openid}}
    elif pay_scene == "mweb":
        path = "/v3/pay/transactions/h5"
        app_id = cfg.oa_app_id or cfg.mp_app_id
        body = {
            **base_body,
            "appid": app_id,
            "scene_info": {
                "payer_client_ip": client_ip or "127.0.0.1",
                "h5_info": {"type": "Wap"},
            },
        }
    else:
        raise AppError("validation_error", f"未知 pay_scene: {pay_scene}", status_code=422)

    payload = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    auth = _authorization(cfg, "POST", path, payload)
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(
            f"https://api.mch.weixin.qq.com{path}",
            content=payload.encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": auth,
            },
        )
    if resp.status_code >= 300:
        raise AppError("wechat_api_error", f"微信下单失败: {resp.text[:300]}", status_code=502)
    data = resp.json()
    if pay_scene == "mweb":
        return WechatPrepayResult(
            provider_ref=out_trade_no,
            prepay_id=None,
            jsapi_params=None,
            mweb_url=data.get("h5_url"),
            dry_run=False,
        )
    prepay_id = data.get("prepay_id")
    if not prepay_id:
        raise AppError("wechat_api_error", "微信未返回 prepay_id", status_code=502)
    return WechatPrepayResult(
        provider_ref=out_trade_no,
        prepay_id=prepay_id,
        jsapi_params=_jsapi_pay_sign(cfg, app_id=app_id, prepay_id=prepay_id),
        mweb_url=None,
        dry_run=False,
    )


def exchange_mini_openid(cfg: EffectivePaymentSettings, code: str) -> str:
    """code2session；dry_run / 缺 secret 时返回可测 mock openid。"""
    if cfg.dry_run or not cfg.mp_app_id or not cfg.mp_app_secret:
        return f"mock_mp_{code[-16:] if code else uuid.uuid4().hex}"
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(
            "https://api.weixin.qq.com/sns/jscode2session",
            params={
                "appid": cfg.mp_app_id,
                "secret": cfg.mp_app_secret,
                "js_code": code,
                "grant_type": "authorization_code",
            },
        )
    data = resp.json()
    openid = data.get("openid")
    if not openid:
        raise AppError("wechat_auth_failed", data.get("errmsg") or "换取 openid 失败", status_code=400)
    return openid


def exchange_oa_openid(cfg: EffectivePaymentSettings, code: str) -> str:
    if cfg.dry_run or not cfg.oa_app_id or not cfg.oa_app_secret:
        return f"mock_oa_{code[-16:] if code else uuid.uuid4().hex}"
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(
            "https://api.weixin.qq.com/sns/oauth2/access_token",
            params={
                "appid": cfg.oa_app_id,
                "secret": cfg.oa_app_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
        )
    data = resp.json()
    openid = data.get("openid")
    if not openid:
        raise AppError("wechat_auth_failed", data.get("errmsg") or "网页授权失败", status_code=400)
    return openid


def decrypt_notify_resource(cfg: EffectivePaymentSettings, resource: dict) -> dict:
    """APIv3 通知 resource AEAD 解密。"""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = (cfg.api_v3_key or "").encode("utf-8")
    if len(key) != 32:
        raise AppError("wechat_unconfigured", "APIv3 密钥须为 32 字节，无法解密回调", status_code=503)
    nonce = (resource.get("nonce") or "").encode("utf-8")
    associated = (resource.get("associated_data") or "").encode("utf-8")
    ciphertext_b64 = resource.get("ciphertext") or ""
    if not nonce or not ciphertext_b64:
        raise AppError("wechat_notify_invalid", "回调缺少密文", status_code=400)
    raw = base64.b64decode(ciphertext_b64)
    try:
        plain = AESGCM(key).decrypt(nonce, raw, associated)
    except Exception as exc:  # noqa: BLE001
        raise AppError("wechat_notify_invalid", f"回调解密失败: {exc}", status_code=400) from exc
    return json.loads(plain.decode("utf-8"))


def parse_pay_notify_payload(cfg: EffectivePaymentSettings, payload: dict) -> dict:
    """解析支付成功通知；非 dry_run 必须解密 resource，禁止仅靠明文 out_trade_no。"""
    resource = payload.get("resource")
    if isinstance(resource, dict) and resource.get("ciphertext"):
        data = decrypt_notify_resource(cfg, resource)
        return {
            "out_trade_no": data.get("out_trade_no"),
            "trade_state": data.get("trade_state") or "SUCCESS",
            "amount_fen": ((data.get("amount") or {}).get("total")),
            "raw": data,
        }
    if cfg.dry_run:
        return {
            "out_trade_no": payload.get("out_trade_no"),
            "trade_state": payload.get("trade_state") or "SUCCESS",
            "amount_fen": payload.get("amount_fen"),
            "raw": payload,
        }
    raise AppError(
        "wechat_notify_rejected",
        "非 DRY_RUN 环境禁止明文回调，请使用微信加密通知",
        status_code=400,
    )


def parse_refund_notify_payload(cfg: EffectivePaymentSettings, payload: dict) -> dict:
    resource = payload.get("resource")
    if isinstance(resource, dict) and resource.get("ciphertext"):
        data = decrypt_notify_resource(cfg, resource)
        return {
            "out_refund_no": data.get("out_refund_no"),
            "refund_status": data.get("refund_status") or data.get("status") or "SUCCESS",
            "raw": data,
        }
    if cfg.dry_run:
        return {
            "out_refund_no": payload.get("out_refund_no"),
            "refund_status": payload.get("refund_status") or "SUCCESS",
            "raw": payload,
        }
    raise AppError(
        "wechat_notify_rejected",
        "非 DRY_RUN 环境禁止明文退款回调",
        status_code=400,
    )


@dataclass
class WechatQueryResult:
    trade_state: str  # SUCCESS / NOTPAY / CLOSED / …
    out_trade_no: str
    amount_fen: int | None
    dry_run: bool


def query_wechat_order(cfg: EffectivePaymentSettings, *, out_trade_no: str) -> WechatQueryResult:
    if cfg.dry_run:
        return WechatQueryResult(
            trade_state="NOTPAY",
            out_trade_no=out_trade_no,
            amount_fen=None,
            dry_run=True,
        )
    if not cfg.mch_id or not cfg.mch_private_key or not cfg.mch_serial_no:
        raise AppError("wechat_unconfigured", "查单需商户私钥与证书序列号", status_code=503)
    path_with_query = f"/v3/pay/transactions/out-trade-no/{out_trade_no}?mchid={cfg.mch_id}"
    auth = _authorization(cfg, "GET", path_with_query, "")
    with httpx.Client(timeout=20.0) as client:
        resp = client.get(
            f"https://api.mch.weixin.qq.com/v3/pay/transactions/out-trade-no/{out_trade_no}",
            params={"mchid": cfg.mch_id},
            headers={"Accept": "application/json", "Authorization": auth},
        )
    if resp.status_code >= 300:
        raise AppError("wechat_api_error", f"查单失败: {resp.text[:300]}", status_code=502)
    data = resp.json()
    return WechatQueryResult(
        trade_state=data.get("trade_state") or "NOTPAY",
        out_trade_no=out_trade_no,
        amount_fen=((data.get("amount") or {}).get("total")),
        dry_run=False,
    )


@dataclass
class WechatRefundResult:
    out_refund_no: str
    status: str  # SUCCESS / PROCESSING / …
    provider_ref: str | None
    dry_run: bool


def create_wechat_refund(
    cfg: EffectivePaymentSettings,
    *,
    out_trade_no: str,
    out_refund_no: str,
    refund_amount: Decimal | str,
    total_amount: Decimal | str,
    reason: str | None,
) -> WechatRefundResult:
    if cfg.dry_run:
        return WechatRefundResult(
            out_refund_no=out_refund_no,
            status="SUCCESS",
            provider_ref=f"wx-refund-dryrun-{out_refund_no}",
            dry_run=True,
        )
    if not cfg.notify_url:
        raise AppError("wechat_unconfigured", "退款需配置 notify_url", status_code=503)
    path = "/v3/refund/domestic/refunds"
    body_obj = {
        "out_trade_no": out_trade_no,
        "out_refund_no": out_refund_no,
        "reason": (reason or "退款")[:80],
        "notify_url": cfg.notify_url.replace("/payments/wechat/notify", "/payments/wechat/refund-notify")
        if "/payments/wechat/notify" in (cfg.notify_url or "")
        else f"{cfg.notify_url.rstrip('/')}/refund-notify",
        "amount": {
            "refund": _amount_fen(refund_amount),
            "total": _amount_fen(total_amount),
            "currency": "CNY",
        },
    }
    payload = json.dumps(body_obj, ensure_ascii=False, separators=(",", ":"))
    auth = _authorization(cfg, "POST", path, payload)
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(
            f"https://api.mch.weixin.qq.com{path}",
            content=payload.encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": auth,
            },
        )
    if resp.status_code >= 300:
        raise AppError("wechat_api_error", f"微信退款失败: {resp.text[:300]}", status_code=502)
    data = resp.json()
    return WechatRefundResult(
        out_refund_no=out_refund_no,
        status=data.get("status") or "PROCESSING",
        provider_ref=data.get("refund_id"),
        dry_run=False,
    )
