from app.adapters.youtube_search import SearchAdapter
from app.models.track import Track


class SearchService:
    def __init__(self, adapter: SearchAdapter):
        self.adapter = adapter

    async def search(self, query: str, limit: int = 20) -> list[Track]:
        query = query.strip()
        if not 1 <= len(query) <= 200:
            raise ValueError("La consulta debe tener entre 1 y 200 caracteres")
        limit = max(1, min(50, limit))
        return await self.adapter.search(query, limit)
