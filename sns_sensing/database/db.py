"""
역할: SQLite 데이터베이스 연결 및 세션 관리를 담당합니다.
목적: Trend Bot 파이프라인 전반에서 데이터베이스에 접근할 수 있도록 일관된 세션을 제공합니다.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# Create data directory if it doesn't exist
db_dir = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(db_dir, exist_ok=True)
DATABASE_URL = f"sqlite:///{os.path.join(db_dir, 'trend_data.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
