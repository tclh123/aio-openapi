import asyncpg
from asyncpg.pool import Pool

import sqlalchemy as sa

from .dbmodel import DbConnection, DbModel
from ..utils import asynccontextmanager
from ..exc import ImproperlyConfigured


class Database(DbConnection):
    """A container for tables in a database
    """
    def __init__(self, dsn: str=None):
        self._dsn = dsn
        self._pool = None
        self._engine = None
        self._metadata = sa.MetaData()

    def setup(self, app):
        """Called by app during setup
        """
        pass

    @property
    def metadata(self):
        return self._metadata

    @property
    def pool(self):
        return self._pool

    @property
    def engine(self):
        if self._engine is None:
            if not self._dsn:
                raise ImproperlyConfigured('DSN not available')
            self._engine = sa.create_engine(self._dsn)
        return self._engine

    def model(self, name):
        return DbModel(self, name)

    async def connect(self) -> Pool:
        self._pool = await asyncpg.create_pool(self._dsn)
        return self._pool

    @asynccontextmanager
    async def connection(self) -> asyncpg.Connection:
        if not self._pool:
            await self.connect()
        async with self._pool.acquire() as conn:
            yield conn

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    @asynccontextmanager
    async def ensure_connection(self, conn):
        if conn:
            yield conn
        else:
            async with self.transaction() as conn:
                yield conn

    # SQL Alchemy Sync Operations
    def create_all(self) -> None:
        self.metadata.create_all(self.engine)

    def drop_all(self) -> None:
        self.engine.execute(f'truncate {", ".join(self.metadata.tables)}')
        try:
            self.engine.execute('drop table alembic_version')
        except Exception:  # noqa
            pass

    def drop_all_schemas(self) -> None:
        self.engine.execute("DROP SCHEMA IF EXISTS public CASCADE")
        self.engine.execute("CREATE SCHEMA IF NOT EXISTS public")
