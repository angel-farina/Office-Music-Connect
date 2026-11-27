from abc import ABC, abstractmethod
from app.models.player import PlayerState


class BrowserAdapter(ABC):
    @abstractmethod
    async def connect(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_state(self) -> PlayerState:
        raise NotImplementedError

    @abstractmethod
    async def play(self) -> PlayerState:
        raise NotImplementedError

    @abstractmethod
    async def pause(self) -> PlayerState:
        raise NotImplementedError

    @abstractmethod
    async def next(self) -> PlayerState:
        raise NotImplementedError

    @abstractmethod
    async def previous(self) -> PlayerState:
        raise NotImplementedError

    @abstractmethod
    async def set_volume(self, volume: int) -> PlayerState:
        raise NotImplementedError

    @abstractmethod
    async def seek(self, position_seconds: float) -> PlayerState:
        raise NotImplementedError

    @abstractmethod
    async def play_url(self, url: str) -> PlayerState:
        raise NotImplementedError
