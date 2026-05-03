"""Encrypted API key storage for dynamic agent configuration."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from sqlalchemy import DateTime, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

log = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet
    from app.config import get_settings
    key = get_settings().encryption_key
    if not key:
        # Auto-generate and warn
        key = Fernet.generate_key().decode()
        log.warning("No ENCRYPTION_KEY set -- generated ephemeral key (keys will not survive restart)")
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
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    key_name: Mapped[str] = mapped_column(String(128), nullable=False)
    encrypted_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


async def store_key(session: AsyncSession, provider: str, label: str, raw_key: str) -> int:
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
    rows = (await session.execute(
        select(ApiKeyStore).order_by(ApiKeyStore.id)
    )).scalars().all()
    return [{"id": r.id, "provider": r.provider, "label": r.key_name} for r in rows]


async def delete_key(session: AsyncSession, key_id: int) -> bool:
    """Delete a stored key. Returns True if found and deleted."""
    entry = await session.get(ApiKeyStore, key_id)
    if entry is None:
        return False
    await session.delete(entry)
    return True
