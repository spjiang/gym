"""临访登记与撤销测试。"""

from fastapi.testclient import TestClient


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def test_visit_create_and_revoke(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13900000901", "name": "临访客", "merchant_id": gym_id},
    ).json()
    point = client.post(
        "/api/v1/access-points",
        headers=admin_headers,
        json={"name": "体验门", "merchant_id": gym_id},
    ).json()

    visit = client.post(
        "/api/v1/visits",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "access_point_id": point["id"],
            "hours": 3,
        },
    )
    assert visit.status_code == 200, visit.text
    body = visit.json()
    assert body["status"] == "active"
    assert body["hours"] == 3
    grant_id = body["grant_id"]

    grants = client.get("/api/v1/grants", headers=admin_headers).json()
    grant = next(g for g in grants if g["id"] == grant_id)
    assert grant["revoked"] is False

    listed = client.get(f"/api/v1/visits?merchant_id={gym_id}", headers=admin_headers).json()
    assert any(v["id"] == body["id"] for v in listed)

    revoked = client.post(f"/api/v1/visits/{body['id']}/revoke", headers=admin_headers)
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["status"] == "revoked"

    grants2 = client.get("/api/v1/grants", headers=admin_headers).json()
    grant2 = next(g for g in grants2 if g["id"] == grant_id)
    assert grant2["revoked"] is True

    again = client.post(f"/api/v1/visits/{body['id']}/revoke", headers=admin_headers)
    assert again.status_code == 400
