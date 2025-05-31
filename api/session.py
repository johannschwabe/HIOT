# SQLAlchemy setup
import logging
import time
import socket
from numbers import Number

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from api.ENV import DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME

logger = logging.getLogger("telegram-notifier")


def wait_for_db_host(host, port: Number, timeout=60):
    """Wait for database host to be reachable"""
    logger.info(f"Waiting for database at {host}:{port}...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                logger.info(f"Database host {host}:{port} is reachable!")
                return True

        except socket.gaierror as e:
            logger.warning(f"DNS resolution failed for {host}: {e}")
        except Exception as e:
            logger.warning(f"Connection check failed: {e}")

        logger.info(f"Database not ready, retrying in 2 seconds...")
        time.sleep(2)

    raise Exception(f"Database at {host}:{port} not reachable after {timeout} seconds")


def create_database_engine_with_retry():
    """Create database engine with connection retry"""
    # First, wait for the host to be reachable
    wait_for_db_host(DB_HOST, int(DB_PORT))

    # Create the database URL
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    # Create engine with connection retry
    max_retries = 10
    retry_delay = 3

    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to connect to database (attempt {attempt + 1}/{max_retries})")

            engine = create_engine(
                DATABASE_URL,
                pool_pre_ping=True,  # Verify connections before use
                pool_recycle=300,  # Recycle connections every 5 minutes
                connect_args={"connect_timeout": 10}
            )

            # Test the connection with a simple query
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            logger.info("Successfully connected to database!")
            return engine

        except OperationalError as e:
            logger.error(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                return None
            else:
                logger.error("All database connection attempts failed!")
                raise
        except Exception as e:
            logger.error(f"Unexpected error during database connection: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                return None
            else:
                raise
    return None


# Initialize database connection with retry
try:
    engine = create_database_engine_with_retry()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base = declarative_base()
    Base.metadata.create_all(bind=engine)
    logger.info("Database setup completed successfully")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    raise


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()