"""SQLite 数据库持久化层"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "wechat_bot.db"


class Database:
    """SQLite 数据库管理器，线程安全"""

    _instance: Optional[Database] = None
    _lock = threading.Lock()

    def __new__(cls) -> Database:
        """单例模式，确保只有一个数据库实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        self._local = threading.local()
        self._init_db()
        self._initialized = True
        logger.info("Database initialized at %s", DB_PATH)

    def _get_connection(self) -> sqlite3.Connection:
        """获取线程本地的数据库连接"""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(DB_PATH),
                check_same_thread=False,
                timeout=30.0,
            )
            self._local.connection.row_factory = sqlite3.Row
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA synchronous=NORMAL")
        return self._local.connection

    @contextmanager
    def get_cursor(self):
        """获取数据库游标的上下文管理器"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    def _init_db(self) -> None:
        """初始化数据库表结构"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    identity TEXT,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_messages INTEGER DEFAULT 0,
                    metadata JSON DEFAULT '{}'
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    state TEXT DEFAULT 'new',
                    stage TEXT DEFAULT 'unknown',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSON DEFAULT '{}',
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSON DEFAULT '{}',
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    preferences JSON DEFAULT '{}',
                    purchase_history JSON DEFAULT '[]',
                    issues_history JSON DEFAULT '[]',
                    conversation_summary TEXT,
                    key_info JSON DEFAULT '{}',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_user_id 
                ON sessions(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_history_session_id 
                ON chat_history(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_history_created_at 
                ON chat_history(created_at)
            """)

    def get_or_create_user(
        self, user_id: str, identity: Optional[str] = None
    ) -> dict[str, Any]:
        """获取或创建用户"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()

            if row:
                cursor.execute(
                    "UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (user_id,),
                )
                return dict(row)

            cursor.execute(
                """INSERT INTO users (user_id, identity, first_seen, last_seen) 
                   VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                (user_id, identity),
            )

            cursor.execute("INSERT INTO user_profiles (user_id) VALUES (?)", (user_id,))

            logger.info("Created new user: %s", user_id)
            return {
                "user_id": user_id,
                "identity": identity,
                "total_messages": 0,
                "metadata": {},
            }

    def update_user_message_count(self, user_id: str) -> None:
        """更新用户消息计数"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """UPDATE users 
                   SET total_messages = total_messages + 1, 
                       last_seen = CURRENT_TIMESTAMP 
                   WHERE user_id = ?""",
                (user_id,),
            )

    def create_session(
        self, session_id: str, user_id: str, state: str = "new"
    ) -> dict[str, Any]:
        """创建新会话"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO sessions (session_id, user_id, state, stage) 
                   VALUES (?, ?, ?, 'unknown')""",
                (session_id, user_id, state),
            )
            logger.info("Created session %s for user %s", session_id, user_id)
            return {
                "session_id": session_id,
                "user_id": user_id,
                "state": state,
                "stage": "unknown",
            }

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        """获取会话"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_active_session(self, user_id: str) -> Optional[dict[str, Any]]:
        """获取用户的活跃会话"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """SELECT * FROM sessions 
                   WHERE user_id = ? AND state != 'ended'
                   ORDER BY updated_at DESC LIMIT 1""",
                (user_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_session(
        self,
        session_id: str,
        state: Optional[str] = None,
        stage: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """更新会话"""
        updates = []
        params = []

        if state is not None:
            updates.append("state = ?")
            params.append(state)
        if stage is not None:
            updates.append("stage = ?")
            params.append(stage)
        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata, ensure_ascii=False))

        if not updates:
            return

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(session_id)

        with self.get_cursor() as cursor:
            cursor.execute(
                f"UPDATE sessions SET {', '.join(updates)} WHERE session_id = ?", params
            )

    def end_session(self, session_id: str) -> None:
        """结束会话"""
        self.update_session(session_id, state="ended")

    def add_chat_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[int]:
        """添加聊天消息"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO chat_history (session_id, role, content, metadata) 
                   VALUES (?, ?, ?, ?)""",
                (
                    session_id,
                    role,
                    content,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
            return cursor.lastrowid

    def get_chat_history(
        self,
        session_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """获取聊天历史"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """SELECT * FROM chat_history 
                   WHERE session_id = ? 
                   ORDER BY created_at DESC 
                   LIMIT ? OFFSET ?""",
                (session_id, limit, offset),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in reversed(rows)]

    def get_recent_messages(
        self,
        session_id: str,
        max_turns: int = 10,
    ) -> list[dict[str, str]]:
        """获取最近的聊天消息，格式化为 AI 对话格式"""
        history = self.get_chat_history(session_id, limit=max_turns * 2)
        return [{"role": msg["role"], "content": msg["content"]} for msg in history]

    def get_message_count(self, session_id: str) -> int:
        """获取会话消息数量"""
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) as count FROM chat_history WHERE session_id = ?",
                (session_id,),
            )
            row = cursor.fetchone()
            return row["count"] if row else 0

    def get_user_profile(self, user_id: str) -> dict[str, Any]:
        """获取用户画像"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()

            if not row:
                cursor.execute(
                    "INSERT INTO user_profiles (user_id) VALUES (?)", (user_id,)
                )
                return {
                    "user_id": user_id,
                    "preferences": {},
                    "purchase_history": [],
                    "issues_history": [],
                    "conversation_summary": None,
                    "key_info": {},
                }

            return {
                "user_id": row["user_id"],
                "preferences": json.loads(row["preferences"])
                if row["preferences"]
                else {},
                "purchase_history": json.loads(row["purchase_history"])
                if row["purchase_history"]
                else [],
                "issues_history": json.loads(row["issues_history"])
                if row["issues_history"]
                else [],
                "conversation_summary": row["conversation_summary"],
                "key_info": json.loads(row["key_info"]) if row["key_info"] else {},
            }

    def update_user_profile(
        self,
        user_id: str,
        preferences: Optional[dict[str, Any]] = None,
        purchase_history: Optional[list[dict[str, Any]]] = None,
        issues_history: Optional[list[dict[str, Any]]] = None,
        conversation_summary: Optional[str] = None,
        key_info: Optional[dict[str, Any]] = None,
    ) -> None:
        """更新用户画像"""
        updates = []
        params = []

        if preferences is not None:
            updates.append("preferences = ?")
            params.append(json.dumps(preferences, ensure_ascii=False))
        if purchase_history is not None:
            updates.append("purchase_history = ?")
            params.append(json.dumps(purchase_history, ensure_ascii=False))
        if issues_history is not None:
            updates.append("issues_history = ?")
            params.append(json.dumps(issues_history, ensure_ascii=False))
        if conversation_summary is not None:
            updates.append("conversation_summary = ?")
            params.append(conversation_summary)
        if key_info is not None:
            updates.append("key_info = ?")
            params.append(json.dumps(key_info, ensure_ascii=False))

        if not updates:
            return

        updates.append("last_updated = CURRENT_TIMESTAMP")
        params.append(user_id)

        with self.get_cursor() as cursor:
            cursor.execute(
                f"UPDATE user_profiles SET {', '.join(updates)} WHERE user_id = ?",
                params,
            )

    def add_to_purchase_history(self, user_id: str, purchase: dict[str, Any]) -> None:
        """添加购买记录"""
        profile = self.get_user_profile(user_id)
        history = profile.get("purchase_history", [])
        history.append(
            {
                **purchase,
                "timestamp": datetime.now().isoformat(),
            }
        )
        history = history[-50:]
        self.update_user_profile(user_id, purchase_history=history)

    def add_to_issues_history(self, user_id: str, issue: dict[str, Any]) -> None:
        """添加问题记录"""
        profile = self.get_user_profile(user_id)
        history = profile.get("issues_history", [])
        history.append(
            {
                **issue,
                "timestamp": datetime.now().isoformat(),
                "resolved": False,
            }
        )
        history = history[-50:]
        self.update_user_profile(user_id, issues_history=history)

    def update_key_info(self, user_id: str, key: str, value: Any) -> None:
        """更新关键信息（如地址、电话等）"""
        profile = self.get_user_profile(user_id)
        key_info = profile.get("key_info", {})
        key_info[key] = {
            "value": value,
            "updated_at": datetime.now().isoformat(),
        }
        self.update_user_profile(user_id, key_info=key_info)

    def cleanup_old_sessions(self, days: int = 30) -> int:
        """清理旧会话数据"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """DELETE FROM chat_history 
                   WHERE session_id IN (
                       SELECT session_id FROM sessions 
                       WHERE updated_at < datetime('now', ?)
                   )""",
                (f"-{days} days",),
            )

            cursor.execute(
                """DELETE FROM sessions 
                   WHERE updated_at < datetime('now', ?)""",
                (f"-{days} days",),
            )

            deleted = cursor.rowcount
            if deleted > 0:
                logger.info("Cleaned up %d old sessions", deleted)
            return deleted

    def vacuum(self) -> None:
        """压缩数据库"""
        with self.get_cursor() as cursor:
            cursor.execute("VACUUM")
        logger.info("Database vacuumed")

    def get_stats(self) -> dict[str, Any]:
        """获取数据库统计信息"""
        with self.get_cursor() as cursor:
            stats = {}

            cursor.execute("SELECT COUNT(*) as count FROM users")
            stats["total_users"] = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM sessions")
            stats["total_sessions"] = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM chat_history")
            stats["total_messages"] = cursor.fetchone()["count"]

            cursor.execute(
                "SELECT COUNT(*) as count FROM sessions WHERE state != 'ended'"
            )
            stats["active_sessions"] = cursor.fetchone()["count"]

            return stats
