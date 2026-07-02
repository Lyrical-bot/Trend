import os
import sys
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from sns_sensing.database.db import SessionLocal
from sns_sensing.models.models import Keyword, KeywordStat, Video

def run_recalc():
    db = SessionLocal()
    try:
        stats = db.query(KeywordStat).all()
        for stat in stats:
            # We need to find videos that match this stat's hour bucket.
            # Since backfill uses published_at (hour=0) and runner uses collected_at,
            # we will find videos linked to this keyword whose derived hour matches.
            
            # For simplicity and idempotency, we can just look at the exact Video records linked to this keyword.
            videos_for_kw = db.query(Video).join(Keyword).filter(Keyword.keyword == stat.keyword).all()
            
            matching_vids = []
            matching_channels = set()
            
            for v in videos_for_kw:
                # Decide which bucket this video belongs to
                # If collected_at is close to published_at (e.g. runner), use collected_at
                # If backfilled (collected_at is way later than published_at), it was bucketed by published_at hour=0
                if (v.collected_at - v.published_at).days >= 1:
                    bucket = v.published_at.replace(hour=0, minute=0, second=0, microsecond=0)
                else:
                    bucket = v.collected_at.replace(minute=0, second=0, microsecond=0)
                    
                if bucket == stat.hour:
                    matching_vids.append(v.video_id)
                    matching_channels.add(v.channel_id)
            
            new_mention_count = len(matching_vids)
            new_channel_count = len(matching_channels)
            
            if stat.mention_count != new_mention_count or stat.channel_count != new_channel_count:
                print(f"[{stat.keyword} | {stat.hour}] 기존(M:{stat.mention_count}, C:{stat.channel_count}) -> 재계산(M:{new_mention_count}, C:{new_channel_count})")
                stat.mention_count = new_mention_count
                stat.channel_count = new_channel_count
                
        db.commit()
        print("재계산 완료!")
    except Exception as e:
        print(f"오류: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_recalc()
