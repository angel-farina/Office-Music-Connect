import asyncio
import logging

from app.adapters.browser_base import BrowserAdapter
from app.models.player import PlayerState
from app.services.events import EventHub
from app.services.queue_service import QueueService


LOGGER = logging.getLogger(__name__)


class PlayerService:
    def __init__(self, adapter: BrowserAdapter, events: EventHub):
        self.adapter = adapter
        self.events = events
        self._monitor_task: asyncio.Task | None = None
        self._next_lock = asyncio.Lock()

    async def start(self) -> None:
        await self.adapter.connect()
        self._monitor_task = asyncio.create_task(self._monitor())

    async def stop(self) -> None:
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        await self.adapter.close()

    async def get_state(self) -> PlayerState:
        return await self.adapter.get_state()

    async def play(self) -> PlayerState:
        state = await self.adapter.play()
        await self.events.publish("player.state", state.model_dump())
        await self.events.publish("command.accepted", {"command": "play"})
        return state

    async def pause(self) -> PlayerState:
        state = await self.adapter.pause()
        await self.events.publish("player.state", state.model_dump())
        await self.events.publish("command.accepted", {"command": "pause"})
        return state

    async def next(self, queue: QueueService | None = None) -> PlayerState:
        async with self._next_lock:
            if queue is not None:
                item = queue.peek_next()
                if item:
                    if not item.track.watch_url:
                        raise RuntimeError(
                            "El siguiente elemento de la cola no tiene una URL reproducible"
                        )
                    state = await self.play_url(item.track.watch_url)
                    if not state.connected:
                        raise RuntimeError("El reproductor no confirmo la reproduccion del tema en cola")
                    await queue.remove(item.queue_id)
                    await self.events.publish("command.accepted", {"command": "next"})
                    return state

            state = await self.adapter.next()
            await self.events.publish("player.state", state.model_dump())
            await self.events.publish("track_changed", state.model_dump())
            await self.events.publish("command.accepted", {"command": "next"})
            return state

    async def previous(self) -> PlayerState:
        state = await self.adapter.previous()
        await self.events.publish("player.state", state.model_dump())
        await self.events.publish("track_changed", state.model_dump())
        await self.events.publish("command.accepted", {"command": "previous"})
        return state

    async def set_volume(self, volume: int) -> PlayerState:
        state = await self.adapter.set_volume(volume)
        await self.events.publish("player.state", state.model_dump())
        return state

    async def seek(self, position_seconds: float) -> PlayerState:
        state = await self.adapter.seek(position_seconds)
        await self.events.publish("player.state", state.model_dump())
        return state

    async def play_url(self, url: str) -> PlayerState:
        state = await self.adapter.play_url(url)
        await self.events.publish("player.state", state.model_dump())
        await self.events.publish("track_changed", state.model_dump())
        return state

    async def _monitor(self) -> None:
        delay = 1
        while True:
            try:
                state = await self.adapter.get_state()
                await self.events.publish("player.state", state.model_dump())
                if state.connected:
                    delay = 1
                else:
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 30)
                    await self.adapter.connect()
                    continue
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                LOGGER.warning("Error monitorizando reproductor: %s", exc)
            await asyncio.sleep(delay)
