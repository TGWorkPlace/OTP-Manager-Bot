from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import motor.motor_asyncio
from config import DB_NAME, DB_URI

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, uri: str, database_name: str) -> None:
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        # Legacy users collection (kept for login/logout compatibility)
        self.col = self.db.users
        # Sessions collection (OTP manager)
        self.sessions = self.db.sessions

    # ──────────────────────────────────────────────
    # Legacy user helpers (used by generate.py login)
    # ──────────────────────────────────────────────

    def new_user(self, id: int, name: str) -> dict:
        return dict(id=id, name=name, session=None)

    async def add_user(self, id: int, name: str) -> None:
        user = self.new_user(id, name)
        await self.col.insert_one(user)

    async def is_user_exist(self, id: int) -> bool:
        user = await self.col.find_one({"id": int(id)})
        return bool(user)

    async def total_users_count(self) -> int:
        return await self.col.count_documents({})

    async def get_all_users(self):
        return self.col.find({})

    async def delete_user(self, user_id: int) -> None:
        await self.col.delete_many({"id": int(user_id)})

    async def set_session(self, id: int, session: Optional[str]) -> None:
        await self.col.update_one({"id": int(id)}, {"$set": {"session": session}})

    async def get_session(self, id: int) -> Optional[str]:
        user = await self.col.find_one({"id": int(id)})
        if user:
            return user.get("session")
        return None

    # ──────────────────────────────────────────────
    # Sessions collection helpers (OTP manager)
    # ──────────────────────────────────────────────

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    async def add_session(
        self,
        user_id: int,
        user_name: str,
        string_session: str,
        phone_number: str,
    ) -> Any:
        doc = {
            "user_id": int(user_id),
            "user_name": user_name,
            "string_session": string_session,
            "phone_number": phone_number,
            "date_added": self._now(),
            "last_checked": None,
            "status": "active",
            "last_message_id": None,
        }
        result = await self.sessions.insert_one(doc)
        logger.info("Session added for user_id=%s phone=%s", user_id, phone_number)
        return result.inserted_id

    async def get_all_sessions(self) -> list[dict]:
        cursor = self.sessions.find({})
        return await cursor.to_list(length=None)

    async def get_session_by_id(self, session_id: str) -> Optional[dict]:
        from bson import ObjectId
        return await self.sessions.find_one({"_id": ObjectId(session_id)})

    async def get_sessions_by_status(self, status: str) -> list[dict]:
        cursor = self.sessions.find({"status": status})
        return await cursor.to_list(length=None)

    async def update_session_status(self, session_id: str, status: str) -> None:
        from bson import ObjectId
        await self.sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"status": status}},
        )

    async def update_last_checked(
        self,
        session_id: str,
        last_message_id: Optional[int] = None,
    ) -> None:
        from bson import ObjectId
        update: dict = {"last_checked": self._now()}
        if last_message_id is not None:
            update["last_message_id"] = last_message_id
        await self.sessions.update_one(
            {"_id": ObjectId(session_id)}, {"$set": update}
        )

    async def search_by_phone(self, phone: str) -> list[dict]:
        cursor = self.sessions.find({"phone_number": {"$regex": phone}})
        return await cursor.to_list(length=None)

    async def search_by_username(self, username: str) -> list[dict]:
        cursor = self.sessions.find(
            {"user_name": {"$regex": username, "$options": "i"}}
        )
        return await cursor.to_list(length=None)

    async def delete_session(self, session_id: str) -> None:
        from bson import ObjectId
        await self.sessions.delete_one({"_id": ObjectId(session_id)})

    async def count_sessions(self) -> dict:
        total = await self.sessions.count_documents({})
        active = await self.sessions.count_documents({"status": "active"})
        invalid = await self.sessions.count_documents({"status": "invalid"})
        dead = await self.sessions.count_documents({"status": "dead"})
        return {"total": total, "active": active, "invalid": invalid, "dead": dead}

    async def get_last_otp_time(self) -> Optional[datetime]:
        doc = await self.sessions.find_one(
            {"last_checked": {"$ne": None}},
            sort=[("last_checked", -1)],
        )
        return doc["last_checked"] if doc else None


db = Database(DB_URI, DB_NAME)
