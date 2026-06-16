"""
Clen AI assistant routes.
POST /v1/clen/chat   — streaming SSE chat (docs mode: no auth, account mode: Bearer JWT required)
DELETE /v1/clen/conversation — stateless clear (frontend holds conversation state)
"""
import json
import time
from typing import Annotated, AsyncGenerator, Optional

import anthropic
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from jose import JWTError, jwt
from jose.exceptions import JWKError
from prisma import Prisma
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.security import _fetch_jwks
from app.clen.context import build_system_prompt
from app.clen.tools import ACCOUNT_TOOLS, execute_tool

logger = get_logger(__name__)
router = APIRouter(tags=["clen"])

# ---------------------------------------------------------------------------
# Rate limiting — in-memory, per user_id (auth) or IP (unauth)
# ---------------------------------------------------------------------------

_rate_limits: dict[str, dict] = {}

_RATE_LIMIT_AUTH = 200      # requests per hour for authenticated users
_RATE_LIMIT_UNAUTH = 20     # requests per hour for unauthenticated users
_RATE_WINDOW_SECONDS = 3600


def _check_rate_limit(key: str, limit: int) -> bool:
    """Returns True if the request is allowed, False if rate limit exceeded."""
    now = time.time()
    bucket = _rate_limits.get(key)
    if bucket is None or now - bucket["window_start"] >= _RATE_WINDOW_SECONDS:
        _rate_limits[key] = {"window_start": now, "count": 1}
        return True
    if bucket["count"] >= limit:
        return False
    bucket["count"] += 1
    return True


# ---------------------------------------------------------------------------
# Optional auth — decode JWT if present, return (tenant_id, user_id) or (None, None)
# ---------------------------------------------------------------------------

async def _try_decode_jwt(token: str, db: Prisma) -> tuple[Optional[str], Optional[str]]:
    """
    Attempts to verify the Bearer token and resolve tenant_id.
    Returns (tenant_id, user_id) on success, (None, None) on any failure.
    Never raises — failures silently fall back to docs mode.
    """
    try:
        jwks = await _fetch_jwks()
        payload = jwt.decode(token, jwks, algorithms=["RS256"], options={"verify_aud": False})
    except (JWTError, JWKError, Exception):
        return None, None

    user_id: str = payload.get("sub", "")
    if not user_id:
        return None, None

    org_id: str = payload.get("org_id", "")
    try:
        if org_id:
            tenant = await db.tenant.find_unique(where={"clerk_org_id": org_id})
            if tenant:
                return tenant.id, user_id
        # Fallback: resolve via Member table
        member = await db.member.find_unique(where={"clerk_user_id": user_id})
        if member:
            tenant = await db.tenant.find_unique(where={"id": member.tenant_id})
            if tenant:
                return tenant.id, user_id
    except Exception as exc:
        logger.warning("clen_auth_resolve_failed error=%s", type(exc).__name__)
    return None, None


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ClenChatRequest(BaseModel):
    messages: list[dict]  # [{role: "user"|"assistant", content: str}]
    mode: str = "docs"    # "docs" | "account" — overridden to "docs" if no valid auth


# ---------------------------------------------------------------------------
# Streaming generator
# ---------------------------------------------------------------------------

_MAX_TOOL_ROUNDS = 5  # prevents infinite tool-use loops


async def _generate(
    messages: list[dict],
    mode: str,
    tenant_id: Optional[str],
    user_id: Optional[str],
    db: Prisma,
) -> AsyncGenerator[str, None]:
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    try:
        system = await build_system_prompt(mode, tenant_id, db)
    except Exception as exc:
        logger.error("clen_system_prompt_failed error=%s", type(exc).__name__)
        yield f"data: {json.dumps({'type': 'error', 'content': 'Clen failed to initialise — please try again'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    tools = ACCOUNT_TOOLS if mode == "account" else []

    # Mutable copy so we can append tool results for multi-turn agentic loop
    current_messages: list[dict] = list(messages[-20:])

    try:
        for _ in range(_MAX_TOOL_ROUNDS):
            kwargs: dict = {
                "model": settings.claude_model,
                "max_tokens": 1024,
                "system": system,
                "messages": current_messages,
            }
            if tools:
                kwargs["tools"] = tools

            async with client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield f"data: {json.dumps({'type': 'text', 'content': text})}\n\n"
                final = await stream.get_final_message()

            # No tool calls — Claude is done
            if final.stop_reason != "tool_use":
                break

            # Build assistant content block list for message history
            assistant_content: list[dict] = []
            for block in final.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            # Execute each tool call and collect results
            tool_results: list[dict] = []
            for block in final.content:
                if block.type != "tool_use":
                    continue
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': block.name, 'input': block.input})}\n\n"
                result = await execute_tool(block.name, block.input, tenant_id or "", user_id, db)
                yield f"data: {json.dumps({'type': 'tool_result', 'tool': block.name, 'result': result})}\n\n"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

            # Append assistant + tool results so Claude can form its natural language response
            current_messages.append({"role": "assistant", "content": assistant_content})
            current_messages.append({"role": "user", "content": tool_results})

    except anthropic.APIError as exc:
        logger.error("clen_stream_api_error type=%s msg=%s", type(exc).__name__, str(exc))
        yield f"data: {json.dumps({'type': 'error', 'content': 'Clen encountered an error — please try again'})}\n\n"
    except Exception as exc:
        import traceback
        logger.error("clen_stream_error type=%s msg=%s trace=%s", type(exc).__name__, str(exc), traceback.format_exc())
        yield f"data: {json.dumps({'type': 'error', 'content': f'[DEBUG] {type(exc).__name__}: {str(exc)[:200]}'})}\n\n"

    yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/clen/chat")
async def clen_chat(
    request: Request,
    body: ClenChatRequest,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    Streaming SSE chat endpoint for Clen AI assistant.
    - No Authorization header → docs mode (rate limited by IP, 20/hour)
    - Valid Authorization header → account mode (rate limited by user_id, 200/hour)
    - Invalid/expired token → docs mode, no error surfaced
    """
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    mode = "docs"

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):]
        tenant_id, user_id = await _try_decode_jwt(token, db)
        if tenant_id and user_id:
            # Security: only elevate to account mode if auth succeeded
            mode = "account" if body.mode == "account" else "docs"

    # Rate limiting
    if user_id:
        rate_key = f"clen:user:{user_id}"
        allowed = _check_rate_limit(rate_key, _RATE_LIMIT_AUTH)
    else:
        client_ip = request.client.host if request.client else "unknown"
        rate_key = f"clen:ip:{client_ip}"
        allowed = _check_rate_limit(rate_key, _RATE_LIMIT_UNAUTH)

    if not allowed:

        async def _rate_limit_stream() -> AsyncGenerator[str, None]:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Rate limit exceeded — please wait before sending more messages'})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            _rate_limit_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return StreamingResponse(
        _generate(body.messages, mode, tenant_id, user_id, db),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/clen/conversation")
async def clen_clear_conversation():
    """
    Stateless conversation clear.
    The frontend holds all conversation state — this endpoint exists for
    clients that want a documented clear action. Returns confirmation only.
    """
    return {"cleared": True}
