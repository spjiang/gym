"""支付入账幂等、查单、验签与退款快照。"""

from __future__ import annotations

import base64
import json
import time
from decimal import Decimal

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core import db as db_module
from app.core.config import get_settings
from app.systems.platform.models.access import AccessEvent
from app.systems.platform.models.commerce import Order, OrderStatus, Payment, PaymentKind
from app.systems.platform.models.payment_settings import PaymentIntent, RefundIntent
from app.systems.platform.services.wechat_pay import WechatQueryResult


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def _enable_wechat(client: TestClient, headers: dict, *, dry_run: bool, extra: dict | None = None) -> None:
    payload = {
        "mode": "wechat",
        "dry_run": dry_run,
        "mp_app_id": "wx_app",
        "mch_id": "mch1",
        "api_v3_key": "k" * 32,
        **(extra or {}),
    }
    resp = client.put("/api/v1/site/payment-settings", headers=headers, json=payload)
    assert resp.status_code == 200, resp.text


def _member_headers(client: TestClient, phone: str) -> dict:
    client.post("/api/v1/member/auth/otp/send", json={"phone": phone})
    verify = client.post(
        "/api/v1/member/auth/otp/verify",
        json={"phone": phone, "code": get_settings().member_otp_mock_code},
    )
    assert verify.status_code == 200, verify.text
    return {"Authorization": f"Bearer {verify.json()['access_token']}"}


def _bind_mini(client: TestClient, mheaders: dict) -> None:
    bind = client.post("/api/v1/member/auth/wechat/mini/bind", headers=mheaders, json={"code": "c" * 20})
    assert bind.status_code == 200, bind.text


def _retail_order(client: TestClient, headers: dict, gym_id: int, member_id: int, amount: str = "1.00") -> dict:
    order = client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "merchant_id": gym_id,
            "member_id": member_id,
            "order_type": "retail",
            "title": "支付完整性",
            "amount": amount,
        },
    )
    assert order.status_code == 200, order.text
    return order.json()


