from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import DATABASE_URL

# db_url = f"postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOSTNAME}/{DATABASE_NAME}"


# engine = create_engine(db_url)
# SessionLocal=sessionmaker(autoflush=False, bind=engine)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
