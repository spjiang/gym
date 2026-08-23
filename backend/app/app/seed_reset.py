"""清空库内业务数据（保留 alembic_version），用于交付前重建 Demo。"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def reset_all_data(db: Session) -> None:
    """TRUNCATE 全部 public 表并重置序列。"""
    db.execute(
        text(
            """
            DO $$ DECLARE r RECORD;
            BEGIN
                FOR r IN (
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = 'public' AND tablename <> 'alembic_version'
                ) LOOP
                    EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' RESTART IDENTITY CASCADE';
                END LOOP;
            END $$;
            """
        )
    )
    db.flush()
