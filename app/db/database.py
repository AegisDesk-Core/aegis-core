from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection
from psycopg_pool import ConnectionPool

from app.db.schema import build_schema_sql
from app.db.settings import DATABASE_URL, DB_MAX_SIZE, DB_MIN_SIZE, DB_TIMEOUT


pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=DB_MIN_SIZE,
    max_size=DB_MAX_SIZE,
    timeout=DB_TIMEOUT,
    open=False,
)


def open_pool() -> None:
    """Open the pool and validate one database connection."""
    try:
        pool.open(wait=True, timeout=DB_TIMEOUT)
        with pool.connection() as connection:
            connection.execute("SELECT 1")
            connection.execute(build_schema_sql())
    except Exception as error:
        pool.close()
        raise RuntimeError(
            "PostgreSQL connection failed. Check DATABASE_URL or POSTGRES_* settings in .env."
        ) from error


def close_pool() -> None:
    """Close all pooled connections during application shutdown."""
    pool.close()


@contextmanager
def get_connection() -> Iterator[Connection]:
    """Borrow a connection and return it to the pool after use."""
    with pool.connection() as connection:
        yield connection
