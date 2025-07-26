import logging
import time
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

logger = logging.getLogger("humidity-api")

Base = declarative_base()
engine = None
SessionLocal = None


def init_database(db_url: str, max_retries: int = 10, retry_delay: int = 3):
    """Initialize database with retry logic"""
    global engine, SessionLocal

    for attempt in range(max_retries):
        try:
            logger.info(f"Database connection attempt {attempt + 1}/{max_retries}")

            engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_recycle=300,
                connect_args={"connect_timeout": 10}
            )

            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

            # Create tables if they don't exist
            Base.metadata.create_all(bind=engine)

            logger.info("Database initialized successfully")
            return True

        except OperationalError as e:
            logger.error(f"Database connection failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise

    return False


def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
