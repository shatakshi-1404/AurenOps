from alembic import context
from sqlalchemy import text

from app import models  # noqa: F401
from app.core.db import Base, engine

target_metadata = Base.metadata


def run_migrations_online():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
        context.configure(connection=conn, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
