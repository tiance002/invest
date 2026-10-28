from logging.config import fileConfig

import app.evaluation.models  # noqa: F401
import app.infrastructure.models  # noqa: F401
import app.rsi_lab.models  # noqa: F401
from alembic import context
from app.infrastructure.config import get_settings
from app.infrastructure.db import Base, make_engine

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=config.attributes.get("schema"),
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    run(config.attributes["connection"])
else:
    engine = make_engine(get_settings().database_url)
    with engine.connect() as connection:
        run(connection)
