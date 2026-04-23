# backend/api/deps.py
# Shared FastAPI dependencies

from fastapi import Header


def get_session_id(x_session_id: str = Header(default="global")) -> str:
    """Extract the browser session ID from the X-Session-ID request header."""
    return x_session_id if x_session_id else "global"
