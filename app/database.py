from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import DATABASE_URL



engine = create_engine(
    DATABASE_URL,
    pool_size=5,         # Number of connections to keep open inside the pool
    max_overflow=10,     # Extra connections if the pool is full
    pool_timeout=30,     # Time (seconds) to wait before giving up
    pool_recycle=1800,   # Refresh connections every 30 minutes
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
