"""
역할: SQLite 데이터베이스 연결 및 세션 관리를 담당합니다.
목적: Trend Bot 파이프라인 전반에서 데이터베이스에 접근할 수 있도록 일관된 세션을 제공합니다.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# 환경변수에서 DATABASE_URL 로드
DATABASE_URL = os.getenv("DATABASE_URL")

# PostgreSQL 비밀번호 특수문자 (%) 파싱 에러 방지 처리
if DATABASE_URL and DATABASE_URL.startswith("postgresql"):
    from urllib.parse import urlparse, quote_plus, urlunparse
    try:
        parsed = urlparse(DATABASE_URL)
        if parsed.password:
            # 비밀번호 내 특수문자를 퍼센트 인코딩하여 SQLAlchemy 파싱 충돌 예방
            encoded_password = quote_plus(parsed.password)
            # URL 재조립
            netloc = f"{parsed.username}:{encoded_password}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            parsed = parsed._replace(netloc=netloc)
            DATABASE_URL = urlunparse(parsed)
    except Exception as e:
        print(f"[Warning] DATABASE_URL 파싱 실패 (SQLite 폴백 사용 가능): {e}")

# 환경변수가 없거나 비어 있으면 기존 SQLite 데이터베이스 폴백 사용
if not DATABASE_URL or DATABASE_URL.strip() == "":
    db_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(db_dir, exist_ok=True)
    DATABASE_URL = f"sqlite:///{os.path.join(db_dir, 'trend_data.db')}"

# SQLite일 때만 check_same_thread 파라미터 적용 (PostgreSQL 등 타 DB 호환용)
is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
