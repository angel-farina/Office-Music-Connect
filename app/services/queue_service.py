from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

from app.models.queue import QueueItem
from app.models.track import Track
from app.services.events import EventHub


class QueueService:
    def __init__(self, database_path: Path, events: EventHub):
        self.database_path = database_path
        self.events = events
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS queue (
                    position INTEGER PRIMARY KEY,
                    queue_id TEXT NOT NULL UNIQUE,
                    track_json TEXT NOT NULL,
                    requested_by TEXT,
                    added_at TEXT NOT NULL
                )
                """
            )

    def list(self) -> list[QueueItem]:
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(
                "SELECT queue_id, track_json, requested_by, added_at FROM queue ORDER BY position"
            ).fetchall()
        return [
            QueueItem(
                queue_id=row["queue_id"],
                track=Track.model_validate_json(row["track_json"]),
                requested_by=row["requested_by"],
                added_at=row["added_at"],
            )
            for row in rows
        ]

    async def add(self, track: Track, requested_by: str | None = None) -> QueueItem:
        item = QueueItem(
            queue_id=str(uuid.uuid4()),
            track=track,
            requested_by=requested_by,
            added_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        )
        with closing(self._connect()) as connection, connection:
            position = connection.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM queue").fetchone()[0]
            connection.execute(
                "INSERT INTO queue(position, queue_id, track_json, requested_by, added_at) VALUES (?, ?, ?, ?, ?)",
                (position, item.queue_id, track.model_dump_json(), item.requested_by, item.added_at),
            )
        await self.events.publish("queue.updated", [item.model_dump() for item in self.list()])
        return item

    async def remove(self, queue_id: str) -> bool:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute("DELETE FROM queue WHERE queue_id = ?", (queue_id,))
            if cursor.rowcount:
                self._normalize_positions(connection)
            found = cursor.rowcount > 0
        if found:
            await self.events.publish("queue.updated", [item.model_dump() for item in self.list()])
        return found

    async def reorder(self, queue_ids: list[str]) -> list[QueueItem]:
        if len(queue_ids) != len(set(queue_ids)):
            raise ValueError("queue_ids no puede contener duplicados")
        current = self.list()
        current_ids = {item.queue_id for item in current}
        if set(queue_ids) != current_ids:
            raise ValueError("La lista de orden debe contener todos los elementos de la cola")
        with closing(self._connect()) as connection, connection:
            rows = connection.execute("SELECT queue_id FROM queue").fetchall()
            for offset, row in enumerate(rows):
                connection.execute(
                    "UPDATE queue SET position = ? WHERE queue_id = ?",
                    (-offset - 1, row["queue_id"]),
                )
            for position, queue_id in enumerate(queue_ids):
                connection.execute("UPDATE queue SET position = ? WHERE queue_id = ?", (position, queue_id))
        items = self.list()
        await self.events.publish("queue.updated", [item.model_dump() for item in items])
        return items

    async def clear(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("DELETE FROM queue")
        await self.events.publish("queue.updated", [])

    def peek_next(self) -> QueueItem | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT queue_id, track_json, requested_by, added_at FROM queue ORDER BY position LIMIT 1"
            ).fetchone()
        if not row:
            return None
        return QueueItem(
            queue_id=row["queue_id"],
            track=Track.model_validate_json(row["track_json"]),
            requested_by=row["requested_by"],
            added_at=row["added_at"],
        )

    async def pop_next(self) -> QueueItem | None:
        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT queue_id, track_json, requested_by, added_at FROM queue ORDER BY position LIMIT 1"
            ).fetchone()
            if not row:
                return None
            connection.execute("DELETE FROM queue WHERE queue_id = ?", (row["queue_id"],))
            self._normalize_positions(connection)
        item = QueueItem(
            queue_id=row["queue_id"],
            track=Track.model_validate_json(row["track_json"]),
            requested_by=row["requested_by"],
            added_at=row["added_at"],
        )
        await self.events.publish("queue.updated", [item.model_dump() for item in self.list()])
        return item

    @staticmethod
    def _normalize_positions(connection: sqlite3.Connection) -> None:
        rows = connection.execute("SELECT queue_id FROM queue ORDER BY position").fetchall()
        for position, row in enumerate(rows):
            connection.execute("UPDATE queue SET position = ? WHERE queue_id = ?", (position, row["queue_id"]))
