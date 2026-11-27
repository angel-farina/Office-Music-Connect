import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from app.models.player import PlayerState, utc_now
from app.models.track import Track
from app.services.events import EventHub
from app.services.player_service import PlayerService
from app.services.queue_service import QueueService


def test_queue_add_remove_reorder_clear():
    with tempfile.TemporaryDirectory() as directory:
        queue = QueueService(Path(directory) / "queue.db", EventHub())
        first = Track(id="1", title="Uno")
        second = Track(id="2", title="Dos")

        async def exercise():
            first_item = await queue.add(first)
            second_item = await queue.add(second)
            assert [item.track.title for item in queue.list()] == ["Uno", "Dos"]
            assert await queue.reorder([second_item.queue_id, first_item.queue_id])
            assert [item.track.title for item in queue.list()] == ["Dos", "Uno"]
            assert await queue.remove(first_item.queue_id)
            await queue.clear()
            assert queue.list() == []

        asyncio.run(exercise())


def test_next_plays_and_removes_first_queued_track():
    with tempfile.TemporaryDirectory() as directory:
        events = EventHub()
        queue = QueueService(Path(directory) / "queue.db", events)
        adapter = Mock()
        adapter.play_url = AsyncMock(
            return_value=PlayerState(connected=True, is_playing=True, updated_at=utc_now())
        )
        adapter.next = AsyncMock()
        player = PlayerService(adapter, events)
        track_url = "https://music.youtube.com/watch?v=queued-track"

        async def exercise():
            await queue.add(Track(id="queued-track", title="En cola", watch_url=track_url))
            await player.next(queue)

        asyncio.run(exercise())

        adapter.play_url.assert_awaited_once_with(track_url)
        adapter.next.assert_not_awaited()
        assert queue.list() == []


def test_next_uses_youtube_controls_when_queue_is_empty():
    events = EventHub()
    queue = Mock()
    queue.peek_next.return_value = None
    adapter = Mock()
    adapter.next = AsyncMock(
        return_value=PlayerState(connected=True, is_playing=True, updated_at=utc_now())
    )
    player = PlayerService(adapter, events)

    asyncio.run(player.next(queue))

    adapter.next.assert_awaited_once()


def test_monitor_does_not_advance_queue_on_track_end(monkeypatch):
    with tempfile.TemporaryDirectory() as directory:
        events = EventHub()
        queue = QueueService(Path(directory) / "queue.db", events)
        adapter = Mock()
        adapter.get_state = AsyncMock(
            return_value=PlayerState(connected=True, is_playing=False, updated_at=utc_now())
        )
        adapter.next = AsyncMock()
        adapter.play_url = AsyncMock()
        player = PlayerService(adapter, events)

        async def exercise():
            await queue.add(Track(id="queued", title="En cola"))

            async def stop_after_first_poll(_delay):
                raise asyncio.CancelledError

            monkeypatch.setattr(asyncio, "sleep", stop_after_first_poll)
            try:
                await player._monitor()
            except asyncio.CancelledError:
                pass

        asyncio.run(exercise())

        adapter.next.assert_not_awaited()
        adapter.play_url.assert_not_awaited()
        assert [item.track.id for item in queue.list()] == ["queued"]
