"""Encrypted API key storage for dynamic agent configuration."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from cryptography.fernet import Fernet
from sqlalchemy import DateTime, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

log = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet
    from app.config import get_settings

    key = get_settings().encryption_key
    if not key:
        # Auto-generate and warn
        key = Fernet.generate_key().decode()
        log.warning(
            "No ENCRYPTION_KEY set -- generated ephemeral key (keys will not survive restart)"
        )
    # Fernet requires url-safe base64 key; if user provides a passphrase, derive one
    try:
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        # Fallback: generate a key from the provided string via hash
        import base64
        import hashlib

        derived = base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
        _fernet = Fernet(derived)
    return _fernet


class ApiKeyStore(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # API keys are BYOK and scoped to a single session (never shared across sessions).
    session_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, default="cli"
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    key_name: Mapped[str] = mapped_column(String(128), nullable=False)
    encrypted_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


async def store_key(
    session: AsyncSession, provider: str, label: str, raw_key: str
) -> int:
    """Encrypt and store an API key, returning its ID."""
    f = _get_fernet()
    encrypted = f.encrypt(raw_key.encode()).decode()
    entry = ApiKeyStore(provider=provider, key_name=label, encrypted_key=encrypted)
    session.add(entry)
    await session.flush()
    return entry.id


async def get_key(session: AsyncSession, key_id: int) -> str | None:
    """Decrypt and return an API key by ID."""
    entry = await session.get(ApiKeyStore, key_id)
    if entry is None:
        return None
    f = _get_fernet()
    return f.decrypt(entry.encrypted_key.encode()).decode()


async def list_keys(session: AsyncSession) -> list[dict]:
    """List stored keys (ID, provider, label only -- never raw keys)."""
    rows = (
        (await session.execute(select(ApiKeyStore).order_by(ApiKeyStore.id)))
        .scalars()
        .all()
    )
    return [{"id": r.id, "provider": r.provider, "label": r.key_name} for r in rows]


async def delete_key(session: AsyncSession, key_id: int) -> bool:
    """Delete a stored key. Returns True if found and deleted."""
    entry = await session.get(ApiKeyStore, key_id)
    if entry is None:
        return False
    await session.delete(entry)
    return True


# --- Per-session BYOK helpers --------------------------------------------------


async def store_session_key(
    session: AsyncSession, session_id: str, provider: str, raw_key: str
) -> None:
    """Encrypt and store a provider key scoped to a session (overwrites prior)."""
    from sqlalchemy import delete as sa_delete

    f = _get_fernet()
    encrypted = f.encrypt(raw_key.encode()).decode()
    # Replace any existing key for this (session, provider).
    await session.execute(
        sa_delete(ApiKeyStore).where(
            ApiKeyStore.session_id == session_id, ApiKeyStore.provider == provider
        )
    )
    session.add(
        ApiKeyStore(
            session_id=session_id,
            provider=provider,
            key_name=f"{provider} key",
            encrypted_key=encrypted,
        )
    )
    await session.flush()


async def get_session_keys(session: AsyncSession, session_id: str) -> dict[str, str]:
    """Return decrypted ``{provider: raw_key}`` for every key stored on a session."""
    rows = (
        (
            await session.execute(
                select(ApiKeyStore).where(ApiKeyStore.session_id == session_id)
            )
        )
        .scalars()
        .all()
    )
    f = _get_fernet()
    out: dict[str, str] = {}
    for r in rows:
        try:
            out[r.provider] = f.decrypt(r.encrypted_key.encode()).decode()
        except Exception:  # noqa: BLE001
            log.warning(
                "Failed to decrypt key for session=%s provider=%s", session_id, r.provider
            )
    return out


async def delete_session_keys(session: AsyncSession, session_id: str) -> None:
    """Delete every stored key for a session."""
    from sqlalchemy import delete as sa_delete

    await session.execute(
        sa_delete(ApiKeyStore).where(ApiKeyStore.session_id == session_id)
    )
