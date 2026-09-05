"""Database connection management using psycopg 3."""

from __future__ import annotations

import contextlib
from typing import Generator
import psycopg

from location_resolver.config import settings


@contextlib.contextmanager
def get_connection(autocommit: bool = False) -> Generator[psycopg.Connection, None, None]:
    """Provide a transactional database connection context manager."""
    conn = psycopg.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        autocommit=autocommit,
    )
    try:
        yield conn
    finally:
        conn.close()


def get_db_pool():
    """Placeholder connection pool accessor for future async / multi-threaded worker pools."""
    return get_connection()
