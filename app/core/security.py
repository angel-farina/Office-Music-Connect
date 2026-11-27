import hmac
import secrets
from collections import deque
from time import monotonic

from fastapi import HTTPException, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


bearer_scheme = HTTPBearer(auto_error=False)
_failed_attempts: dict[str, deque[float]] = {}


def validate_configured_token(token: str) -> None:
    if not token or token.startswith("REEMPLAZAR"):
        raise RuntimeError(
            "APP_ACCESS_TOKEN no esta configurado. Copie .env.example a .env y genere un token aleatorio."
        )


def verify_token(token: str, configured_token: str) -> bool:
    return bool(token) and hmac.compare_digest(token, configured_token)


def require_bearer(
    credentials: HTTPAuthorizationCredentials | None,
    configured_token: str,
    client_key: str = "unknown",
) -> None:
    if not credentials or not verify_token(credentials.credentials, configured_token):
        now = monotonic()
        attempts = _failed_attempts.setdefault(client_key, deque())
        while attempts and now - attempts[0] > 60:
            attempts.popleft()
        attempts.append(now)
        if len(attempts) >= 10:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados intentos")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalido")


async def require_websocket_token(websocket: WebSocket, configured_token: str) -> None:
    token = websocket.query_params.get("token")
    if not verify_token(token or "", configured_token):
        await websocket.close(code=1008)
        raise RuntimeError("Unauthorized")


def generate_token() -> str:
    return secrets.token_urlsafe(32)
