from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel

from app.models.track import Track


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PlayerState(BaseModel):
    connected: bool
    service: str = "youtube_music"
    is_playing: bool = False
    current_track: Optional[Track] = None
    position_seconds: float = 0
    duration_seconds: Optional[float] = None
    volume: Optional[int] = None
    updated_at: str
