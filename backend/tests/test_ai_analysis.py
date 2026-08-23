"""AI 分析模块测试。"""

from fastapi.testclient import TestClient


def test_ai_prompt_templates_auto_seed(client: TestClient, admin_headers: dict):
    listed = client.get("/api/v1/ai/prompt-templates", headers=admin_headers)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] >= 8
    items = body["items"]
    codes = {x["code"] for x in items}
    assert "ops_overview" in codes
    assert "audit_log_review" in codes
    assert any(x["is_builtin"] for x in items)

    filtered = client.get(
        "/api/v1/ai/prompt-templates",
        headers=admin_headers,
        params={"q": "操作日志", "page_size": 10},
    )
    assert filtered.status_code == 200
    assert all("操作" in x["name"] or "日志" in (x["description"] or "") for x in filtered.json()["items"])


def test_ai_llm_account_crud(client: TestClient, admin_headers: dict):
    created = client.post(
        "/api/v1/ai/llm-accounts",
        headers=admin_headers,
        json={
            "name": "测试 DeepSeek",
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "sk-test-key",
            "model_name": "deepseek-chat",
            "is_default": True,
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["has_api_key"] is True
    assert body["name"] == "测试 DeepSeek"

    listed = client.get("/api/v1/ai/llm-accounts", headers=admin_headers)
    assert listed.status_code == 200
    assert any(x["id"] == body["id"] for x in listed.json())

    updated = client.patch(
        f"/api/v1/ai/llm-accounts/{body['id']}",
        headers=admin_headers,
        json={"model_name": "deepseek-reasoner"},
    )
    assert updated.status_code == 200
    assert updated.json()["model_name"] == "deepseek-reasoner"

    deleted = client.delete(f"/api/v1/ai/llm-accounts/{body['id']}", headers=admin_headers)
    assert deleted.status_code == 200


def test_ai_analyze_requires_llm_key(client: TestClient, admin_headers: dict):
    templates = client.get("/api/v1/ai/prompt-templates", headers=admin_headers).json()["items"]
    tpl = next(x for x in templates if x["code"] == "ops_overview")
    acc = client.post(
        "/api/v1/ai/llm-accounts",
        headers=admin_headers,
        json={
            "name": "无密钥",
            "base_url": "https://api.deepseek.com/v1",
            "model_name": "deepseek-chat",
        },
    ).json()
    resp = client.post(
        "/api/v1/ai/analyze",
        headers=admin_headers,
        json={"template_id": tpl["id"], "llm_account_id": acc["id"]},
    )
    assert resp.status_code == 400


def test_ai_analysis_logs_list_and_download(client: TestClient, admin_headers: dict):
    listed = client.get("/api/v1/ai/analysis-records", headers=admin_headers)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    if body["total"] == 0:
        return
    row = body["items"][0]
    assert "template_name" in row
    detail = client.get(f"/api/v1/ai/analysis-records/{row['id']}", headers=admin_headers)
    assert detail.status_code == 200
    download = client.get(f"/api/v1/ai/analysis-records/{row['id']}/download", headers=admin_headers)
    assert download.status_code == 200
    assert b"AI" in download.content or b"\xe5" in download.content
    export = client.get(
        "/api/v1/ai/analysis-records/export",
        headers=admin_headers,
        params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
    )
    assert export.status_code == 200
    assert "text/csv" in export.headers.get("content-type", "")


def test_ai_analysis_records_merchant_isolation(client: TestClient, admin_headers: dict):
    """商户账号不可查看全场地或其他商户的 AI 分析记录。"""
    from sqlalchemy import select

    from app.core import db as db_module
    from app.systems.platform.models.ai_analysis import AiAnalysisRecord

    merchants = client.get("/api/v1/merchants", headers=admin_headers).json()
    gym_id = merchants[0]["id"]
    client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "ai_gym_admin",
            "password": "Ai@123456",
            "display_name": "AI商户管理员",
            "merchant_id": gym_id,
            "role_codes": ["gym_admin"],
        },
    )
    mheaders = {
        "Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'username': 'ai_gym_admin', 'password': 'Ai@123456'}).json()['access_token']}"
    }

    db = db_module.SessionLocal()
    site_row_id: int | None = None
    try:
        from app.systems.platform.models.ai_analysis import AiLlmAccount, AiPromptTemplate

        template_id = db.scalar(select(AiPromptTemplate.id).limit(1))
        llm_id = db.scalar(select(AiLlmAccount.id).limit(1))
        if template_id is None or llm_id is None:
            return
        site_rec = AiAnalysisRecord(
            site_id=1,
            merchant_id=None,
            template_id=template_id,
            llm_account_id=llm_id,
            status="success",
            input_summary="全场地分析",
            result_text="secret site report",
        )
        gym_rec = AiAnalysisRecord(
            site_id=1,
            merchant_id=gym_id,
            template_id=template_id,
            llm_account_id=llm_id,
            status="success",
            input_summary="本商户分析",
            result_text="gym report",
        )
        db.add(site_rec)
        db.add(gym_rec)
        db.flush()
        site_row_id = site_rec.id
        db.commit()
    finally:
        db.close()

    listed = client.get("/api/v1/ai/analysis-records", headers=mheaders, params={"page_size": 50})
    assert listed.status_code == 200
    summaries = {x["input_summary"] for x in listed.json()["items"]}
    assert "本商户分析" in summaries
    assert "全场地分析" not in summaries

    if site_row_id:
        denied = client.get(f"/api/v1/ai/analysis-records/{site_row_id}", headers=mheaders)
        assert denied.status_code == 403
