from typing import Optional

from pydantic import BaseModel


class Track(BaseModel):
    id: str
    title: str
    artists: list[str] = []
    album: Optional[str] = None
    duration_seconds: Optional[float] = None
    thumbnail_url: Optional[str] = None
    watch_url: Optional[str] = None
    source: str = "youtube_music"
