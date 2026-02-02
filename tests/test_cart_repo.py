import asyncio
import tempfile
from pathlib import Path

from app.db.database import Database, DBConfig
from app.repositories.shops_repo import ShopsRepo
from app.repositories.categories_repo import CategoriesRepo
from app.repositories.products_repo import ProductsRepo
from app.repositories.cart_repo import CartRepo


async def _seed_product(db: Database) -> tuple[int, int, int]:
    """Готовим магазин, категорию и товар для тестов корзины."""
    shops = ShopsRepo(db)
    categories = CategoriesRepo(db)
    products = ProductsRepo(db)

    shop_id = await shops.create_shop("Тестовый магазин", "shop")
    category_id = await categories.create(shop_id, "Тестовая категория")
    product_id = await products.create(shop_id, category_id, "Тестовый товар", 100.0, "Описание")
    return shop_id, category_id, product_id


def test_cart_set_qty_zero_deletes_row():
    async def _run():
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(DBConfig(path=str(Path(tmpdir) / "t.db")))
            await db.init_schema()
            _, _, product_id = await _seed_product(db)
            cart = CartRepo(db)
            user_id = 501

            # Добавляем товар, затем обнуляем количество — строка должна исчезнуть.
            await cart.add(user_id=user_id, product_id=product_id, qty=2)
            items_before = await cart.list_items(user_id)
            assert len(items_before) == 1
            assert int(items_before[0]["quantity"]) == 2

            await cart.set_qty(user_id=user_id, product_id=product_id, qty=0)
            items_after = await cart.list_items(user_id)
            assert items_after == []

    asyncio.run(_run())


def test_cart_set_qty_negative_deletes_row():
    async def _run():
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(DBConfig(path=str(Path(tmpdir) / "t.db")))
            await db.init_schema()
            _, _, product_id = await _seed_product(db)
            cart = CartRepo(db)
            user_id = 502

            # Отрицательное количество должно приводить к удалению строки.
            await cart.add(user_id=user_id, product_id=product_id, qty=1)
            await cart.set_qty(user_id=user_id, product_id=product_id, qty=-3)
            items_after = await cart.list_items(user_id)
            assert items_after == []

    asyncio.run(_run())


def test_cart_set_qty_updates_row():
    async def _run():
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(DBConfig(path=str(Path(tmpdir) / "t.db")))
            await db.init_schema()
            _, _, product_id = await _seed_product(db)
            cart = CartRepo(db)
            user_id = 503

            # Устанавливаем количество больше нуля — строка остаётся и обновляется.
            await cart.add(user_id=user_id, product_id=product_id, qty=1)
            await cart.set_qty(user_id=user_id, product_id=product_id, qty=5)
            items_after = await cart.list_items(user_id)
            assert len(items_after) == 1
            assert int(items_after[0]["quantity"]) == 5

    asyncio.run(_run())
