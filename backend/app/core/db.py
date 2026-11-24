from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=10, max_overflow=10)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def session_scope():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Extensions, tables, FTS index and append-only audit trigger."""
    with engine.begin() as c:
        c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    from app import models  # noqa: F401

    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("CREATE INDEX IF NOT EXISTS ix_chunks_fts ON document_chunks "
                       "USING gin (to_tsvector('english', content))"))
        c.execute(text("""
            CREATE OR REPLACE FUNCTION audit_logs_immutable() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION 'audit_logs is append-only'; END;
            $$ LANGUAGE plpgsql"""))
        c.execute(text("DROP TRIGGER IF EXISTS audit_logs_no_change ON audit_logs"))
        c.execute(text("CREATE TRIGGER audit_logs_no_change BEFORE UPDATE OR DELETE ON audit_logs "
                       "FOR EACH ROW EXECUTE FUNCTION audit_logs_immutable()"))
