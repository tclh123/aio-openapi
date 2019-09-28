import os
from typing import Optional, Any

import asyncpg
import sqlalchemy as sa
from asyncpg import Connection
from asyncpg.pool import Pool

from ..exc import ImproperlyConfigured
from ..utils import asynccontextmanager

DBPOOL_MIN_SIZE = int(os.environ.get("DBPOOL_MIN_SIZE") or "10")
DBPOOL_MAX_SIZE = int(os.environ.get("DBPOOL_MAX_SIZE") or "10")


class Database:
    """A container for tables in a database
    """

    def __init__(self, dsn: str = "", metadata: sa.MetaData = None) -> None:
        self._dsn = dsn
        self._metadata = metadata or sa.MetaData()
        self._pool = None
        self._engine = None

    def __repr__(self) -> str:
        return self._dsn

    __str__ = __repr__

    @property
    def dsn(self) -> str:
        return self._dsn

    @property
    def metadata(self) -> sa.MetaData:
        return self._metadata

    @property
    def pool(self) -> Optional[Pool]:
        return self._pool

    @property
    def engine(self):
        if self._engine is None:
            if not self._dsn:
                raise ImproperlyConfigured("DSN not available")
            self._engine = sa.create_engine(self._dsn)
        return self._engine

    def __getattr__(self, name: str) -> Any:
        if name in self._metadata.tables:
            return self._metadata.tables[name]
        return super().__getattribute__(name)

    async def connect(self) -> Pool:
        pool = await asyncpg.create_pool(
            self._dsn, min_size=DBPOOL_MIN_SIZE, max_size=DBPOOL_MAX_SIZE
        )
        self._pool = pool
        return pool

    async def get_connection(self) -> Connection:
        pool = self._pool
        if pool is None:
            pool = await self.connect()
        return await pool.acquire()

    async def release_connection(self, conn: Connection) -> None:
        if self._pool is not None:
            await self._pool.release(conn)

    @asynccontextmanager
    async def connection(self) -> Connection:
        pool = self._pool
        if pool is None:
            pool = await self.connect()
        async with pool.acquire() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self) -> Connection:
        async with self.connection() as conn, conn.transaction():
            yield conn

    @asynccontextmanager
    async def ensure_connection(self, conn: Optional[Connection] = None) -> Connection:
        if conn:
            yield conn
        else:
            async with self.connection() as conn:
                async with conn.transaction():
                    yield conn

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    # SQL Alchemy Sync Operations
    def create_all(self) -> None:
        self.metadata.create_all(self.engine)

    def drop_all(self) -> None:
        self.engine.execute(f'truncate {", ".join(self.metadata.tables)}')
        try:
            self.engine.execute("drop table alembic_version")
        except Exception:  # noqa
            pass

    def drop_all_schemas(self) -> None:
        self.engine.execute("DROP SCHEMA IF EXISTS public CASCADE")
        self.engine.execute("CREATE SCHEMA IF NOT EXISTS public")
