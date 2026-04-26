# backend/api/deps.py
# Shared FastAPI dependencies

import logging

from fastapi import Header

logger = logging.getLogger(__name__)


def get_session_id(x_session_id: str = Header(default=None)) -> str:
    """Extract the browser session ID from the X-Session-ID request header.

    Bug #5 fix: Log a warning when the header is missing so misconfigured
    clients (curl, Postman, direct API calls) are visible in server logs.
    The "global" fallback is kept for backwards compatibility but should
    not be relied on in production — all clients must send X-Session-ID.
    """
    if not x_session_id:
        logger.warning(
            "X-Session-ID header missing — falling back to 'global' partition. "
            "All headerless API calls share a single data namespace. "
            "Ensure every client sends X-Session-ID."
        )
        return "global"
    return x_session_id
