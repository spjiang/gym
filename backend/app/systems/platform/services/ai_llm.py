"""OpenAI 兼容接口调用大模型。"""

from __future__ import annotations

import httpx

from app.core.errors import AppError


async def chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    timeout: float = 120.0,
) -> str:
    """调用 Chat Completions，返回 assistant 文本。"""
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
    except httpx.TimeoutException as exc:
        raise AppError("llm_timeout", "大模型请求超时，请稍后重试", status_code=504) from exc
    except httpx.RequestError as exc:
        raise AppError("llm_network", f"无法连接大模型服务: {exc}", status_code=502) from exc

    if resp.status_code >= 400:
        detail = resp.text[:500]
        raise AppError("llm_error", f"大模型返回错误 ({resp.status_code}): {detail}", status_code=502)

    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise AppError("llm_empty", "大模型未返回有效内容", status_code=502)
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not content:
        raise AppError("llm_empty", "大模型返回内容为空", status_code=502)
    return str(content).strip()
