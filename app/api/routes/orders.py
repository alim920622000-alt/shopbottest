from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import CurrentUser, get_current_user, get_db
from app.api.schemas import CreateOrderRequest, CursorPage
from app.db.database import Database
from app.handlers_admin_restaurant.utils import get_admin_restaurant_ids
from app.handlers_admin_shop.utils import get_admin_shop_ids
from app.repositories.orders_repo import OrdersRepo

router = APIRouter(prefix="/orders", tags=["orders"])


def _parse_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return max(int(cursor), 0)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Некорректный cursor") from exc


async def _allowed_shop_ids(db: Database, user: CurrentUser) -> set[int]:
    if user.role == "admin_shop":
        return set(await get_admin_shop_ids(db, user.user_id))
    if user.role == "admin_restaurant":
        return set(await get_admin_restaurant_ids(db, user.user_id))
    return set()


async def _assert_order_access(db: Database, user: CurrentUser, order_id: int) -> dict:
    order = await OrdersRepo(db).get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    if user.role == "client":
        if int(order["client_user_id"]) != user.user_id:
            raise HTTPException(status_code=403, detail="Нет доступа к заказу")
        return order

    allowed = await _allowed_shop_ids(db, user)
    if int(order["shop_id"]) not in allowed:
        raise HTTPException(status_code=403, detail="Нет доступа к заказу")
    return order


@router.get("", response_model=CursorPage)
async def list_orders(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    status: str | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> CursorPage:
    cursor_id = _parse_cursor(cursor)
    params: list[object] = [cursor_id]
    where = ["o.id > ?"]

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

    if status:
        where.append("o.status = ?")
        params.append(status)

    where_sql = " AND ".join(where)
    async with db.conn() as conn:
        cur = await conn.execute(
            f"""
            SELECT o.*, s.name AS shop_name, s.business_type
            FROM orders o
            JOIN shops s ON s.id = o.shop_id
            WHERE {where_sql}
            ORDER BY o.id ASC
            LIMIT ?
            """,
            (*params, limit + 1),
        )
        page = [dict(r) for r in await cur.fetchall()]

    next_cursor = str(page[limit - 1]["id"]) if len(page) > limit else None
    return CursorPage(items=page[:limit], next_cursor=next_cursor)


@router.get("/{order_id}")
async def get_order(
    order_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> dict:
    order = await _assert_order_access(db, user, order_id)
    items = await OrdersRepo(db).get_order_items(order_id)
    return {"order": order, "items": items}


@router.post("")
async def create_order(
    payload: CreateOrderRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> dict:
    if user.role != "client":
        raise HTTPException(status_code=403, detail="Создавать заказ может только клиент")

    repo = OrdersRepo(db)
    if not payload.items:
        try:
            order_id = await repo.create_order_from_cart(
                shop_id=payload.shop_id,
                client_user_id=user.user_id,
                comment=payload.comment,
                fulfillment_type=payload.fulfillment_type,
            )
            return {"order_id": order_id}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    async with db.conn() as conn:
        await conn.execute("BEGIN")
        total = 0.0
        collected: list[tuple[int, int, float]] = []
        for item in payload.items:
            cur = await conn.execute(
                "SELECT id, price, shop_id FROM products WHERE id=? AND is_active=1",
                (item.product_id,),
            )
            row = await cur.fetchone()
            if not row:
                await conn.execute("ROLLBACK")
                raise HTTPException(status_code=400, detail=f"Товар {item.product_id} не найден")
            if int(row["shop_id"]) != payload.shop_id:
                await conn.execute("ROLLBACK")
                raise HTTPException(status_code=400, detail="Все товары должны быть из одного магазина")
            price = float(row["price"])
            total += price * item.quantity
            collected.append((item.product_id, item.quantity, price))

        cur_order = await conn.execute(
            """
            INSERT INTO orders (shop_id, client_user_id, status, total_amount, comment, fulfillment_type, updated_at)
            VALUES (?, ?, 'new', ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (payload.shop_id, user.user_id, total, payload.comment, payload.fulfillment_type),
        )
        order_id = int(cur_order.lastrowid)

        for product_id, quantity, price in collected:
            await conn.execute(
                """
                INSERT INTO order_items (order_id, product_id, quantity, price_at_moment)
                VALUES (?, ?, ?, ?)
                """,
                (order_id, product_id, quantity, price),
            )
        await conn.commit()

    return {"order_id": order_id}