def _prepay(client: TestClient, mheaders: dict, order_id: int) -> dict:
    resp = client.post(
        f"/api/v1/member/orders/{order_id}/pay/online",
        headers=mheaders,
        json={"pay_scene": "miniprogram"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _session():
    return db_module.SessionLocal()


def _charge_count(order_id: int) -> int:
    db = _session()
    try:
        return int(
            db.scalar(
                select(func.count())
                .select_from(Payment)
                .where(Payment.order_id == order_id, Payment.kind == PaymentKind.CHARGE.value)
            )
            or 0
        )
    finally:
        db.close()


def _intents(order_id: int) -> list[PaymentIntent]:
    db = _session()
    try:
        return list(
            db.scalars(select(PaymentIntent).where(PaymentIntent.order_id == order_id).order_by(PaymentIntent.id)).all()
        )
    finally:
        db.close()


def test_paid_notify_is_idempotent_success(client: TestClient, admin_headers: dict):
    """已支付订单再收到 SUCCESS 回调须 ACK，且不得重复入账。"""
    _enable_wechat(client, admin_headers, dry_run=True)
    gym_id = _gym_id(client, admin_headers)
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13981000001", "name": "幂等回调", "merchant_id": gym_id},
    ).json()
    mheaders = _member_headers(client, "13981000001")
    _bind_mini(client, mheaders)
    order = _retail_order(client, admin_headers, gym_id, member["id"])
    prepay = _prepay(client, mheaders, order["id"])
    confirm = client.post(
        f"/api/v1/member/orders/{order['id']}/pay/dry-run-confirm",
        headers=mheaders,
        json={"out_trade_no": prepay["out_trade_no"]},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["status"] == "paid"
    assert _charge_count(order["id"]) == 1

    again = client.post(
        "/api/v1/payments/wechat/notify",
        json={"out_trade_no": prepay["out_trade_no"], "trade_state": "SUCCESS", "amount_fen": 100},
    )
    assert again.status_code == 200, again.text
    assert again.json()["code"] == "SUCCESS"
    assert _charge_count(order["id"]) == 1


def test_repay_same_second_does_not_collide(client: TestClient, admin_headers: dict, monkeypatch):
    """同一秒重复预下单不得撞 unique out_trade_no。"""
    _enable_wechat(client, admin_headers, dry_run=True)
    gym_id = _gym_id(client, admin_headers)
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13981000002", "name": "撞单号", "merchant_id": gym_id},
    ).json()
    mheaders = _member_headers(client, "13981000002")
    _bind_mini(client, mheaders)
    order = _retail_order(client, admin_headers, gym_id, member["id"])
    monkeypatch.setattr(time, "time", lambda: 1_700_000_000.0)
    first = _prepay(client, mheaders, order["id"])
    second = _prepay(client, mheaders, order["id"])
    assert first["out_trade_no"] != second["out_trade_no"]
    assert second["status"] == "pending"


def test_query_fulfills_older_paid_intent(client: TestClient, admin_headers: dict, monkeypatch):
    """查单须扫描旧 intent：用户付的是被本地关闭的那一笔时仍应入账。"""
    _enable_wechat(client, admin_headers, dry_run=False, extra={"mch_serial_no": "s1", "mch_private_key": "dummy"})
    gym_id = _gym_id(client, admin_headers)
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13981000003", "name": "旧单查单", "merchant_id": gym_id},
    ).json()
    mheaders = _member_headers(client, "13981000003")
    _bind_mini(client, mheaders)
    order = _retail_order(client, admin_headers, gym_id, member["id"])

    # 干跑预下单需要 dry_run；此处改为先 dry_run 造两笔 intent，再伪造查单
    _enable_wechat(client, admin_headers, dry_run=True)
    first = _prepay(client, mheaders, order["id"])
    second = _prepay(client, mheaders, order["id"])
    assert first["out_trade_no"] != second["out_trade_no"]

    def fake_query(cfg, *, out_trade_no: str):
        if out_trade_no == first["out_trade_no"]:
            return WechatQueryResult(trade_state="SUCCESS", out_trade_no=out_trade_no, amount_fen=100, dry_run=False)
        return WechatQueryResult(trade_state="NOTPAY", out_trade_no=out_trade_no, amount_fen=None, dry_run=False)

    monkeypatch.setattr("app.systems.platform.api.payment_notify.query_wechat_order", fake_query)
    monkeypatch.setattr("app.systems.platform.services.wechat_pay.query_wechat_order", fake_query)

    # 关闭 dry_run 以便走微信查单分支
    _enable_wechat(client, admin_headers, dry_run=False, extra={"mch_serial_no": "s1", "mch_private_key": "dummy"})
    queried = client.post(f"/api/v1/member/orders/{order['id']}/pay/query", headers=mheaders)
    assert queried.status_code == 200, queried.text
    assert queried.json()["status"] == "paid"
    assert queried.json()["out_trade_no"] == first["out_trade_no"]
    assert _charge_count(order["id"]) == 1


