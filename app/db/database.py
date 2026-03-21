from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Optional
from contextlib import asynccontextmanager
from datetime import datetime

import asyncpg




@dataclass(frozen=True)
class DBConfig:
    path: str = ""
    dsn: str = ""


def _try_parse_dt(val):
    if not isinstance(val, str):
        return val
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    return val


def _convert_query(sql: str, params) -> tuple[str, list]:
    if not params:
        return sql, []
    pg_params = [_try_parse_dt(p) for p in params]
    result = []
    counter = 1
    for ch in sql:
        if ch == "?":
            result.append(f"${counter}")
            counter += 1
        else:
            result.append(ch)
    return "".join(result), pg_params


async def _generate_sku() -> str:
    return f"SKU-{secrets.token_hex(4).upper()}"


class _RowProxy(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)


class _AsyncPGCursor:
    def __init__(self, rows: list, lastrowid: Optional[int] = None):
        self._rows = [_RowProxy(dict(r)) for r in rows]
        self.lastrowid = lastrowid

    async def fetchall(self) -> list[_RowProxy]:
        return self._rows

    async def fetchone(self) -> Optional[_RowProxy]:
        return self._rows[0] if self._rows else None

    def __aiter__(self):
        return _RowIter(self._rows)


class _RowIter:
    def __init__(self, rows):
        self._rows = rows
        self._idx = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._rows):
            raise StopAsyncIteration
        row = self._rows[self._idx]
        self._idx += 1
        return row


class _AsyncPGConnection:
    def __init__(self, conn: asyncpg.Connection):
        self._conn = conn

    async def execute(self, sql: str, params=()) -> _AsyncPGCursor:
        pg_sql, pg_params = _convert_query(sql, params)
        sql_upper = pg_sql.strip().upper()
        if sql_upper.startswith("INSERT") and "RETURNING" not in sql_upper:
            pg_sql = pg_sql.rstrip().rstrip(";") + " RETURNING id"
            try:
                rows = await self._conn.fetch(pg_sql, *pg_params)
                lastrowid = int(rows[-1]["id"]) if rows else None
                return _AsyncPGCursor(rows, lastrowid)
            except Exception:
                pg_sql = _convert_query(sql, params)[0]
                await self._conn.execute(pg_sql, *pg_params)
                return _AsyncPGCursor([], None)
        elif sql_upper.startswith(("UPDATE", "DELETE", "ALTER", "CREATE", "DROP", "PRAGMA")):
            await self._conn.execute(pg_sql, *pg_params)
            return _AsyncPGCursor([])
        else:
            rows = await self._conn.fetch(pg_sql, *pg_params)
            return _AsyncPGCursor(rows)

    async def executescript(self, sql: str) -> None:
        await self._conn.execute(sql)

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class Database:
    def __init__(self, config: DBConfig):
        self.config = config
        self._pool: Optional[asyncpg.Pool] = None

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=self.config.dsn,
                min_size=2,
                max_size=10,
            )
        return self._pool

    @asynccontextmanager
    async def conn(self):
        pool = await self._get_pool()
        async with pool.acquire() as raw_conn:
            yield _AsyncPGConnection(raw_conn)

    async def init_schema(self, schema_path=None) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
