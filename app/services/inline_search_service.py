from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.db.database import Database
from app.repositories.shops_repo import ShopsRepo
from app.services.search_service import SearchService, SearchResult


@dataclass(frozen=True)
class InlineSearchResult:
    product: dict
    shop: dict
    score: float


class InlineSearchService:
    def __init__(self, db: Database):
        self.db = db
        self.search_service = SearchService(db)

    async def search(self, query: str, limit: int = 20) -> Sequence[InlineSearchResult]:
        query = query.strip()
        if not query:
            return []

        shops = await ShopsRepo(self.db).list_active()
        if not shops:
            return []

        results: list[InlineSearchResult] = []
        for shop in shops:
            items: Sequence[SearchResult] = await self.search_service.search_products(
                shop_id=shop["id"],
                query=query,
                active_only=True,
                limit=limit,
            )
            for item in items:
                results.append(
                    InlineSearchResult(product=item.product, shop=shop, score=item.score)
                )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]
