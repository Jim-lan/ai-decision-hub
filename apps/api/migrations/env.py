from alembic import context
from sqlalchemy import create_engine
from app.db import migration_url

engine = create_engine(migration_url())
with engine.connect() as conn:
    context.configure(connection=conn)
    with context.begin_transaction():
        context.run_migrations()
