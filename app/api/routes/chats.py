from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import CurrentUser, get_current_user, get_db
from app.api.schemas import CursorPage, SendChatMessageRequest
from app.db.database import Database
from app.handlers_admin_restaurant.utils import get_admin_restaurant_ids
from app.handlers_admin_shop.utils import get_admin_shop_ids
from app.repositories.chat_reads_repo import ChatReadsRepo
from app.repositories.chat_repo import ChatRepo
from app.repositories.orders_repo import OrdersRepo

router = APIRouter(prefix="/chats", tags=["chats"])


async def _allowed_shop_ids(db: Database, user: CurrentUser) -> set[int]:
    if user.role == "admin_shop":
        return set(await get_admin_shop_ids(db, user.user_id))
    if user.role == "admin_restaurant":
        return set(await get_admin_restaurant_ids(db, user.user_id))
    return set()


async def _assert_order_chat_access(db: Database, user: CurrentUser, order_id: int) -> dict:
    order = await OrdersRepo(db).get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    if user.role == "client":
        if int(order["client_user_id"]) != user.user_id:
            raise HTTPException(status_code=403, detail="Нет доступа к чату")
        return order

    allowed = await _allowed_shop_ids(db, user)
    if int(order["shop_id"]) not in allowed:
        raise HTTPException(status_code=403, detail="Нет доступа к чату")
    return order


def _parse_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return max(int(cursor), 0)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Некорректный cursor") from exc


@router.get("", response_model=CursorPage)
async def list_chats(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> CursorPage:
    cursor_id = _parse_cursor(cursor)
    where = ["o.id > ?"]
    params: list[object] = [cursor_id]

    if user.role == "client":
        where.append("o.client_user_id = ?")
        params.append(user.user_id)
    else:
        allowed = await _allowed_shop_ids(db, user)
        if not allowed:
            return CursorPage(items=[], next_cursor=None)
        placeholders = ",".join(["?"] * len(allowed))
        where.append(f"o.shop_id IN ({placeholders})")
        params.extend(sorted(allowed))

    where_sql = " AND ".join(where)
    async with db.conn() as conn:
        cur = await conn.execute(
            f"""
            SELECT o.id AS order_id, MAX(m.id) AS last_message_id, MAX(m.created_at) AS last_message_at
            FROM orders o
            JOIN order_chat_messages m ON m.order_id = o.id
            WHERE {where_sql}
            GROUP BY o.id
            ORDER BY o.id ASC
            LIMIT ?
            """,
            (*params, limit + 1),
        )
        page = [dict(r) for r in await cur.fetchall()]

    next_cursor = str(page[limit - 1]["order_id"]) if len(page) > limit else None
    return CursorPage(items=page[:limit], next_cursor=next_cursor)


@router.get("/{order_id}/messages", response_model=CursorPage)
async def list_messages(
    order_id: int,
    limit: int = Query(default=30, ge=1, le=100),
    cursor: str | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> CursorPage:
    await _assert_order_chat_access(db, user, order_id)
    cursor_id = _parse_cursor(cursor)

    async with db.conn() as conn:
        cur = await conn.execute(
            """
            SELECT id, sender_user_id, sender_role, message_text, created_at
            FROM order_chat_messages
            WHERE order_id=? AND id>?
            ORDER BY id ASC
            LIMIT ?
            """,
            (order_id, cursor_id, limit + 1),
        )
        page = [dict(r) for r in await cur.fetchall()]

    next_cursor = str(page[limit - 1]["id"]) if len(page) > limit else None
    return CursorPage(items=page[:limit], next_cursor=next_cursor)


@router.post("/{order_id}/messages")
async def send_message(
    order_id: int,
    payload: SendChatMessageRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> dict:
    await _assert_order_chat_access(db, user, order_id)
    message_id = await ChatRepo(db).add_message(order_id, user.user_id, user.role, payload.text.strip())
    return {"message_id": message_id}


@router.post("/{order_id}/read")
async def mark_chat_read(
    order_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> dict:
    await _assert_order_chat_access(db, user, order_id)
    await ChatReadsRepo(db).mark_read(order_id, user.role, user.user_id)
    return {"ok": True}
