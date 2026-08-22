"""会员档案扩展字段测试。"""

from fastapi.testclient import TestClient

from app.core import db as db_module
from app.systems.platform.models.member import Member
from app.systems.platform.models.promoter import PromoterChannel, PromoterCode, PromoterSubjectType


def test_member_profile_create_and_update(client: TestClient, admin_headers: dict):
    gym_id = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    created = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={
            "phone": "13900001122",
            "name": "档案测试",
            "merchant_id": gym_id,
            "gender": "male",
            "birthday": "1990-05-20",
            "email": "member@example.com",
            "remark": "偏好晚间训练",
            "emergency_contact": "张三",
            "emergency_phone": "13800009999",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["gender"] == "male"
    assert body["birthday"] == "1990-05-20"
    assert body["email"] == "member@example.com"
    assert body["remark"] == "偏好晚间训练"
    assert body["emergency_contact"] == "张三"
    assert body["emergency_phone"] == "13800009999"

    member_id = body["id"]
    updated = client.patch(
        f"/api/v1/members/{member_id}",
        headers=admin_headers,
        json={
            "phone": "13900001123",
            "gender": "other",
            "birthday": "1991-01-02",
            "email": "new@example.com",
            "remark": "已改备注",
            "emergency_contact": "李四",
            "emergency_phone": "13800008888",
        },
    )
    assert updated.status_code == 200, updated.text
    row = updated.json()
    assert row["phone"] == "13900001123"
    assert row["gender"] == "other"
    assert row["birthday"] == "1991-01-02"
    assert row["email"] == "new@example.com"
    assert row["remark"] == "已改备注"

    dup = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13900001123", "name": "冲突", "merchant_id": gym_id},
    )
    assert dup.status_code == 409

    bad_gender = client.patch(
        f"/api/v1/members/{member_id}",
        headers=admin_headers,
        json={"gender": "unknown"},
    )
    assert bad_gender.status_code == 400


def test_member_update_skips_unchanged_inactive_referral_code(client: TestClient, admin_headers: dict):
    """仅改姓名时，未变更的注册推广码（即使已停用）不应再次校验失败。"""
    gym_id = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    created = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13900002200", "name": "推广码保留", "merchant_id": gym_id},
    )
    assert created.status_code == 200, created.text
    member_id = created.json()["id"]

    db = db_module.SessionLocal()
    try:
        code = "INACT01"
        db.add(
            PromoterCode(
                site_id=1,
                merchant_id=None,
                code=code,
                name="已停用注册码",
                subject_type=PromoterSubjectType.CHANNEL.value,
                channel=PromoterChannel.POSTER.value,
                is_active=False,
            )
        )
        member = db.get(Member, member_id)
        assert member is not None
        member.referral_code = code
        db.commit()
    finally:
        db.close()

    updated = client.patch(
        f"/api/v1/members/{member_id}",
        headers=admin_headers,
        json={"name": "推广码保留-已改名", "referral_code": code},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "推广码保留-已改名"
    assert updated.json()["referral_code"] == code


def test_member_update_phone_conflict(client: TestClient, admin_headers: dict):
    """编辑会员时手机号与他人冲突应返回 409。"""
    gym_id = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    a = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13900003301", "name": "会员A", "merchant_id": gym_id},
    ).json()
    client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13900003302", "name": "会员B", "merchant_id": gym_id},
    )
    conflict = client.patch(
        f"/api/v1/members/{a['id']}",
        headers=admin_headers,
        json={"phone": "13900003302"},
    )
    assert conflict.status_code == 409
