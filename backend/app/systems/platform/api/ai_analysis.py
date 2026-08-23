"""AI 分析：提示词模版、大模型账号与执行。"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.crypto_secrets import decrypt_secret, encrypt_secret
from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.errors import AppError
from app.core.schemas.paging import PageOut, paginate
from app.systems.platform.models.ai_analysis import AiAnalysisRecord, AiLlmAccount, AiPromptTemplate
from app.systems.platform.models.identity import StaffUser
from app.systems.platform.models.org import Merchant
from app.systems.platform.services.ai_data_context import context_as_json, render_prompt
from app.systems.platform.services.ai_llm import chat_completion
from app.systems.platform.services.ai_prompt_seed import seed_ai_prompt_templates
from app.systems.platform.services.audit import write_audit

router = APIRouter(prefix="/ai", tags=["ai-analysis"])


# ---------- Schemas ----------


class PromptTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    category: str
    data_source: str
    system_prompt: str
    user_prompt_template: str
    description: str | None
    is_builtin: bool
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class PromptTemplateIn(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    category: str = Field(default="自定义", max_length=64)
    data_source: str = Field(default="operations", max_length=64)
    system_prompt: str = Field(min_length=10)
    user_prompt_template: str = Field(min_length=10)
    description: str | None = Field(default=None, max_length=512)
    is_active: bool = True
    sort_order: int = 100


class PromptTemplatePatch(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    category: str | None = Field(default=None, max_length=64)
    data_source: str | None = Field(default=None, max_length=64)
    system_prompt: str | None = None
    user_prompt_template: str | None = None
    description: str | None = Field(default=None, max_length=512)
    is_active: bool | None = None
    sort_order: int | None = None


class LlmAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    provider: str
    base_url: str
    model_name: str
    has_api_key: bool
    is_default: bool
    is_active: bool
    remark: str | None
    created_at: datetime
    updated_at: datetime


class LlmAccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    provider: str = Field(default="openai_compatible", max_length=32)
    base_url: str = Field(min_length=8, max_length=512)
    api_key: str | None = Field(default=None, max_length=512)
    model_name: str = Field(min_length=1, max_length=128)
    is_default: bool = False
    is_active: bool = True
    remark: str | None = Field(default=None, max_length=255)


class LlmAccountPatch(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    provider: str | None = Field(default=None, max_length=32)
    base_url: str | None = Field(default=None, max_length=512)
    api_key: str | None = Field(default=None, max_length=512)
    model_name: str | None = Field(default=None, max_length=128)
    is_default: bool | None = None
    is_active: bool | None = None
    remark: str | None = Field(default=None, max_length=255)


class AnalyzeIn(BaseModel):
    template_id: int
    llm_account_id: int
    merchant_id: int | None = None
    date_from: date | None = None
    date_to: date | None = None
    extra_instruction: str | None = Field(default=None, max_length=2000)


class AnalyzeOut(BaseModel):
    record_id: int
    result_text: str
    input_summary: str


class AnalysisRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    template_id: int
    llm_account_id: int
    merchant_id: int | None
    staff_id: int | None
    status: str
    input_summary: str | None
    result_text: str | None
    error_message: str | None
    created_at: datetime
    template_name: str | None = None
    llm_account_name: str | None = None
    merchant_name: str | None = None
    staff_name: str | None = None


def _day_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start, end


def _analysis_record_scope(ctx: RequestContext, stmt):
    stmt = stmt.where(AiAnalysisRecord.site_id == ctx.site_id)
    if not ctx.is_site_wide:
        # 商户账号仅可见本商户分析记录，不可查看全场地（merchant_id 为空）分析
        stmt = stmt.where(AiAnalysisRecord.merchant_id == ctx.resolve_merchant_id())
    return stmt


def _get_analysis_record_or_404(db: Session, ctx: RequestContext, record_id: int) -> AiAnalysisRecord:
    row = db.get(AiAnalysisRecord, record_id)
    if row is None or row.site_id != ctx.site_id:
        raise AppError("not_found", "记录不存在", status_code=404)
    if not ctx.is_site_wide:
        mid = ctx.resolve_merchant_id()
        if row.merchant_id != mid:
            raise AppError("forbidden", "无权查看该记录", status_code=403)
    return row


def _record_out(db: Session, row: AiAnalysisRecord) -> AnalysisRecordOut:
    template = db.get(AiPromptTemplate, row.template_id)
    account = db.get(AiLlmAccount, row.llm_account_id)
    merchant = db.get(Merchant, row.merchant_id) if row.merchant_id else None
    staff = db.get(StaffUser, row.staff_id) if row.staff_id else None
    return AnalysisRecordOut(
        id=row.id,
        template_id=row.template_id,
        llm_account_id=row.llm_account_id,
        merchant_id=row.merchant_id,
        staff_id=row.staff_id,
        status=row.status,
        input_summary=row.input_summary,
        result_text=row.result_text,
        error_message=row.error_message,
        created_at=row.created_at,
        template_name=template.name if template else None,
        llm_account_name=account.name if account else None,
        merchant_name=merchant.name if merchant else ("全场地" if row.merchant_id is None else None),
        staff_name=staff.display_name if staff else None,
    )


def _build_download_markdown(db: Session, row: AiAnalysisRecord) -> str:
    meta = _record_out(db, row)
    lines = [
        f"# AI 分析报告 #{row.id}",
        "",
        f"- 摘要：{meta.input_summary or '-'}",
        f"- 提示词模版：{meta.template_name or row.template_id}",
        f"- 大模型：{meta.llm_account_name or row.llm_account_id}",
        f"- 分析范围：{meta.merchant_name or '-'}",
        f"- 操作人：{meta.staff_name or '-'}",
        f"- 状态：{row.status}",
        f"- 生成时间：{row.created_at.isoformat() if row.created_at else '-'}",
        "",
        "---",
        "",
    ]
    if row.status == "success" and row.result_text:
        lines.append(row.result_text)
    elif row.error_message:
        lines.append(f"**分析失败**：{row.error_message}")
    else:
        lines.append("_无分析内容_")
    lines.append("")
    return "\n".join(lines)


def _template_out(row: AiPromptTemplate) -> PromptTemplateOut:
    return PromptTemplateOut.model_validate(row)


def _llm_out(row: AiLlmAccount) -> LlmAccountOut:
    return LlmAccountOut(
        id=row.id,
        name=row.name,
        provider=row.provider,
        base_url=row.base_url,
        model_name=row.model_name,
        has_api_key=bool(row.api_key_enc),
        is_default=row.is_default,
        is_active=row.is_active,
        remark=row.remark,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _clear_default_llm(db: Session, site_id: int, except_id: int | None = None) -> None:
    stmt = select(AiLlmAccount).where(AiLlmAccount.site_id == site_id, AiLlmAccount.is_default.is_(True))
    for row in db.scalars(stmt).all():
        if except_id is None or row.id != except_id:
            row.is_default = False


# ---------- 提示词模版 ----------


@router.get("/prompt-templates", response_model=PageOut[PromptTemplateOut])
def list_prompt_templates(
    active_only: bool = False,
    q: str | None = None,
    category: str | None = None,
    data_source: str | None = None,
    is_active: bool | None = None,
    is_builtin: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("ai:read", "ai:manage", "report:read")
    total_count = db.scalar(
        select(func.count()).select_from(AiPromptTemplate).where(AiPromptTemplate.site_id == ctx.site_id)
    )
    if not total_count:
        seed_ai_prompt_templates(db, ctx.site_id)
        db.commit()

    stmt = select(AiPromptTemplate).where(AiPromptTemplate.site_id == ctx.site_id)
    if active_only:
        stmt = stmt.where(AiPromptTemplate.is_active.is_(True))
    if is_active is not None:
        stmt = stmt.where(AiPromptTemplate.is_active.is_(is_active))
    if is_builtin is not None:
        stmt = stmt.where(AiPromptTemplate.is_builtin.is_(is_builtin))
    if category and category.strip():
        stmt = stmt.where(AiPromptTemplate.category == category.strip())
    if data_source and data_source.strip():
        stmt = stmt.where(AiPromptTemplate.data_source == data_source.strip())
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                AiPromptTemplate.name.ilike(like),
                AiPromptTemplate.code.ilike(like),
                AiPromptTemplate.category.ilike(like),
                AiPromptTemplate.description.ilike(like),
            )
        )
    rows, total = paginate(
        db, stmt.order_by(AiPromptTemplate.sort_order.asc(), AiPromptTemplate.id.asc()), page=page, page_size=page_size
    )
    return PageOut(
        items=[_template_out(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/prompt-templates", response_model=PromptTemplateOut)
def create_prompt_template(
    body: PromptTemplateIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("ai:manage")
    code = body.code.strip()
    dup = db.scalar(
        select(AiPromptTemplate.id).where(AiPromptTemplate.site_id == ctx.site_id, AiPromptTemplate.code == code)
    )
    if dup is not None:
        raise AppError("conflict", "模版编码已存在", status_code=409)
    row = AiPromptTemplate(
        site_id=ctx.site_id,
        code=code,
        name=body.name.strip(),
        category=body.category.strip(),
        data_source=body.data_source.strip(),
        system_prompt=body.system_prompt.strip(),
        user_prompt_template=body.user_prompt_template.strip(),
        description=(body.description or "").strip() or None,
        is_builtin=False,
        is_active=body.is_active,
        sort_order=body.sort_order,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _template_out(row)


@router.patch("/prompt-templates/{template_id}", response_model=PromptTemplateOut)
def update_prompt_template(
    template_id: int,
    body: PromptTemplatePatch,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("ai:manage")
    row = db.get(AiPromptTemplate, template_id)
    if row is None or row.site_id != ctx.site_id:
        raise AppError("not_found", "模版不存在", status_code=404)
    fields = body.model_dump(exclude_unset=True)
    for key, val in fields.items():
        if key in {"name", "category", "data_source"} and isinstance(val, str):
            setattr(row, key, val.strip())
        else:
            setattr(row, key, val)
    db.commit()
    db.refresh(row)
    return _template_out(row)


@router.delete("/prompt-templates/{template_id}")
def delete_prompt_template(
    template_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("ai:manage")
    row = db.get(AiPromptTemplate, template_id)
    if row is None or row.site_id != ctx.site_id:
        raise AppError("not_found", "模版不存在", status_code=404)
    if row.is_builtin:
        raise AppError("forbidden", "内置模版不可删除，可停用", status_code=403)
    used = db.scalar(
        select(func.count()).select_from(AiAnalysisRecord).where(AiAnalysisRecord.template_id == template_id)
    )
    if used:
        raise AppError("conflict", "该模版已有分析记录，无法删除，可停用", status_code=409)
    db.delete(row)
    db.commit()
    return {"ok": True}


# ---------- 大模型账号 ----------


@router.get("/llm-accounts", response_model=list[LlmAccountOut])
def list_llm_accounts(
    active_only: bool = False,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("ai:read", "ai:manage")
    stmt = select(AiLlmAccount).where(AiLlmAccount.site_id == ctx.site_id)
    if active_only:
        stmt = stmt.where(AiLlmAccount.is_active.is_(True))
    rows = db.scalars(stmt.order_by(AiLlmAccount.is_default.desc(), AiLlmAccount.id.asc())).all()
    return [_llm_out(r) for r in rows]


@router.post("/llm-accounts", response_model=LlmAccountOut)
def create_llm_account(
    body: LlmAccountIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("ai:manage")
    if body.is_default:
        _clear_default_llm(db, ctx.site_id)
    row = AiLlmAccount(
        site_id=ctx.site_id,
        name=body.name.strip(),
        provider=body.provider.strip(),
        base_url=body.base_url.strip().rstrip("/"),
        api_key_enc=encrypt_secret(body.api_key.strip()) if body.api_key and body.api_key.strip() else None,
        model_name=body.model_name.strip(),
        is_default=body.is_default,
        is_active=body.is_active,
        remark=(body.remark or "").strip() or None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _llm_out(row)


@router.patch("/llm-accounts/{account_id}", response_model=LlmAccountOut)
def update_llm_account(
    account_id: int,
    body: LlmAccountPatch,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("ai:manage")
    row = db.get(AiLlmAccount, account_id)
    if row is None or row.site_id != ctx.site_id:
        raise AppError("not_found", "大模型账号不存在", status_code=404)
    fields = body.model_dump(exclude_unset=True)
    api_key = fields.pop("api_key", None)
    if body.is_default is True:
        _clear_default_llm(db, ctx.site_id, except_id=row.id)
    for key, val in fields.items():
        if key == "base_url" and isinstance(val, str):
            setattr(row, key, val.strip().rstrip("/"))
        elif isinstance(val, str):
            setattr(row, key, val.strip())
        else:
            setattr(row, key, val)
    if api_key is not None:
        row.api_key_enc = encrypt_secret(api_key.strip()) if api_key.strip() else None
    db.commit()
    db.refresh(row)
    return _llm_out(row)


@router.delete("/llm-accounts/{account_id}")
def delete_llm_account(
    account_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("ai:manage")
    row = db.get(AiLlmAccount, account_id)
    if row is None or row.site_id != ctx.site_id:
        raise AppError("not_found", "大模型账号不存在", status_code=404)
    used = db.scalar(
        select(func.count()).select_from(AiAnalysisRecord).where(AiAnalysisRecord.llm_account_id == account_id)
    )
    if used:
        raise AppError("conflict", "该账号已有分析记录，无法删除，可停用", status_code=409)
    db.delete(row)
    db.commit()
    return {"ok": True}


# ---------- 分析执行 ----------


@router.post("/analyze", response_model=AnalyzeOut)
async def run_analysis(
    body: AnalyzeIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("ai:read", "ai:manage")
    template = db.get(AiPromptTemplate, body.template_id)
    if template is None or template.site_id != ctx.site_id or not template.is_active:
        raise AppError("not_found", "提示词模版不存在或已停用", status_code=404)
    account = db.get(AiLlmAccount, body.llm_account_id)
    if account is None or account.site_id != ctx.site_id or not account.is_active:
        raise AppError("not_found", "大模型账号不存在或已停用", status_code=404)
    api_key = decrypt_secret(account.api_key_enc)
    if not api_key:
        raise AppError("validation_error", "大模型账号未配置 API Key", status_code=400)

    today = date.today()
    date_from = body.date_from or today.replace(day=1)
    date_to = body.date_to or today
    if date_to < date_from:
        raise AppError("invalid_range", "结束日期不得早于开始日期", status_code=400)

    merchant_id = body.merchant_id
    if merchant_id is not None:
        merchant = db.get(Merchant, merchant_id)
        if merchant is None or merchant.site_id != ctx.site_id:
            raise AppError("not_found", "商户不存在", status_code=404)
    if merchant_id is not None and not ctx.is_site_wide:
        mid = ctx.resolve_merchant_id()
        if merchant_id != mid:
            raise AppError("forbidden", "无权分析其他商户数据", status_code=403)
    elif merchant_id is None and not ctx.is_site_wide:
        merchant_id = ctx.resolve_merchant_id()

    data_json = context_as_json(
        db,
        ctx,
        data_source=template.data_source,
        date_from=date_from,
        date_to=date_to,
        merchant_id=merchant_id,
    )
    ctx_vars = {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "merchant_name": "全场地" if merchant_id is None else f"商户#{merchant_id}",
    }
    if merchant_id is not None:
        from app.systems.platform.models.org import Merchant

        m = db.get(Merchant, merchant_id)
        if m:
            ctx_vars["merchant_name"] = m.name

    user_prompt = render_prompt(template.user_prompt_template, data_json=data_json, ctx_vars=ctx_vars)
    if body.extra_instruction and body.extra_instruction.strip():
        user_prompt += f"\n\n## 补充要求\n{body.extra_instruction.strip()}"

    input_summary = f"{template.name} · {ctx_vars['merchant_name']} · {date_from}~{date_to}"
    record = AiAnalysisRecord(
        site_id=ctx.site_id,
        merchant_id=merchant_id,
        staff_id=ctx.staff.id if ctx.staff else None,
        template_id=template.id,
        llm_account_id=account.id,
        status="running",
        input_summary=input_summary,
    )
    db.add(record)
    db.flush()

    try:
        result = await chat_completion(
            base_url=account.base_url,
            api_key=api_key,
            model=account.model_name,
            system_prompt=template.system_prompt,
            user_prompt=user_prompt,
        )
        record.status = "success"
        record.result_text = result
    except AppError as exc:
        record.status = "failure"
        record.error_message = exc.message
        db.commit()
        raise
    except Exception as exc:
        record.status = "failure"
        record.error_message = str(exc)[:500]
        db.commit()
        raise AppError("llm_error", f"分析失败: {exc}", status_code=500) from exc

    write_audit(
        db,
        action="ai.analyze",
        target_type="ai_analysis",
        target_id=record.id,
        summary=f"AI 分析：{input_summary}",
        actor_staff_id=ctx.staff.id if ctx.staff else None,
        site_id=ctx.site_id,
        merchant_id=merchant_id,
        subsystem_code="platform",
        module="AI分析",
    )
    db.commit()
    db.refresh(record)
    return AnalyzeOut(record_id=record.id, result_text=record.result_text or "", input_summary=input_summary)


@router.get("/analysis-records/export")
def export_analysis_records(
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """导出分析日志清单（CSV）。"""
    ctx.require_permission("ai:read", "ai:manage")
    stmt = _analysis_record_scope(ctx, select(AiAnalysisRecord))
    if status and status.strip():
        stmt = stmt.where(AiAnalysisRecord.status == status.strip())
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(AiAnalysisRecord.input_summary.ilike(like), AiAnalysisRecord.error_message.ilike(like))
        )
    if date_from is not None and date_to is not None:
        if date_to < date_from:
            raise AppError("invalid_range", "结束日期不得早于开始日期", status_code=400)
        start, end = _day_bounds(date_from, date_to)
        stmt = stmt.where(AiAnalysisRecord.created_at >= start, AiAnalysisRecord.created_at < end)
    rows = db.scalars(stmt.order_by(AiAnalysisRecord.id.desc()).limit(5000)).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["id", "input_summary", "template_name", "llm_account_name", "merchant_name", "staff_name", "status", "created_at"]
    )
    for row in rows:
        meta = _record_out(db, row)
        writer.writerow(
            [
                row.id,
                meta.input_summary or "",
                meta.template_name or "",
                meta.llm_account_name or "",
                meta.merchant_name or "",
                meta.staff_name or "",
                row.status,
                row.created_at.isoformat() if row.created_at else "",
            ]
        )
    buf.seek(0)
    suffix = f"{date_from}-{date_to}" if date_from and date_to else "all"
    filename = f"ai-analysis-logs-{suffix}.csv"
    encoded = quote(filename)
    return StreamingResponse(
        iter(["\ufeff" + buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


@router.get("/analysis-records", response_model=PageOut[AnalysisRecordOut])
def list_analysis_records(
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("ai:read", "ai:manage")
    stmt = _analysis_record_scope(ctx, select(AiAnalysisRecord))
    if status and status.strip():
        stmt = stmt.where(AiAnalysisRecord.status == status.strip())
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(AiAnalysisRecord.input_summary.ilike(like), AiAnalysisRecord.error_message.ilike(like))
        )
    if date_from is not None and date_to is not None:
        if date_to < date_from:
            raise AppError("invalid_range", "结束日期不得早于开始日期", status_code=400)
        start, end = _day_bounds(date_from, date_to)
        stmt = stmt.where(AiAnalysisRecord.created_at >= start, AiAnalysisRecord.created_at < end)
    rows, total = paginate(
        db, stmt.order_by(AiAnalysisRecord.id.desc()), page=page, page_size=page_size
    )
    return PageOut(
        items=[_record_out(db, r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/analysis-records/{record_id}", response_model=AnalysisRecordOut)
def get_analysis_record(
    record_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("ai:read", "ai:manage")
    row = _get_analysis_record_or_404(db, ctx, record_id)
    return _record_out(db, row)


@router.get("/analysis-records/{record_id}/download")
def download_analysis_record(
    record_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """下载单条分析报告（Markdown）。"""
    ctx.require_permission("ai:read", "ai:manage")
    row = _get_analysis_record_or_404(db, ctx, record_id)
    content = _build_download_markdown(db, row)
    filename = f"ai-analysis-{record_id}.md"
    encoded = quote(filename)
    return StreamingResponse(
        iter([content.encode("utf-8")]),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )
