from __future__ import annotations

import aiosqlite
import secrets
from sqlite3 import IntegrityError
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from app.services.order_statuses import map_from_legacy, map_to_legacy


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
            connection.row_factory = aiosqlite.Row
            yield connection
        finally:
            await connection.close()

    async def init_schema(self, schema_path: Optional[str] = None) -> None:
        if schema_path is None:
            schema_path = str(Path(__file__).with_name("schema.sql"))
    
        # schema.sql содержит CREATE INDEX ... по новым колонкам.
        # На старой БД новые колонки ещё не добавлены -> падает "no such column".
        # Решение: сначала DDL без индексов, потом миграции, потом индексы.
        raw_sql = Path(schema_path).read_text(encoding="utf-8")
    
        schema_lines: list[str] = []
        index_lines: list[str] = []
    
        for line in raw_sql.splitlines():
            l = line.lstrip().upper()
            if l.startswith("CREATE INDEX") or l.startswith("CREATE UNIQUE INDEX") or l.startswith("DROP INDEX"):
                index_lines.append(line)
            else:
                schema_lines.append(line)
    
        sql_schema = "\n".join(schema_lines).strip() + "\n"
        sql_indexes = "\n".join(index_lines).strip() + "\n"
    
        async with self.conn() as connection:
            # 1) базовые таблицы/DDL (без индексов)
            if sql_schema.strip():
                await connection.executescript(sql_schema)
    
            # 2) миграции (ADD COLUMN и т.д.)
            await self._migrate(connection)
    
            # 3) индексы (когда колонки уже точно есть)
            if sql_indexes.strip():
                await connection.executescript(sql_indexes)
    
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

        # orders: комментарий клиента и двухосевые статусы
        await add_column("orders", "comment", "comment TEXT DEFAULT ''")
        await add_column("orders", "merchant_status", "merchant_status TEXT NOT NULL DEFAULT 'new'")
        await add_column("orders", "courier_status", "courier_status TEXT NOT NULL DEFAULT 'searching'")
        await add_column("orders", "courier_user_id", "courier_user_id INTEGER")
        await add_column("orders", "handoff_code", "handoff_code TEXT")
        await add_column("orders", "handoff_confirmed", "handoff_confirmed INTEGER NOT NULL DEFAULT 0")
        await add_column("orders", "client_arrival_message_id", "client_arrival_message_id INTEGER")
        await add_column("orders", "zone_id", "zone_id INTEGER")
        await add_column("shops", "allow_prepare_before_courier", "allow_prepare_before_courier INTEGER NOT NULL DEFAULT 0")
        await add_column("couriers", "transport_type", "transport_type TEXT DEFAULT ''")
        await add_column("client_profiles", "locale", "locale TEXT DEFAULT 'ru'")
        await add_column("order_chat_messages", "thread", "thread TEXT NOT NULL DEFAULT 'merchant'")

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
                thread TEXT NOT NULL DEFAULT 'merchant',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
            )
            """
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_prefs (
                order_id INTEGER NOT NULL,
                actor_role TEXT NOT NULL,
                actor_id INTEGER NOT NULL,
                thread TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (order_id, actor_role, actor_id),
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
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS couriers (
                user_id INTEGER PRIMARY KEY,
                is_online INTEGER NOT NULL DEFAULT 0,
                accept_all_zones INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS courier_zones (
                courier_user_id INTEGER NOT NULL,
                zone_id INTEGER NOT NULL,
                PRIMARY KEY (courier_user_id, zone_id),
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
            )
            """
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
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
        await connection.execute("CREATE INDEX IF NOT EXISTS idx_orders_courier_status ON orders(courier_status);")
        await connection.execute("CREATE INDEX IF NOT EXISTS idx_orders_merchant_status ON orders(merchant_status);")
        await connection.execute("CREATE INDEX IF NOT EXISTS idx_orders_courier_user ON orders(courier_user_id);")
        await connection.execute("CREATE INDEX IF NOT EXISTS idx_orders_zone_id ON orders(zone_id);")
        await connection.execute("CREATE INDEX IF NOT EXISTS idx_couriers_online ON couriers(is_online);")
        await connection.execute("CREATE INDEX IF NOT EXISTS idx_courier_zones_zone ON courier_zones(zone_id);")
        await connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_reminders_due ON chat_message_reminders(recipient_kind, status, scheduled_at);"
        )

        cur_orders = await connection.execute("SELECT id, status, merchant_status, courier_status FROM orders")
        order_rows = await cur_orders.fetchall()
        for row in order_rows:
            merchant_status = (row["merchant_status"] or "").strip().lower()
            courier_status = (row["courier_status"] or "").strip().lower()
            if not merchant_status or not courier_status:
                merchant_status, courier_status = map_from_legacy(row["status"])
            legacy = map_to_legacy(merchant_status, courier_status)
            await connection.execute(
                "UPDATE orders SET merchant_status=?, courier_status=?, status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (merchant_status, courier_status, legacy, int(row["id"])),
            )
