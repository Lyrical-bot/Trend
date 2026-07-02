import os
import sys
from sqlalchemy.orm import Session
from sqlalchemy import func

# Add root directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from sns_sensing.database.db import SessionLocal, engine, Base
from sns_sensing.models.models import Keyword, KeywordStat

def merge_keywords(db: Session, old_kw: str, new_kw: str):
    print(f"[{old_kw}] -> [{new_kw}] 병합 시작")
    
    # 1. KeywordStat 병합
    old_stats = db.query(KeywordStat).filter(KeywordStat.keyword == old_kw).all()
    for o_stat in old_stats:
        n_stat = db.query(KeywordStat).filter(
            KeywordStat.keyword == new_kw,
            KeywordStat.hour == o_stat.hour
        ).first()
        
        if n_stat:
            n_stat.mention_count += o_stat.mention_count
            n_stat.channel_count += o_stat.channel_count
            db.delete(o_stat)
        else:
            o_stat.keyword = new_kw
            
    # 2. Keyword 병합
    old_keywords = db.query(Keyword).filter(Keyword.keyword == old_kw).all()
    for o_kw in old_keywords:
        n_kw = db.query(Keyword).filter(
            Keyword.keyword == new_kw,
            Keyword.video_id == o_kw.video_id
        ).first()
        
        if n_kw:
            db.delete(o_kw) # 중복이면 기존 것 삭제
        else:
            o_kw.keyword = new_kw
            
    db.commit()
    print(f"[{old_kw}] -> [{new_kw}] 병합 완료")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        # 병합할 쌍들 (잘못 적재된 띄어쓰기 없는 버전을 있는 버전으로)
        merge_pairs = {
            "왁뿌소금빵": "왁뿌 소금빵",
            "두바이초콜릿": "두바이 초콜릿"
        }
        for old_k, new_k in merge_pairs.items():
            merge_keywords(db, old_k, new_k)
    except Exception as e:
        print(f"오류: {e}")
        db.rollback()
    finally:
        db.close()
