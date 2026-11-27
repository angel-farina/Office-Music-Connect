import asyncio
from urllib.parse import parse_qs, urlparse

from app.models.track import Track


class SearchAdapter:
    async def search(self, query: str, limit: int = 20) -> list[Track]:
        raise NotImplementedError


class YouTubeSearchAdapter(SearchAdapter):
    def __init__(self):
        self._api = None
        try:
            from ytmusicapi import YTMusic
            self._api = YTMusic()
        except Exception:
            self._api = None

    async def search(self, query: str, limit: int = 20) -> list[Track]:
        if self._api is None:
            raise RuntimeError(
                "ytmusicapi no esta disponible. Instale y revise los requisitos de uso."
            )
        results = await asyncio.to_thread(
            self._api.search,
            query,
            filter="songs",
            limit=limit,
        )
        tracks = []
        for item in results:
            video_id = item.get("videoId")
            if not video_id:
                continue
            artists = [artist.get("name") for artist in item.get("artists", []) if artist.get("name")]
            duration = self._duration_seconds(item.get("duration"))
            tracks.append(
                Track(
                    id=video_id,
                    title=item.get("title") or "Sin titulo",
                    artists=artists,
                    album=item.get("album", {}).get("name") if item.get("album") else None,
                    duration_seconds=duration,
                    thumbnail_url=self._thumbnail(item),
                    watch_url=f"https://music.youtube.com/watch?v={video_id}",
                )
            )
        return tracks

    @staticmethod
    def _thumbnail(item: dict) -> str | None:
        thumbnails = item.get("thumbnails") or []
        return thumbnails[-1].get("url") if thumbnails else None

    @staticmethod
    def _duration_seconds(value: str | None) -> float | None:
        if not value:
            return None
        try:
            parts = [int(part) for part in value.split(":")]
            return float(sum(part * (60 ** index) for index, part in enumerate(reversed(parts))))
        except Exception:
            return None
