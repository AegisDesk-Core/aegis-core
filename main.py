"""ASGI entrypoint for running Uvicorn from the repository root."""

from app.main import app

__all__ = ["app"]
