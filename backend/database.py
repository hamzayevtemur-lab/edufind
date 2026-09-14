import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Ironman3106)")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_NAME = os.getenv("DB_NAME", "right_center")

DATABASE_URL = os.getenv("DATABASE_URL", f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{DB_NAME}")

engine = create_engine(
    DATABASE_URL,
    echo=False,           # Disable verbose logging overhead for max performance
    pool_size=10,         # Pre-allocated connection pool size
    max_overflow=20,      # Overflow connections for peak load
    pool_recycle=1800,    # Recycle connections after 30 min to prevent MySQL disconnects
    pool_pre_ping=True    # Avoids stale connection errors
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
Base = declarative_base()
