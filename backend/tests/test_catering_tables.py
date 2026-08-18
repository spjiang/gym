"""餐饮桌号与点餐码。"""

from fastapi.testclient import TestClient

from app.core.config import get_settings


def _member_login(client: TestClient, phone: str) -> dict:
    assert client.post("/api/v1/member/auth/otp/send", json={"phone": phone}).status_code == 200
    code = get_settings().member_otp_mock_code
    verify = client.post("/api/v1/member/auth/otp/verify", json={"phone": phone, "code": code})
    assert verify.status_code == 200, verify.text
    return {"Authorization": f"Bearer {verify.json()['access_token']}"}


def _bar_id(client: TestClient, admin_headers: dict) -> int:
    merchants = client.get("/api/v1/merchants", headers=admin_headers).json()
    bar = next(m for m in merchants if "catering" in (m.get("subsystem_codes") or []))
    return bar["id"]


def test_catering_table_qr_and_member_resolve(client: TestClient, admin_headers: dict):
    bar_id = _bar_id(client, admin_headers)
    created = client.post(
        "/api/v1/catering/tables",
        headers=admin_headers,
        json={"merchant_id": bar_id, "name": "A9", "sort_order": 90},
    )
    assert created.status_code == 200, created.text
    table = created.json()
    assert table["name"] == "A9"
    assert table["code"]
    assert f"/m/{bar_id}/catering?table={table['code']}" in table["order_url"]

    dup = client.post(
        "/api/v1/catering/tables",
        headers=admin_headers,
        json={"merchant_id": bar_id, "name": "A9"},
    )
    assert dup.status_code == 409

    listed = client.get("/api/v1/catering/tables", headers=admin_headers, params={"merchant_id": bar_id})
    assert listed.status_code == 200
    body = listed.json()
    assert set(body.keys()) >= {"items", "total", "page", "page_size"}
    assert any(row["id"] == table["id"] for row in body["items"])

    hit = client.get(
        "/api/v1/catering/tables",
        headers=admin_headers,
        params={"merchant_id": bar_id, "q": "A9"},
    ).json()
    assert hit["total"] >= 1
    assert any(row["id"] == table["id"] for row in hit["items"])

    paged = client.get(
        "/api/v1/catering/tables",
        headers=admin_headers,
        params={"merchant_id": bar_id, "page": 1, "page_size": 1},
    ).json()
    assert paged["page"] == 1
    assert paged["page_size"] == 1
    assert paged["total"] >= 1
    assert len(paged["items"]) == 1

    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13880000901", "name": "扫码客", "merchant_id": bar_id},
    ).json()
    mheaders = _member_login(client, member["phone"])
    resolved = client.get(
        "/api/v1/member/catering/table",
        headers=mheaders,
        params={"merchant_id": bar_id, "code": table["code"].lower()},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["name"] == "A9"

    paused = client.patch(
        f"/api/v1/catering/tables/{table['id']}",
        headers=admin_headers,
        params={"merchant_id": bar_id},
        json={"is_active": False},
    )
    assert paused.status_code == 200
    blocked = client.get(
        "/api/v1/member/catering/table",
        headers=mheaders,
        params={"merchant_id": bar_id, "code": table["code"]},
    )
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "table_inactive"
