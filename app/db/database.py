from __future__ import annotations

import aiosqlite
import secrets
from sqlite3 import IntegrityError
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager


@dataclass(frozen=True)
class DBConfig:
    path: str  # sqlite file path, e.g. "shop.db"




async def _generate_sku() -> str:
    # Генерация публичного SKU в формате SKU-XXXXXXXX.
    return f"SKU-{secrets.token_hex(4).upper()}"


async def _assign_sku_for_product(connection: aiosqlite.Connection, product_id: int, attempts: int = 25) -> None:
    # Пытаемся назначить уникальный SKU, повторяя генерацию при конфликте.
    for _ in range(attempts):
        candidate = await _generate_sku()
        try:
            await connection.execute(
                "UPDATE products SET sku=? WHERE id=? AND (sku IS NULL OR sku='')",
                (candidate, product_id),
            )
            return
        except IntegrityError:
            continue
    raise RuntimeError("Не удалось назначить SKU при миграции")

class Database:
    """
    Единая точка входа в БД: всегда включает foreign_keys и Row factory.
    """
    def __init__(self, config: DBConfig):
        self.config = config

    @asynccontextmanager
    async def conn(self) -> aiosqlite.Connection:
        connection = await aiosqlite.connect(self.config.path)
        try:
            await connection.execute("PRAGMA foreign_keys = ON;")
            await connection.execute("PRAGMA journal_mode = WAL;")
            await connection.execute("PRAGMA busy_timeout = 8000;")
            connection.row_factory = aiosqlite.Row
            yield connection
        finally:
            await connection.close()

    async def init_schema(self, schema_path: Optional[str] = None) -> None:
        if schema_path is None:
            schema_path = str(Path(__file__).with_name("schema.sql"))

        sql = Path(schema_path).read_text(encoding="utf-8")
        async with self.conn() as connection:
            await connection.executescript(sql)
            # ✅ ДОБАВЬ ЭТО:
            await self._migrate(connection)

            await connection.commit()
    
    async def _migrate(self, connection: aiosqlite.Connection) -> None:
        async def has_column(table: str, col: str) -> bool:
            cur = await connection.execute(f"PRAGMA table_info({table})")
            rows = await cur.fetchall()
            return any(r["name"] == col for r in rows)

        async def add_column(table: str, col: str, ddl: str) -> None:
            if not await has_column(table, col):
                await connection.execute(f"ALTER TABLE {table} ADD COLUMN {ddl};")

        # categories: нормализованное имя для поиска/дедупликации
        await add_column("categories", "name_norm", "name_norm TEXT DEFAULT ''")
        await add_column("categories", "business_type", "business_type TEXT DEFAULT 'shop'")
        
        await add_column("categories", "name_ru", "name_ru TEXT")
        await add_column("categories", "name_uz", "name_uz TEXT")
        await add_column("categories", "name_tj", "name_tj TEXT")

        # products: поля под поиск и импорт
        await add_column("products", "name_norm", "name_norm TEXT DEFAULT ''")
        await add_column("products", "keywords_norm", "keywords_norm TEXT DEFAULT ''")
        await add_column("products", "unit", "unit TEXT DEFAULT 'шт'")
        await add_column("products", "barcode", "barcode TEXT DEFAULT ''")
        await add_column("products", "updated_at", "updated_at DATETIME")
        await add_column("products", "sku", "sku TEXT")

        # orders: комментарий клиента
        await add_column("orders", "comment", "comment TEXT DEFAULT ''")
        await add_column("client_profiles", "locale", "locale TEXT DEFAULT 'ru'")

        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS client_profiles (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                address TEXT DEFAULT '',
                locale TEXT DEFAULT 'ru'
            )
            """
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS search_synonyms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_id INTEGER,
                term TEXT NOT NULL,
                synonym TEXT NOT NULL,
                FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE
            )
            """
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS promotions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE
            )
            """
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS promotion_items (
                promo_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                PRIMARY KEY (promo_id, product_id),
                FOREIGN KEY (promo_id) REFERENCES promotions(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
            """
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS order_chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                sender_user_id INTEGER NOT NULL,
                sender_role TEXT NOT NULL,
                message_text TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
            )
            """
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS order_chat_reads (
                order_id INTEGER NOT NULL,
                viewer_role TEXT NOT NULL,
                viewer_user_id INTEGER NOT NULL,
                last_read_at DATETIME NOT NULL,
                PRIMARY KEY (order_id, viewer_role, viewer_user_id),
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
            )
            """
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS order_seen (
                order_id INTEGER NOT NULL,
                viewer_role TEXT NOT NULL,
                viewer_user_id INTEGER NOT NULL,
                seen_at DATETIME NOT NULL,
                PRIMARY KEY (order_id, viewer_role, viewer_user_id),
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
            )
            """
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_message_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                recipient_user_id INTEGER NOT NULL,
                recipient_kind TEXT NOT NULL,
                last_message_at DATETIME NOT NULL,
                last_message_preview TEXT NOT NULL,
                scheduled_at DATETIME NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                UNIQUE (order_id, recipient_user_id, recipient_kind)
            )
            """
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ui_screens (
                bot_kind TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                screen_message_id INTEGER,
                updated_at TEXT,
                PRIMARY KEY (bot_kind, chat_id)
            )
            """
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_nav_state (
                bot_kind TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                prev_target TEXT NOT NULL,
                updated_at DATETIME,
                PRIMARY KEY (bot_kind, user_id)
            )
            """
        )

        await connection.execute("CREATE INDEX IF NOT EXISTS idx_products_name_norm ON products(name_norm);")
        await connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_products_sku ON products(sku);")
        await connection.execute("CREATE INDEX IF NOT EXISTS idx_products_keywords_norm ON products(keywords_norm);")


        cur = await connection.execute(
            """
            SELECT p.id
            FROM products p
            JOIN shops s ON s.id = p.shop_id
            WHERE s.business_type='shop' AND (p.sku IS NULL OR p.sku='')
            """
        )
        rows = await cur.fetchall()
        for row in rows:
            await _assign_sku_for_product(connection, int(row["id"]))

        await connection.execute("CREATE INDEX IF NOT EXISTS idx_search_synonyms_term ON search_synonyms(term);")
        await connection.execute("CREATE INDEX IF NOT EXISTS idx_promotions_shop ON promotions(shop_id);")
        await connection.execute("CREATE INDEX IF NOT EXISTS idx_promo_items_promo ON promotion_items(promo_id);")
        await connection.execute("CREATE INDEX IF NOT EXISTS idx_chat_order ON order_chat_messages(order_id, created_at);")
        await connection.execute("CREATE INDEX IF NOT EXISTS idx_chat_reads_viewer ON order_chat_reads(viewer_role, viewer_user_id);")
        await connection.execute("CREATE INDEX IF NOT EXISTS idx_order_seen_viewer ON order_seen(viewer_role, viewer_user_id);")
        await connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_reminders_due ON chat_message_reminders(recipient_kind, status, scheduled_at);"
        )
