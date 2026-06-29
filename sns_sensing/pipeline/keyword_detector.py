"""
역할: 새롭게 등장한 신규 키워드를 감지합니다.
목적: 과거 DB에 존재하지 않던 키워드가 오늘 처음 발견되었는지를 판별하여 트렌드의 시작점(New Keyword) 신호를 제공합니다.
"""

from typing import List
from sqlalchemy.orm import Session
from sns_sensing.models.models import Keyword

def get_new_keywords(db: Session, extracted_keywords: List[str]) -> List[str]:
    """
    주어진 키워드 목록 중, DB(keywords 테이블)에 존재하지 않는 완전 신규 키워드만 필터링하여 반환합니다.
    """
    if not extracted_keywords:
        return []
    
    # DB에 이미 존재하는 키워드 목록 조회
    existing_keywords_query = db.query(Keyword.keyword).filter(Keyword.keyword.in_(extracted_keywords)).distinct()
    existing_keywords = {row[0] for row in existing_keywords_query.all()}
    
    # 신규 키워드 도출
    new_keywords = [kw for kw in extracted_keywords if kw not in existing_keywords]
    return new_keywords
