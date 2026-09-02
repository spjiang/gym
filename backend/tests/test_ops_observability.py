"""运维可观测：探活、错误事件、request_id。"""

from datetime import date

from fastapi.testclient import TestClient


def test_health_returns_request_id(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.headers.get("x-request-id")


def test_ready_ok_when_postgres_up(client: TestClient):
    resp = client.get("/ready")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert body["checks"]["postgres"] == "ok"


def test_ops_health_requires_auth(client: TestClient):
    assert client.get("/api/v1/ops/health-status").status_code in (401, 403)


def test_ops_health_status_for_admin(client: TestClient, admin_headers: dict):
    resp = client.get("/api/v1/ops/health-status", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["postgres"]["ok"] is True
    assert "error_count_24h" in body


def test_devops_menus_in_navigation(client: TestClient, admin_headers: dict):
    nav = client.get("/api/v1/me/navigation", headers=admin_headers)
    assert nav.status_code == 200, nav.text
    paths = {m["path"] for m in nav.json()["menus"]}
    assert "/platform/audit-logs" in paths
    assert "/platform/error-logs" in paths
    assert "/platform/service-health" in paths


def test_order_validation_does_not_write_error_event(client: TestClient, admin_headers: dict):
    gym_id = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    before = client.get("/api/v1/ops/error-events", headers=admin_headers).json()["total"]
    resp = client.post(
        "/api/v1/orders",
        headers=admin_headers,
        json={"merchant_id": gym_id, "order_type": "retail", "title": "  ", "amount": 0},
    )
    assert resp.status_code in (400, 422)
    after = client.get("/api/v1/ops/error-events", headers=admin_headers).json()["total"]
    assert after == before


def test_unhandled_exception_writes_error_event(client: TestClient, admin_headers: dict):
    async def boom():
        raise RuntimeError("intentional-ops-boom")

    client.app.add_api_route("/api/v1/__test/boom", boom, methods=["GET"])
    resp = client.get("/api/v1/__test/boom", headers=admin_headers)
    assert resp.status_code == 500
    rid = resp.headers.get("x-request-id")
    assert rid
    listed = client.get(
        "/api/v1/ops/error-events",
        headers=admin_headers,
        params={"request_id": rid},
    )
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert items
    assert any("intentional-ops-boom" in (x.get("message") or "") or "intentional-ops-boom" in (x.get("stack_trace") or "") for x in items)
    assert items[0]["request_id"] == rid
    assert items[0]["stack_trace"]


def test_wechat_notify_invalid_json_writes_error_event(client: TestClient, admin_headers: dict):
    before_ids = {
        x["id"]
        for x in client.get("/api/v1/ops/error-events", headers=admin_headers, params={"page_size": 100}).json()["items"]
    }
    resp = client.post(
        "/api/v1/payments/wechat/notify",
        content=b"not-json",
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == "FAIL"
    listed = client.get("/api/v1/ops/error-events", headers=admin_headers, params={"page_size": 100})
    new_items = [x for x in listed.json()["items"] if x["id"] not in before_ids]
    assert new_items
    assert any(x["error_code"] in ("wechat_notify_invalid", "wechat_notify_rejected") or "json" in (x["message"] or "").lower() for x in new_items)


def test_error_events_forbidden_without_devops(client: TestClient, admin_headers: dict):
    gym_id = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    created = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "front_no_devops",
            "password": "Front@123456",
            "display_name": "前台无运维",
            "merchant_id": gym_id,
            "role_codes": ["gym_ops"],
        },
    )
    assert created.status_code == 200, created.text
    token = client.post(
        "/api/v1/auth/login", json={"username": "front_no_devops", "password": "Front@123456"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    denied = client.get("/api/v1/ops/error-events", headers=headers)
    assert denied.status_code == 403


def test_write_audit_keeps_request_id(client: TestClient, admin_headers: dict):
    gym_id = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    resp = client.post(
        "/api/v1/orders",
        headers=admin_headers,
        json={"merchant_id": gym_id, "order_type": "retail", "title": "运维追踪单", "amount": 10},
    )
    assert resp.status_code == 200, resp.text
    rid = resp.headers.get("x-request-id")
    today = date.today().isoformat()
    logs = client.get(
        "/api/v1/audit-logs",
        headers=admin_headers,
        params={"date_from": today, "date_to": today, "page_size": 50},
    )
    assert logs.status_code == 200, logs.text
    assert any(x.get("request_id") == rid for x in logs.json()["items"])


def test_site_ops_can_read_error_events(client: TestClient, admin_headers: dict):
    created = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "site_ops_errors",
            "password": "Ops@123456",
            "display_name": "场地运营看错误",
            "merchant_id": None,
            "role_codes": ["site_ops"],
        },
    )
    assert created.status_code == 200, created.text
    token = client.post(
        "/api/v1/auth/login", json={"username": "site_ops_errors", "password": "Ops@123456"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    listed = client.get("/api/v1/ops/error-events", headers=headers)
    assert listed.status_code == 200, listed.text
