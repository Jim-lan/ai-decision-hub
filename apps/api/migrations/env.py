from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from app.db import migration_url

engine = create_engine(migration_url(), poolclass=NullPool)
with engine.connect() as conn:
    context.configure(connection=conn)
    with context.begin_transaction():
        context.run_migrations()
