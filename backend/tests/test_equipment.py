"""器材台账与报修测试。"""

from fastapi.testclient import TestClient


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def test_equipment_lifecycle(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    asset = client.post(
        "/api/v1/equipment/assets",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "跑步机 A1",
            "category": "cardio",
            "asset_code": "EQ-A1",
            "area": "有氧区",
            "status": "in_use",
        },
    )
    assert asset.status_code == 200, asset.text
    asset_id = asset.json()["id"]

    dup = client.post(
        "/api/v1/equipment/assets",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "重复",
            "category": "cardio",
            "asset_code": "EQ-A1",
        },
    )
    assert dup.status_code == 409

    repair = client.post(
        "/api/v1/equipment/repairs",
        headers=admin_headers,
        json={"merchant_id": gym_id, "asset_id": asset_id, "description": "皮带异响"},
    )
    assert repair.status_code == 200, repair.text
    ticket_id = repair.json()["id"]

    assets = client.get(
        f"/api/v1/equipment/assets?merchant_id={gym_id}&status=repair",
        headers=admin_headers,
    ).json()
    assert any(a["id"] == asset_id for a in assets)

    done = client.post(
        f"/api/v1/equipment/repairs/{ticket_id}/complete",
        headers=admin_headers,
        json={"resolution": "已更换皮带", "asset_status": "in_use"},
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "done"

    refreshed = client.get(
        f"/api/v1/equipment/assets?merchant_id={gym_id}&status=in_use",
        headers=admin_headers,
    ).json()
    assert any(a["id"] == asset_id for a in refreshed)
