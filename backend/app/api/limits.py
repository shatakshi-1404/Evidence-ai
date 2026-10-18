from fastapi import HTTPException, Request, status

from app.api.deps import CurrentUser
from app.core.config import settings
from app.services.ratelimit import check_rate_limit


def _too_many(retry_after: int) -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "Too many requests. Please wait a moment and try again.",
        headers={"Retry-After": str(retry_after)},
    )


def user_rate_limit(name: str, setting: str):
    """Per-user limit. It depends on CurrentUser, so login is checked first (401 before 429)."""

    def dependency(user: CurrentUser) -> None:
        retry_after = check_rate_limit(f"evidenceai:rl:{name}:{user.id}", getattr(settings, setting))
        if retry_after is not None:
            raise _too_many(retry_after)

    return dependency


def ip_rate_limit(name: str, setting: str):
    """Per-IP limit for routes with no logged-in user yet (login, register)."""

    def dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        retry_after = check_rate_limit(f"evidenceai:rl:{name}:{ip}", getattr(settings, setting))
        if retry_after is not None:
            raise _too_many(retry_after)

    return dependency
