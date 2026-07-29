"""HTTP and JSON-RPC interfaces for the offline agent."""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .graph import AgentState, get_graph
from .logging_config import configure_logging
from .tools import TOOLS, ToolError, call_tool

LOGGER = logging.getLogger("agentsvc.api")
DEFAULT_APP_VERSION = "0.1.0"
DEFAULT_LOG_LEVEL = "INFO"


class InvokeRequest(BaseModel):
    question: str


class InvokeResponse(BaseModel):
    answer: str
    steps: list[str]
    tool_name: str | None
    tool_result: dict[str, Any] | None
    latency_ms: float


class JsonRpcRequest(BaseModel):
    jsonrpc: Literal["2.0"]
    id: str | int | None
    method: str
    params: Any = None


def _jsonrpc_error(request_id: str | int | None, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _initial_state(question: str) -> AgentState:
    return {
        "question": question,
        "plan": "",
        "tool_name": None,
        "tool_args": None,
        "tool_result": None,
        "answer": "",
        "steps": [],
    }


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    configure_logging(os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL))
    app_version = os.getenv("APP_VERSION", DEFAULT_APP_VERSION)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.graph_ready = False
        app.state.graph = None
        try:
            app.state.graph = get_graph()
            app.state.graph_ready = True
        except Exception:
            LOGGER.exception("graph compilation failed")
        yield

    app = FastAPI(title="LangGraph Kubernetes Demo", version=app_version, lifespan=lifespan)
    app.state.graph_ready = False
    app.state.graph = None

    @app.middleware("http")
    async def request_logging(request: Request, call_next: Any) -> Any:
        request_id = uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            LOGGER.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                },
            )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> Any:
        if not app.state.graph_ready:
            return JSONResponse(status_code=503, content={"status": "not ready"})
        return {"status": "ready"}

    @app.post("/invoke", response_model=InvokeResponse)
    async def invoke(body: InvokeRequest) -> InvokeResponse:
        if not app.state.graph_ready or app.state.graph is None:
            raise HTTPException(status_code=503, detail="Graph is not ready")
        started = time.perf_counter()
        result = app.state.graph.invoke(_initial_state(body.question))
        return InvokeResponse(
            answer=result["answer"],
            steps=result["steps"],
            tool_name=result["tool_name"],
            tool_result=result["tool_result"],
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
        )

    @app.post("/mcp")
    async def mcp(body: JsonRpcRequest) -> dict[str, Any]:
        if body.method == "tools/list":
            if body.params not in (None, {}):
                return _jsonrpc_error(body.id, -32602, "Invalid params")
            tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.input_schema,
                }
                for tool in TOOLS.values()
            ]
            return {"jsonrpc": "2.0", "id": body.id, "result": {"tools": tools}}

        if body.method == "tools/call":
            params = body.params
            if (
                not isinstance(params, dict)
                or not isinstance(params.get("name"), str)
                or not isinstance(params.get("arguments"), dict)
                or set(params) != {"name", "arguments"}
            ):
                return _jsonrpc_error(body.id, -32602, "Invalid params")
            try:
                result = call_tool(params["name"], params["arguments"])
            except ToolError as exc:
                return _jsonrpc_error(body.id, -32602, str(exc))
            return {
                "jsonrpc": "2.0",
                "id": body.id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result)}],
                    "isError": False,
                },
            }

        return _jsonrpc_error(body.id, -32601, "Method not found")

    return app


app = create_app()
