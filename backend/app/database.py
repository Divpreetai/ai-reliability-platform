import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.app.config import settings

logger = logging.getLogger(__name__)

db_url = settings.DATABASE_URL
connect_args = {}

if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

try:
    # Test database connectivity
    engine = create_engine(db_url, connect_args=connect_args)
    with engine.connect() as conn:
        pass
except Exception as e:
    # Fallback to local SQLite database if Postgres is unreachable
    logger.warning(f"Database connection to PostgreSQL failed ({str(e)}). Falling back to SQLite.")
    db_url = "sqlite:///./agent_eval.db"
    connect_args = {"check_same_thread": False}
    engine = create_engine(db_url, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

# Dependency to get db session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
