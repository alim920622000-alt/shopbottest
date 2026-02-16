from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user, get_db
from app.api.schemas import BusinessType, CursorPage
from app.db.database import Database
from app.repositories.categories_repo import CategoriesRepo
from app.repositories.shops_repo import ShopsRepo

router = APIRouter(tags=["catalog"])


def _parse_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return max(int(cursor), 0)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Некорректный cursor") from exc


def _build_next_cursor(items: list[dict], limit: int) -> str | None:
    if len(items) <= limit:
        return None
    return str(items[limit - 1]["id"])


@router.get("/catalog/merchants", response_model=CursorPage)
async def list_merchants(
    type: BusinessType = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    _: object = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> CursorPage:
    cursor_id = _parse_cursor(cursor)
    items = list(await ShopsRepo(db).list_active(type))
    filtered = [row for row in items if int(row["id"]) > cursor_id]
    page = filtered[: limit + 1]
    next_cursor = _build_next_cursor(page, limit)
    return CursorPage(items=page[:limit], next_cursor=next_cursor)


@router.get("/catalog/{merchant_id}/categories", response_model=CursorPage)
async def list_categories(
    merchant_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    _: object = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> CursorPage:
    cursor_id = _parse_cursor(cursor)
    repo = CategoriesRepo(db)
    items = list(await repo.list_for_shop(merchant_id, active_only=True))
    filtered = [row for row in items if int(row["id"]) > cursor_id]
    page = filtered[: limit + 1]
    next_cursor = _build_next_cursor(page, limit)
    return CursorPage(items=page[:limit], next_cursor=next_cursor)


@router.get("/catalog/categories/{category_id}/items", response_model=CursorPage)
async def list_category_items(
    category_id: int,
    merchant_id: int = Query(..., gt=0),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    _: object = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> CursorPage:
    cursor_id = _parse_cursor(cursor)
    async with db.conn() as conn:
        cur = await conn.execute(
            """
            SELECT *
            FROM products
            WHERE shop_id=? AND category_id=? AND is_active=1 AND id>?
            ORDER BY id ASC
            LIMIT ?
            """,
            (merchant_id, category_id, cursor_id, limit + 1),
        )
        page = [dict(r) for r in await cur.fetchall()]
    next_cursor = _build_next_cursor(page, limit)
    return CursorPage(items=page[:limit], next_cursor=next_cursor)


@router.get("/search", response_model=CursorPage)
async def search_products(
    q: str = Query(..., min_length=1),
    type: BusinessType = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    _: object = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> CursorPage:
    cursor_id = _parse_cursor(cursor)
    like = f"%{q.strip().lower()}%"
    async with db.conn() as conn:
        cur = await conn.execute(
            """
            SELECT p.*, s.name AS merchant_name, s.business_type
            FROM products p
            JOIN shops s ON s.id = p.shop_id
            WHERE s.business_type=?
              AND p.is_active=1
              AND p.id>?
              AND (
                lower(p.name) LIKE ?
                OR lower(COALESCE(p.description, '')) LIKE ?
                OR lower(COALESCE(p.keywords_norm, '')) LIKE ?
              )
            ORDER BY p.id ASC
            LIMIT ?
            """,
            (type, cursor_id, like, like, like, limit + 1),
        )
        page = [dict(r) for r in await cur.fetchall()]
    next_cursor = _build_next_cursor(page, limit)
    return CursorPage(items=page[:limit], next_cursor=next_cursor)
