"""FastAPI application entry point."""

from fastapi import FastAPI

from app.core.config import get_settings

# Validate required configuration before the application begins serving requests.
get_settings()

app = FastAPI(title="HI Gallery API", version="0.1.0")


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Report that the API process is running."""
    return {"status": "ok"}
