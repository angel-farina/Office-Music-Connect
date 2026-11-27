from app.models.track import Track
from pydantic import BaseModel


class QueueItem(BaseModel):
    queue_id: str
    track: Track
    requested_by: str | None = None
    added_at: str
