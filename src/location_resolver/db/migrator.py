"""Database schema migration runner."""

from __future__ import annotations

from pathlib import Path
import psycopg
from psycopg import sql

from location_resolver.config import settings
from location_resolver.db.connection import get_connection

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def apply_migrations(migrations_dir: Path | None = None) -> list[str]:
    """Execute all pending SQL migrations in alphabetical order within a transaction."""
    target_dir = migrations_dir or MIGRATIONS_DIR
    if not target_dir.exists():
        raise FileNotFoundError(f"Migrations directory not found: {target_dir}")

    migration_files = sorted(target_dir.glob("*.sql"))
    applied: list[str] = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Ensure migrations tracking table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)

            # 2. Fetch already applied versions
            cur.execute("SELECT version FROM schema_migrations;")
            applied_versions = {row[0] for row in cur.fetchall()}

            # 3. Apply pending migrations
            for mf in migration_files:
                version = mf.name
                if version not in applied_versions:
                    sql_content = mf.read_text(encoding="utf-8")
                    cur.execute(psycopg.sql.SQL(sql_content))
                    cur.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s);",
                        (version,),
                    )
                    applied.append(version)

        conn.commit()

    return applied


if __name__ == "__main__":
    applied_list = apply_migrations()
    if applied_list:
        print(f"Successfully applied migrations: {applied_list}")
    else:
        print("Database schema is up to date. No new migrations applied.")
