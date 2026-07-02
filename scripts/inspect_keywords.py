import os
import sys
from sqlalchemy import func

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from sns_sensing.database.db import SessionLocal
from sns_sensing.models.models import Keyword, Video

SUSPICIOUS_CASES = [
    "Pistachio Dubai Chocolate",
    "Dubai Chocolate Pancakes",
    "왁뿌 소금빵",
    "크루키",
]


def inspect_keyword(db, keyword: str):
    print(f"\n=== [{keyword}] 원본 데이터 직접 조회 ===")

    # 1. 정확히 이 문자열로 저장된 Keyword 로우가 실제로 몇 개 있는가
    exact_rows = db.query(Keyword).filter(Keyword.keyword == keyword).all()
    print(f"  정확히 일치하는 Keyword 로우 수: {len(exact_rows)}")

    if exact_rows:
        for r in exact_rows[:5]:  # 너무 많으면 5개만 샘플로
            print(f"    video_id={r.video_id}, extracted_at={r.extracted_at}")

    # 2. 혹시 공백/유사 표기로 다른 이름 밑에 숨어있지 않은지 확인
    #    (예: "Pistachio Dubai Chocolate" vs "피스타치오 두바이 초콜릿" 등)
    similar = (
        db.query(Keyword.keyword, func.count(Keyword.video_id))
        .filter(Keyword.keyword.like(f"%{keyword.split()[0]}%"))
        .group_by(Keyword.keyword)
        .all()
    )
    print(f"  '{keyword.split()[0]}' 포함된 유사 키워드 그룹:")
    for kw, cnt in similar:
        print(f"    - '{kw}': {cnt}건")

    # 3. distinct 채널 수 직접 계산 (스크립트와 별개로 재확인)
    channel_count = (
        db.query(func.count(func.distinct(Video.channel_id)))
        .join(Keyword, Keyword.video_id == Video.video_id)
        .filter(Keyword.keyword == keyword)
        .scalar()
    )
    print(f"  이 키워드의 전체 기간 distinct 채널 수: {channel_count}")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        for kw in SUSPICIOUS_CASES:
            inspect_keyword(db, kw)
    finally:
        db.close()
