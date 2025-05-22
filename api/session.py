# SQLAlchemy setup
import logging

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from api.ENV import DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME


logger = logging.getLogger("telegram-notifier")



DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()  # Remove this line


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


