from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Every model inherits from this, so SQLAlchemy can track all tables."""
