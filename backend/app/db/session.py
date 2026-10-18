from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# The engine manages connections to PostgreSQL.
# pool_pre_ping checks a connection is alive before using it.
engine = create_engine(settings.sqlalchemy_database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """One database session per request, always closed afterwards.

    If a route raises before commit(), closing the session discards the
    uncommitted changes, which is our automatic rollback.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
