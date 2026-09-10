from __future__ import annotations

import logging
import traceback
from typing import NoReturn
from uuid import uuid4

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("pixelator")


def new_trace_id() -> str:
    return uuid4().hex[:12]


def _user_message(exc: BaseException) -> str:
    text = str(exc) or exc.__class__.__name__
    lowered = text.lower()
    if "errno 22" in lowered or "invalid argument" in lowered:
        return (
            "Could not open or save a file (Windows invalid argument). "
            "This usually means a path had a reserved character such as : * ? \" < > |, "
            "an empty filename, or a file that is not a valid image. "
            f"Technical: {text}"
        )
    return text


def error_payload(
    exc: BaseException,
    *,
    context: dict | None = None,
    trace_id: str | None = None,
    include_trace: bool = True,
) -> dict:
    tid = trace_id or new_trace_id()
    details = traceback.format_exc() if include_trace else str(exc)
    payload = {
        "error": True,
        "message": _user_message(exc),
        "details": details.strip() or str(exc),
        "traceId": tid,
        "context": {key: str(value) for key, value in (context or {}).items() if value is not None},
    }
    logger.error(
        "trace=%s context=%s error=%s\n%s",
        tid,
        payload["context"],
        payload["message"],
        payload["details"],
    )
    return payload


def http_error(exc: Exception, *, status: int | None = None, context: dict | None = None) -> NoReturn:
    if isinstance(exc, HTTPException):
        raise exc
    code = status
    if code is None:
        if isinstance(exc, KeyError):
            code = 404
        elif isinstance(exc, ValueError):
            code = 400
        elif isinstance(exc, FileNotFoundError):
            code = 404
        elif isinstance(exc, OSError):
            code = 500
        else:
            code = 500
    payload = error_payload(exc, context=context)
    raise HTTPException(status_code=code, detail=payload) from exc


def install_error_handlers(app) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        payload = error_payload(
            ValueError("Invalid request payload"),
            context={"path": str(request.url.path), "method": request.method},
            include_trace=False,
        )
        payload["details"] = str(exc.errors())
        payload["message"] = "Invalid request payload"
        return JSONResponse(status_code=422, content=payload)

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and detail.get("error"):
            payload = detail
        else:
            payload = {
                "error": True,
                "message": str(detail) if detail else exc.reason,
                "details": str(detail),
                "traceId": new_trace_id(),
                "context": {"path": str(request.url.path), "method": request.method, "status": str(exc.status_code)},
            }
            logger.error("HTTP %s %s %s", exc.status_code, request.url.path, payload["message"])
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        payload = error_payload(
            exc,
            context={"path": str(request.url.path), "method": request.method},
        )
        return JSONResponse(status_code=500, content=payload)