def test_cancelled_order_notify_acks_without_fulfill(client: TestClient, admin_headers: dict):
    """已取消订单收到付款通知须 ACK，不得履约。"""
    _enable_wechat(client, admin_headers, dry_run=True)
    gym_id = _gym_id(client, admin_headers)
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13981000004", "name": "取消后回调", "merchant_id": gym_id},
    ).json()
    mheaders = _member_headers(client, "13981000004")
    _bind_mini(client, mheaders)
    order = _retail_order(client, admin_headers, gym_id, member["id"])
    prepay = _prepay(client, mheaders, order["id"])

    db = _session()
    try:
        row = db.get(Order, order["id"])
        assert row is not None
        row.status = OrderStatus.CANCELLED.value
        db.commit()
    finally:
        db.close()

    resp = client.post(
        "/api/v1/payments/wechat/notify",
        json={"out_trade_no": prepay["out_trade_no"], "trade_state": "SUCCESS", "amount_fen": 100},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == "SUCCESS"
    db = _session()
    try:
        row = db.get(Order, order["id"])
        assert row is not None
        assert row.status == OrderStatus.CANCELLED.value
    finally:
        db.close()
    assert _charge_count(order["id"]) == 0


def test_staff_dry_run_pay_writes_intent(client: TestClient, admin_headers: dict):
    _enable_wechat(client, admin_headers, dry_run=True)
    gym_id = _gym_id(client, admin_headers)
    order = client.post(
        "/api/v1/orders",
        headers=admin_headers,
        json={"merchant_id": gym_id, "order_type": "retail", "title": "前台代收", "amount": "2.00"},
    ).json()
    paid = client.post(f"/api/v1/orders/{order['id']}/pay/online", headers=admin_headers, json={})
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"
    assert _intents(order["id"])


def test_missing_notify_signature_rejected_when_live(client: TestClient, admin_headers: dict):
    _enable_wechat(client, admin_headers, dry_run=False)
    nonce = "n" * 12
    cipher = AESGCM(b"k" * 32).encrypt(nonce.encode("utf-8"), b'{"out_trade_no":"x"}', b"transaction")
    resp = client.post(
        "/api/v1/payments/wechat/notify",
        json={
            "resource": {
                "algorithm": "AEAD_AES_256_GCM",
                "ciphertext": base64.b64encode(cipher).decode(),
                "nonce": nonce,
                "associated_data": "transaction",
            }
        },
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == "FAIL"
    assert "签名" in resp.json()["message"]


def test_signed_encrypted_notify_fulfills(client: TestClient, admin_headers: dict):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    _enable_wechat(
        client,
        admin_headers,
        dry_run=True,
        extra={"platform_serial_no": "PLATSERIAL", "platform_public_key": public_pem},
    )
    gym_id = _gym_id(client, admin_headers)
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13981000005", "name": "验签入账", "merchant_id": gym_id},
    ).json()
    mheaders = _member_headers(client, "13981000005")
    _bind_mini(client, mheaders)
    order = _retail_order(client, admin_headers, gym_id, member["id"], amount="1.00")
    prepay = _prepay(client, mheaders, order["id"])

    _enable_wechat(
        client,
        admin_headers,
        dry_run=False,
        extra={"platform_serial_no": "PLATSERIAL", "platform_public_key": public_pem},
    )

    nonce = "n" * 12
    plain = json.dumps(
        {"out_trade_no": prepay["out_trade_no"], "trade_state": "SUCCESS", "amount": {"total": 100}},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    cipher = AESGCM(b"k" * 32).encrypt(nonce.encode("utf-8"), plain, b"transaction")
    payload = {
        "resource": {
            "algorithm": "AEAD_AES_256_GCM",
            "ciphertext": base64.b64encode(cipher).decode(),
            "nonce": nonce,
            "associated_data": "transaction",
        }
    }
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    ts = str(int(time.time()))
    hdr_nonce = "wxnonce123456"
    message = f"{ts}\n{hdr_nonce}\n{body}\n".encode("utf-8")
    signature = base64.b64encode(
        private_key.sign(message, padding.PKCS1v15(), hashes.SHA256())
    ).decode()
    resp = client.post(
        "/api/v1/payments/wechat/notify",
        content=body.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Wechatpay-Timestamp": ts,
            "Wechatpay-Nonce": hdr_nonce,
            "Wechatpay-Signature": signature,
            "Wechatpay-Serial": "PLATSERIAL",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["code"] == "SUCCESS"
    db = _session()
    try:
        row = db.get(Order, order["id"])
        assert row is not None
        assert row.status == OrderStatus.PAID.value
    finally:
        db.close()
    assert _charge_count(order["id"]) == 1


def test_refund_success_uses_suggested_snapshot(client: TestClient, admin_headers: dict, monkeypatch):
    """会籍 force 部分退：须用创建时 suggested 快照，避免当下 preview 变小后误作废卡。"""
    gym_id = _gym_id(client, admin_headers)
    point = client.post(
        "/api/v1/access-points",
        headers=admin_headers,
        json={"name": "快照门", "merchant_id": gym_id},
    ).json()
    product = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "快照卡",
            "product_type": "term",
            "price": "100.00",
            "duration_days": 30,
            "access_point_ids": [point["id"]],
            "is_active": True,
        },
    ).json()
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13981000007", "name": "快照会员", "merchant_id": gym_id},
    ).json()
    order = client.post(
        "/api/v1/memberships/purchase",
        headers=admin_headers,
        json={"member_id": member["id"], "product_id": product["id"], "merchant_id": gym_id},
    ).json()
    client.post(
        f"/api/v1/orders/{order['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    db = _session()
    try:
        order_row = db.get(Order, order["id"])
        assert order_row is not None
        intent = RefundIntent(
            site_id=order_row.site_id,
            order_id=order["id"],
            out_refund_no=f"snap-{order['id']}-a",
            amount=Decimal("10.00"),
            suggested_amount=Decimal("100.00"),
            channel="offline_cash",
            status="created",
            force=True,
        )
        db.add(intent)
        db.commit()
        intent_id = intent.id
    finally:
        db.close()

    from app.systems.platform.services import refunds as refunds_mod

    def fake_preview(db, order_row):  # noqa: ARG001
        # 模拟时间流逝后建议额变成 10；若误用当下 preview，10 元会被当成退满建议并作废卡
        return {"suggested_amount": "10.00"}

    monkeypatch.setattr(refunds_mod, "preview_refund", fake_preview)
    db = _session()
    try:
        intent = db.get(RefundIntent, intent_id)
        order_row = db.get(Order, order["id"])
        assert intent is not None and order_row is not None
        refunds_mod.apply_refund_success(db, intent, actor_staff_id=1)
        db.commit()
        db.refresh(order_row)
        assert order_row.status == OrderStatus.PAID.value
        assert Decimal(str(order_row.refunded_amount)) == Decimal("10.00")
    finally:
        db.close()

    cards = client.get(
        f"/api/v1/memberships?merchant_id={gym_id}&member_id={member['id']}",
        headers=admin_headers,
    )
    assert cards.status_code == 200, cards.text
    items = cards.json()["items"]
    assert items
    assert items[0]["status"] != "void"


def test_term_unused_ignores_other_access_point(client: TestClient, admin_headers: dict):
    """期限卡未使用判定只看本卡种门禁点，其它点通行不算已使用。"""
    gym_id = _gym_id(client, admin_headers)
    point_a = client.post(
        "/api/v1/access-points",
        headers=admin_headers,
        json={"name": "本卡门", "merchant_id": gym_id},
    ).json()
    point_b = client.post(
        "/api/v1/access-points",
        headers=admin_headers,
        json={"name": "其它门", "merchant_id": gym_id},
    ).json()
    product = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "未使用判定卡",
            "product_type": "term",
            "price": "100.00",
            "duration_days": 30,
            "access_point_ids": [point_a["id"]],
            "is_active": True,
        },
    ).json()
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13981000006", "name": "未使用会员", "merchant_id": gym_id},
    ).json()
    order = client.post(
        "/api/v1/memberships/purchase",
        headers=admin_headers,
        json={"member_id": member["id"], "product_id": product["id"], "merchant_id": gym_id},
    ).json()
    client.post(
        f"/api/v1/orders/{order['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    device = client.post(
        "/api/v1/devices",
        headers=admin_headers,
        json={"access_point_id": point_b["id"], "device_code": "other-pad", "api_key": "other-key"},
    ).json()
    db = _session()
    try:
        db.add(
            AccessEvent(
                device_id=device["id"],
                access_point_id=point_b["id"],
                member_id=member["id"],
                allowed=True,
                reason="other_point",
            )
        )
        db.commit()
    finally:
        db.close()

    preview = client.get(f"/api/v1/orders/{order['id']}/refund/preview", headers=admin_headers)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["unused"] is True
    assert body["suggested_amount"] == "100.00"
