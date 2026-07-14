"""Session storage for in-progress WhatsApp conversations.

Uses an in-memory dictionary by default. Swap ``InMemorySessionStore`` for a
Redis-backed implementation without changing the conversation service.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from app.services.whatsapp.schemas import WhatsAppSession

logger = logging.getLogger(__name__)


class SessionStore(ABC):
    """Abstract session store — implement for Redis or another backend."""

    @abstractmethod
    def get(self, phone: str) -> Optional[WhatsAppSession]:
        ...

    @abstractmethod
    def set(self, phone: str, session: WhatsAppSession) -> None:
        ...

    @abstractmethod
    def delete(self, phone: str) -> None:
        ...


class InMemorySessionStore(SessionStore):
    """Thread-unsafe in-memory fallback for local development."""

    def __init__(self) -> None:
        self._sessions: dict[str, WhatsAppSession] = {}

    def get(self, phone: str) -> Optional[WhatsAppSession]:
        return self._sessions.get(phone)

    def set(self, phone: str, session: WhatsAppSession) -> None:
        self._sessions[phone] = session
        logger.debug("Session saved for %s (step=%s)", phone, session.step.value)

    def delete(self, phone: str) -> None:
        if phone in self._sessions:
            del self._sessions[phone]
            logger.debug("Session deleted for %s", phone)


# ---------------------------------------------------------------------------
# Redis integration point (future):
# class RedisSessionStore(SessionStore):
#     def __init__(self, redis_url: str, ttl_seconds: int) -> None:
#         ...
#     def get(self, phone: str) -> Optional[WhatsAppSession]:
#         ...
#     def set(self, phone: str, session: WhatsAppSession) -> None:
#         ...
#     def delete(self, phone: str) -> None:
#         ...
# ---------------------------------------------------------------------------

_session_store: SessionStore = InMemorySessionStore()


def get_session_store() -> SessionStore:
    """Return the active session store instance."""
    return _session_store


def set_session_store(store: SessionStore) -> None:
    """Replace the global session store (e.g. with Redis in production)."""
    global _session_store
    _session_store = store
    logger.info("WhatsApp session store replaced with %s", type(store).__name__)
