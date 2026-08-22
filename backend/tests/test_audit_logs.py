"""操作日志 API 测试。"""

from datetime import date

from fastapi.testclient import TestClient

from app.core import db as db_module
from app.systems.platform.services.audit import write_audit


def test_audit_logs_list_and_filter(client: TestClient, admin_headers: dict):
    db = db_module.SessionLocal()
    try:
        write_audit(
            db,
            action="order.pay_offline",
            target_type="order",
            target_id=9001,
            summary="测试线下收款 ¥100",
            actor_staff_id=1,
            actor_type="staff",
            actor_name="管理员",
            actor_account="admin",
            site_id=1,
            merchant_id=1,
            subsystem_code="platform",
            module="订单管理",
            client_channel="admin_web",
            http_method="POST",
            request_path="/api/v1/orders/9001/pay-offline",
            status="success",
            status_code=200,
        )
        write_audit(
            db,
            action="member.register",
            target_type="member",
            target_id=9002,
            summary="会员自助注册",
            actor_type="member",
            actor_member_id=2,
            actor_name="测试会员",
            actor_account="13800001001",
            site_id=1,
            subsystem_code="member",
            module="会员认证",
            client_channel="member_h5",
            status="success",
        )
        db.commit()
    finally:
        db.close()

    today = date.today().isoformat()
    listed = client.get(
        "/api/v1/audit-logs",
        headers=admin_headers,
        params={"date_from": today, "date_to": today, "page_size": 50},
    )
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] >= 2
    assert any(x["action"] == "order.pay_offline" for x in body["items"])
    assert any(x["client_channel"] == "member_h5" for x in body["items"])

    filtered = client.get(
        "/api/v1/audit-logs",
        headers=admin_headers,
        params={"q": "自助注册", "date_from": today, "date_to": today},
    )
    assert filtered.status_code == 200, filtered.text
    assert all("注册" in x["summary"] for x in filtered.json()["items"])

    by_subsystem = client.get(
        "/api/v1/audit-logs",
        headers=admin_headers,
        params={"subsystem_code": "member", "date_from": today, "date_to": today},
    )
    assert by_subsystem.status_code == 200
    assert all(x["subsystem_code"] == "member" for x in by_subsystem.json()["items"])


def test_audit_logs_requires_permission(client: TestClient, admin_headers: dict):
    gym_id = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "audit_front",
            "password": "Front@123456",
            "display_name": "无日志权限前台",
            "merchant_id": gym_id,
            "role_codes": ["gym_ops"],
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "audit_front", "password": "Front@123456"},
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    denied = client.get("/api/v1/audit-logs", headers=headers)
    assert denied.status_code == 403


def test_auto_audit_middleware_on_staff_create(client: TestClient, admin_headers: dict):
    today = date.today().isoformat()
    before = client.get(
        "/api/v1/audit-logs",
        headers=admin_headers,
        params={"q": "auto_audit_staff", "date_from": today, "date_to": today},
    ).json()["total"]
    gym_id = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    resp = client.post(
        "/api/v1/staff",
        headers={**admin_headers, "X-Client-Channel": "admin_web"},
        json={
            "username": "auto_audit_staff",
            "password": "Front@123456",
            "display_name": "自动审计测试",
            "merchant_id": gym_id,
            "role_codes": ["gym_ops"],
        },
    )
    assert resp.status_code == 200, resp.text
    after = client.get(
        "/api/v1/audit-logs",
        headers=admin_headers,
        params={"q": "auto_audit_staff", "date_from": today, "date_to": today},
    ).json()
    assert after["total"] >= before + 1
    hit = next(x for x in after["items"] if x["action"] == "staff.create")
    assert hit["subsystem_code"] == "platform"
    assert hit["client_channel"] == "admin_web"
    assert hit["module"] == "员工管理"


def test_audit_logs_merchant_isolation(client: TestClient, admin_headers: dict):
    """商户账号仅能查看本商户日志，不可见 merchant_id 为空或其他商户记录。"""
    merchants = client.get("/api/v1/merchants", headers=admin_headers).json()
    gym_id = merchants[0]["id"]
    other_id = merchants[1]["id"] if len(merchants) > 1 else None
    if other_id is None:
        types = client.get("/api/v1/merchant-types", headers=admin_headers).json()
        bar = next(t for t in types if t["code"] == "bar")
        other_id = client.post(
            "/api/v1/merchants",
            headers=admin_headers,
            json={
                "merchant_type_id": bar["id"],
                "name": "审计隔离酒吧",
                "status": "active",
                "subsystem_codes": ["catering"],
            },
        ).json()["id"]

    client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "audit_gym_admin",
            "password": "Audit@123456",
            "display_name": "审计商户管理员",
            "merchant_id": gym_id,
            "role_codes": ["gym_admin"],
        },
    )
    mheaders = {
        "Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'username': 'audit_gym_admin', 'password': 'Audit@123456'}).json()['access_token']}"
    }

    db = db_module.SessionLocal()
    try:
        write_audit(
            db,
            action="audit.scope.gym",
            target_type="test",
            target_id="gym",
            summary="健身房商户日志",
            site_id=1,
            merchant_id=gym_id,
        )
        write_audit(
            db,
            action="audit.scope.other",
            target_type="test",
            target_id="other",
            summary="其他商户日志",
            site_id=1,
            merchant_id=other_id,
        )
        write_audit(
            db,
            action="audit.scope.null",
            target_type="test",
            target_id="null",
            summary="平台级空商户日志",
            site_id=1,
            merchant_id=None,
        )
        db.commit()
    finally:
        db.close()

    today = date.today().isoformat()
    listed = client.get(
        "/api/v1/audit-logs",
        headers=mheaders,
        params={"date_from": today, "date_to": today, "page_size": 100},
    )
    assert listed.status_code == 200, listed.text
    actions = {x["action"] for x in listed.json()["items"]}
    assert "audit.scope.gym" in actions
    assert "audit.scope.other" not in actions
    assert "audit.scope.null" not in actions
