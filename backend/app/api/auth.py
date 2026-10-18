from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.api.limits import ip_rate_limit
from app.core.config import settings
from app.core.security import (
    DUMMY_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

# Login and register share one budget per IP address, which slows password guessing.
auth_limit = Depends(ip_rate_limit("auth", "rate_limit_auth_per_minute"))


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[auth_limit],
)
def register(payload: UserCreate, db: DbSession) -> User:
    email = payload.email.lower()

    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip(),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    db.refresh(user)
    return user


@router.post("/login", response_model=Token, dependencies=[auth_limit])
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
    response: Response,
) -> Token:
    email = form.username.strip().lower()
    user = db.scalar(select(User).where(User.email == email))

    hashed = user.hashed_password if user else DUMMY_HASH
    password_ok = verify_password(form.password, hashed)

    if user is None or not password_ok or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(str(user.id))
    # The browser keeps this cookie but page scripts cannot read it (httponly).
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.use_secure_cookie,
        samesite="lax",
        path="/",
    )
    return Token(access_token=token)  # the token also works as a Bearer header (scripts, Swagger)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(
        key=settings.cookie_name,
        path="/",
        httponly=True,
        secure=settings.use_secure_cookie,
        samesite="lax",
    )


@router.get("/me", response_model=UserRead)
def me(current_user: CurrentUser) -> User:
    return current_user
