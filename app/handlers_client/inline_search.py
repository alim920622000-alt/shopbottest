import logging

from aiogram import Router
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent

from app.db.database import Database
from app.services.inline_search_service import InlineSearchService

router = Router()
logger = logging.getLogger(__name__)


@router.inline_query()
async def inline_search(inline_query: InlineQuery, db: Database):
    query = (inline_query.query or "").strip()
    if not query:
        await inline_query.answer([], cache_time=1, is_personal=True)
        return

    service = InlineSearchService(db)
    results = await service.search(query, limit=30)
    if not results:
        await inline_query.answer([], cache_time=5, is_personal=True)
        return

    articles: list[InlineQueryResultArticle] = []
    for item in results:
        product = item.product
        shop = item.shop
        price = product.get("price")
        price_text = f"{price}" if price is not None else "—"
        title = product.get("name") or "Товар"
        description_parts = []
        if price is not None:
            description_parts.append(price_text)
        if shop.get("name"):
            description_parts.append(shop["name"])
        description = " • ".join(description_parts)
        message_text = (
            f"🛒 {title}\n"
            f"💰 {price_text}\n"
            f"🏬 {shop.get('name', 'Точка')}"
        )
        articles.append(
            InlineQueryResultArticle(
                id=str(product.get("id")),
                title=title,
                description=description,
                input_message_content=InputTextMessageContent(message_text),
            )
        )

    await inline_query.answer(articles, cache_time=5, is_personal=True)
