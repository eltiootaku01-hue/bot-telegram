# -*- coding: utf-8 -*-
"""FastAPI authentication, database and Café authorization dependencies."""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache
import os

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from bot_ia.interfaces.telegram_room_routing import TelegramRoomRouter
from bot_ia.paths import PROJECT_ROOT

from .security.telegram_auth import (
    AuthenticatedTelegramActor,
    TelegramAuthError,
    extract_tma_init_data,
    validate_telegram_init_data,
)
from .security.telegram_membership import (
    TelegramMembershipDecision,
    TelegramMembershipUnavailable,
    TelegramMembershipVerifier,
)
from .security.trusted_context import (
    TrustedCafeContext,
    TrustedContextConfigurationError,
    TrustedContextError,
    TrustedContextRegistry,
)


class CafeAuthorization(BaseModel):
    """Final W01-C authorization result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor: AuthenticatedTelegramActor
    context: TrustedCafeContext
    membership: TelegramMembershipDecision


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker:
    db_url = os.getenv(
        "DATABASE_URL",
        "sqlite:///bot_database.db",
    ).strip() or "sqlite:///bot_database.db"
    connect_args = (
        {"check_same_thread": False}
        if db_url.startswith("sqlite:")
        else {}
    )
    engine = create_engine(
        db_url,
        echo=False,
        connect_args=connect_args,
    )
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )


def get_db() -> Generator[Session, None, None]:
    """Yield a short-lived SQLAlchemy session for the existing TCG DB."""
    db = _session_factory()()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    authorization: str | None = Header(
        default=None,
        alias="Authorization",
    ),
) -> AuthenticatedTelegramActor:
    """Validate Telegram identity; never accept client actor data."""
    try:
        init_data = extract_tma_init_data(authorization)
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not bot_token:
            raise TelegramAuthError("missing_bot_token")
        return validate_telegram_init_data(init_data, bot_token)
    except TelegramAuthError as error:
        if error.code in {"missing_bot_token", "invalid_configuration"}:
            raise HTTPException(
                status_code=503,
                detail="Telegram authentication dependency is not configured",
            ) from error
        raise HTTPException(
            status_code=401,
            detail="Invalid Telegram authentication",
        ) from error


def get_trusted_context_registry() -> TrustedContextRegistry:
    """Use the existing TelegramRoomRouter as the Room authority."""
    router = TelegramRoomRouter(
        PROJECT_ROOT / "config" / "telegram_rooms.sqlite3"
    )
    try:
        return TrustedContextRegistry(
            router,
            issuer=os.getenv(
                "TMA_CONTEXT_ISSUER",
                "cafe-otaku",
            ).strip(),
        )
    except TrustedContextConfigurationError as error:
        raise HTTPException(
            status_code=503,
            detail="Trusted context dependency is not configured",
        ) from error


def get_telegram_membership_verifier() -> TelegramMembershipVerifier:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise HTTPException(
            status_code=503,
            detail="Telegram membership dependency is not configured",
        )
    try:
        return TelegramMembershipVerifier(token)
    except TelegramMembershipUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Telegram membership dependency is unavailable",
        ) from error


async def authorize_cafe_access(
    actor: AuthenticatedTelegramActor,
    context_reference: str | None,
    registry: TrustedContextRegistry,
    membership_verifier: TelegramMembershipVerifier,
) -> CafeAuthorization:
    """Execute auth -> trusted context -> Room routing -> membership."""
    if not context_reference:
        raise HTTPException(
            status_code=404,
            detail="Trusted Room context not found",
        )

    try:
        context = registry.resolve(context_reference)
    except TrustedContextError as error:
        code = error.args[0] if error.args else ""
        if code in {
            "room_routing_unavailable",
            "context_store_unavailable",
        }:
            raise HTTPException(
                status_code=503,
                detail="Room authorization dependency is unavailable",
            ) from error
        raise HTTPException(
            status_code=404,
            detail="Trusted Room context not found",
        ) from error

    try:
        membership = await membership_verifier.check(
            context.chat_id,
            actor.telegram_user_id,
        )
    except TelegramMembershipUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Telegram membership verification is unavailable",
        ) from error

    if not membership.allowed:
        raise HTTPException(
            status_code=403,
            detail="Telegram membership does not authorize Café access",
        )

    return CafeAuthorization(
        actor=actor,
        context=context,
        membership=membership,
    )


async def get_current_cafe_access(
    current_user: AuthenticatedTelegramActor = Depends(get_current_user),
    registry: TrustedContextRegistry = Depends(
        get_trusted_context_registry
    ),
    membership_verifier: TelegramMembershipVerifier = Depends(
        get_telegram_membership_verifier
    ),
) -> CafeAuthorization:
    """Full W01-C gate using authenticated start_param context."""
    return await authorize_cafe_access(
        current_user,
        current_user.start_param,
        registry,
        membership_verifier,
    )


__all__ = [
    "AuthenticatedTelegramActor",
    "CafeAuthorization",
    "authorize_cafe_access",
    "get_current_cafe_access",
    "get_current_user",
    "get_db",
    "get_telegram_membership_verifier",
    "get_trusted_context_registry",
]
