from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

engine = create_engine(settings.DATABASE_URL, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def init_db():
    from . import models  # noqa: F401

    try:
        Base.metadata.create_all(bind=engine)
    except OperationalError as exc:
        if "does not exist" not in str(exc) or "postgresql" not in settings.DATABASE_URL:
            raise
        _create_missing_postgres_database(settings.DATABASE_URL)
        Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _create_missing_postgres_database(database_url: str):
    import psycopg

    url = make_url(database_url)
    target_db = url.database
    admin_url = url.set(database="postgres")
    dsn = f"postgresql://{admin_url.username}:{admin_url.password}@{admin_url.host}:{admin_url.port}/{admin_url.database}"
    with psycopg.connect(dsn) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{target_db}"')
