"""
역할: SQLite 데이터베이스 연결 및 세션 관리를 담당합니다.
목적: Trend Bot 파이프라인 전반에서 데이터베이스에 접근할 수 있도록 일관된 세션을 제공합니다.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

# 최상위 루트의 .env 파일을 로드
db_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(db_dir))
load_dotenv(dotenv_path=os.path.join(root_dir, ".env"))

# 환경변수에서 DATABASE_URL 로드 (Azure Connection Strings Fallback 포함)
DATABASE_URL = (
    os.getenv("DATABASE_URL") or 
    os.getenv("POSTGRESQLCONNSTR_DATABASE_URL") or 
    os.getenv("CUSTOMCONNSTR_DATABASE_URL") or 
    os.getenv("SQLCONNSTR_DATABASE_URL")
)

if DATABASE_URL:
    DATABASE_URL = DATABASE_URL.strip().strip('"').strip("'")

# PostgreSQL 비밀번호 특수문자 (%) 파싱 에러 방지 처리
if DATABASE_URL and (DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres")):
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

# [자동 마이그레이션] PostgreSQL 등에서 videos 테이블에 subscriber_count 컬럼이 누락된 경우 자동 생성
if not is_sqlite:
    from sqlalchemy import text
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE videos ADD COLUMN IF NOT EXISTS subscriber_count INTEGER DEFAULT 0;"))
            print("[Migration] Checked/Added subscriber_count column to videos table.")
    except Exception as migration_error:
        print(f"[Warning] Failed to run migration for subscriber_count: {migration_error}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
