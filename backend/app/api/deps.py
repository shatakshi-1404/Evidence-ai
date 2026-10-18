import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

# auto_error=False: a missing Authorization header isn't fatal any more, because
# the browser app authenticates with a cookie. Swagger's Authorize button still works.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_current_user(
    request: Request,
    bearer: Annotated[str | None, Depends(oauth2_scheme)],
    db: DbSession,
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = bearer
    from_cookie = False
    if token is None:
        token = request.cookies.get(settings.cookie_name)
        from_cookie = token is not None
    if token is None:
        raise credentials_error

    if from_cookie and request.method not in SAFE_METHODS:
        # Browsers attach cookies on their own, so a hostile website could try to
        # trigger actions in your name. SameSite=Lax already blocks most of that;
        # this Origin check is a second layer. Bearer-header requests skip it,
        # because a header is never attached automatically.
        origin = request.headers.get("origin")
        if origin is not None and origin not in settings.cors_origins:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-origin request blocked")

    subject = decode_access_token(token)
    if subject is None:
        raise credentials_error
    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        raise credentials_error

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_error
    return user


# Add `current_user: CurrentUser` to any route to make it login-only.
CurrentUser = Annotated[User, Depends(get_current_user)]
