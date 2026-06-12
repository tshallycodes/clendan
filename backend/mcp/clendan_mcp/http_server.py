"""
http_server.py — Starlette app wrapping the MCP server over HTTP/SSE transport.

Each SSE connection authenticates with a Clendan API key (Bearer token or
?api_key= query param). The key is injected into a ContextVar so all tool
calls in that session use it instead of the global CLENDAN_API_KEY env var.

Run locally:
    uvicorn clendan_mcp.http_server:app --port 8080

Deploy on Railway: see Dockerfile + railway.toml in this directory.
"""
from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from mcp.server.sse import SseServerTransport

from clendan_mcp.auth import _request_api_key
from clendan_mcp.server import app as mcp_app

sse = SseServerTransport("/messages/")


async def handle_sse(request: Request) -> Response:
    auth = request.headers.get("Authorization", "")
    api_key = (
        auth.removeprefix("Bearer ").strip()
        if auth.startswith("Bearer ")
        else request.query_params.get("api_key", "")
    )

    if not api_key:
        return Response(
            "Unauthorized — provide your Clendan API key as a Bearer token "
            "or ?api_key= query parameter.",
            status_code=401,
        )

    token = _request_api_key.set(api_key)
    try:
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp_app.run(
                streams[0], streams[1], mcp_app.create_initialization_options()
            )
    finally:
        _request_api_key.reset(token)

    return Response()


async def handle_messages(request: Request) -> Response:
    await sse.handle_post_message(request.scope, request.receive, request._send)
    return Response()


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


app = Starlette(
    routes=[
        Route("/health", endpoint=health),
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ]
)
