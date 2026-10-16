"""FastAPI application entry point."""

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette import status

from app.core.config import get_settings
from app.modules.auth.router import router as auth_router

# Validate required configuration before the application begins serving requests.
get_settings()

settings = get_settings()
app = FastAPI(title="HI Gallery API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
app.include_router(auth_router)


def _error_body(code: str, message: str, details: object = None) -> dict[str, object]:
    return {
        "code": code,
        "message": message,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    del request
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    code = str(detail.get("code", "REQUEST_FAILED"))
    message = str(detail.get("message", code.replace("_", " ").capitalize()))
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(code, message, detail.get("details")),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    del request
    safe_details = [
        {"field": ".".join(str(part) for part in error.get("loc", ()) if part != "body"),
         "code": str(error.get("type", "invalid"))}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_body("VALIDATION_ERROR", "Request validation failed", safe_details),
    )


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Report that the API process is running."""
    return {"status": "ok"}
