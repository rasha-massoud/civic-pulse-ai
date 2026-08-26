"""Idempotency store for inbound WhatsApp message IDs (Meta retries).

In-memory MVP. Swap for Redis/DB later without changing call sites.
"""

from __future__ import annotations

import logging
import threading
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class MessageProcessingState(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"


class MessageIdempotencyStore:
    """Track Meta WhatsApp message IDs to avoid duplicate processing."""

    def __init__(self) -> None:
        self._states: dict[str, MessageProcessingState] = {}
        self._lock = threading.Lock()

    def try_acquire(self, message_id: str) -> bool:
        """Mark message as processing if not already processing/completed.

        Returns True when this worker should process the message.
        Returns False for duplicates (already processing or completed).
        Failed jobs call ``mark_failed`` so Meta retries can re-acquire.
        """
        message_id = (message_id or "").strip()
        if not message_id:
            return False

        with self._lock:
            state = self._states.get(message_id)
            if state in (MessageProcessingState.PROCESSING, MessageProcessingState.COMPLETED):
                return False
            self._states[message_id] = MessageProcessingState.PROCESSING
            return True

    def mark_completed(self, message_id: str) -> None:
        message_id = (message_id or "").strip()
        if not message_id:
            return
        with self._lock:
            self._states[message_id] = MessageProcessingState.COMPLETED

    def mark_failed(self, message_id: str) -> None:
        """Allow a later Meta retry to reprocess this message."""
        message_id = (message_id or "").strip()
        if not message_id:
            return
        with self._lock:
            current = self._states.get(message_id)
            if current == MessageProcessingState.PROCESSING:
                del self._states[message_id]

    def get_state(self, message_id: str) -> Optional[MessageProcessingState]:
        with self._lock:
            return self._states.get(message_id)

    def clear(self) -> None:
        with self._lock:
            self._states.clear()


_store: MessageIdempotencyStore = MessageIdempotencyStore()


def get_idempotency_store() -> MessageIdempotencyStore:
    return _store


def set_idempotency_store(store: MessageIdempotencyStore) -> None:
    global _store
    _store = store
    logger.info("WhatsApp idempotency store replaced with %s", type(store).__name__)
