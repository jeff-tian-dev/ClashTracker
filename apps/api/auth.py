import logging

from fastapi import Header, HTTPException

from .config import ADMIN_API_KEY

logger = logging.getLogger(__name__)


def require_admin(authorization: str | None = Header(None)) -> None:
    if not ADMIN_API_KEY:
        raise HTTPException(
            status_code=503,
            detail={"error": "admin_not_configured", "hint": "ADMIN_API_KEY is not set on the server."},
        )

    if not authorization or not authorization.startswith("Bearer "):
        logger.warning(
            "admin auth missing or malformed",
            extra={"event": "admin.auth.missing"},
        )
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    if token != ADMIN_API_KEY:
        logger.warning(
            "admin auth rejected (wrong key)",
            extra={"event": "admin.auth.rejected"},
        )
        raise HTTPException(status_code=403, detail="Invalid admin key")
