"""Thread-safe in-memory session manager."""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from session.models import Session

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages user sessions with in-memory dict storage.

    Thread-safe — all public methods acquire a lock.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def get_or_create(self, user_id: str) -> Session:
        """Return existing session or create a new one."""
        with self._lock:
            if user_id not in self._sessions:
                session = Session(user_id=user_id)
                self._sessions[user_id] = session
                logger.info("Created new session for user %s", user_id)
            return self._sessions[user_id]

    def get(self, user_id: str) -> Optional[Session]:
        """Return session if it exists, else None."""
        with self._lock:
            return self._sessions.get(user_id)

    def update(self, session: Session) -> None:
        """Persist session changes (in-memory, so just overwrite)."""
        with self._lock:
            self._sessions[session.user_id] = session

    def delete(self, user_id: str) -> None:
        """Remove a session."""
        with self._lock:
            if user_id in self._sessions:
                del self._sessions[user_id]
                logger.info("Deleted session for user %s", user_id)

    def cleanup_expired(self, max_age_hours: int = 24) -> int:
        """Remove sessions older than *max_age_hours*. Returns count deleted."""
        cutoff = time.time() - max_age_hours * 3600
        with self._lock:
            expired = [
                uid for uid, s in self._sessions.items() if s.updated_at < cutoff
            ]
            for uid in expired:
                del self._sessions[uid]
        if expired:
            logger.info("Cleaned up %d expired sessions", len(expired))
        return len(expired)
