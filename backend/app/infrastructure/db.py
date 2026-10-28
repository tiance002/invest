from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.infrastructure.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    if not url.startswith("postgresql"):
        raise ValueError("PostgreSQL is required")
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 3})


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
