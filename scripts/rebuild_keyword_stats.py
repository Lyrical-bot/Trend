import os
import sys
import argparse
from collections import defaultdict
from sqlalchemy import func

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from sns_sensing.database.db import SessionLocal
from sns_sensing.models.models import Keyword, Video, VideoStat, KeywordStat

# 독립 검증 스크립트로 이미 확인된 정답 (mention_count, channel_count)
# 재구축 결과가 이 값들과 일치하지 않으면 자동으로 실행을 중단한다.
GROUND_TRUTH = {
    "Pistachio Dubai Chocolate": {"mention_count": 1, "channel_count": None},  # channel_count는 미확인 -> None
    "Dubai Chocolate Pancakes": {"mention_count": 4, "channel_count": None},
    "왁뿌 소금빵": {"mention_count": 9, "channel_count": None},
    "크루키": {"mention_count": 18, "channel_count": 7},
}


def build_new_stats(db):
    """
    새 KeywordStat 데이터를 메모리에 딕셔너리로 구성한다. DB에는 아직 아무것도 쓰지 않는다.
    key: (keyword, bucket_hour) -> {"mention_count": int, "channel_ids": set()}
    """
    # 1. 비디오별 최초 VideoStat.hour (진짜 버킷) 서브쿼리
    first_bucket_subq = (
        db.query(
            VideoStat.video_id,
            func.min(VideoStat.hour).label("first_hour"),
        )
        .group_by(VideoStat.video_id)
        .subquery()
    )

    # 2. Keyword + Video + 최초버킷 조인
    rows = (
        db.query(
            Keyword.keyword,
            first_bucket_subq.c.first_hour,
            Video.channel_id,
        )
        .join(Video, Keyword.video_id == Video.video_id)
        .join(first_bucket_subq, Video.video_id == first_bucket_subq.c.video_id)
        .all()
    )

    grouped = defaultdict(lambda: {"mention_count": 0, "channel_ids": set()})
    for keyword, bucket_hour, channel_id in rows:
        key = (keyword, bucket_hour)
        grouped[key]["mention_count"] += 1
        grouped[key]["channel_ids"].add(channel_id)

    return grouped


def summarize_by_keyword(grouped):
    """검증용: 키워드 전체 기간 총합으로 요약 (bucket 무시하고 GROUND_TRUTH와 대조하기 위함)"""
    summary = defaultdict(lambda: {"mention_count": 0, "channel_ids": set()})
    for (keyword, _hour), data in grouped.items():
        summary[keyword]["mention_count"] += data["mention_count"]
        summary[keyword]["channel_ids"] |= data["channel_ids"]
    return summary


def verify_against_ground_truth(summary) -> bool:
    all_ok = True
    print("\n=== Ground Truth 대조 ===")
    for keyword, expected in GROUND_TRUTH.items():
        actual = summary.get(keyword)
        if actual is None:
            print(f"  [FAIL] '{keyword}' - 재구축 결과에 존재하지 않음 (기대: {expected})")
            all_ok = False
            continue

        actual_mentions = actual["mention_count"]
        actual_channels = len(actual["channel_ids"])

        mention_ok = actual_mentions == expected["mention_count"]
        channel_ok = (
            expected["channel_count"] is None
            or actual_channels == expected["channel_count"]
        )

        status = "OK" if (mention_ok and channel_ok) else "FAIL"
        if status == "FAIL":
            all_ok = False

        print(
            f"  [{status}] '{keyword}' - "
            f"mention_count 기대:{expected['mention_count']} 실제:{actual_mentions} | "
            f"channel_count 기대:{expected['channel_count']} 실제:{actual_channels}"
        )

    return all_ok


def commit_new_stats(db, grouped):
    print("\n=== 기존 KeywordStat 삭제 및 재생성 실행 ===")
    db.query(KeywordStat).delete()

    new_rows = []
    for (keyword, bucket_hour), data in grouped.items():
        new_rows.append(
            KeywordStat(
                keyword=keyword,
                hour=bucket_hour,
                mention_count=data["mention_count"],
                channel_count=len(data["channel_ids"]),
            )
        )
    db.bulk_save_objects(new_rows)
    db.commit()
    print(f"재생성 완료: 총 {len(new_rows)}개 버킷 삽입됨")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--commit",
        action="store_true",
        help="실제로 DB에 반영 (기본값은 dry-run, DB를 건드리지 않음)",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        grouped = build_new_stats(db)
        summary = summarize_by_keyword(grouped)

        ok = verify_against_ground_truth(summary)

        if not ok:
            print(
                "\n[중단] Ground Truth와 불일치하는 항목이 있습니다. "
                "DB는 전혀 건드리지 않았습니다. 재구축 로직을 다시 점검해주세요."
            )
            sys.exit(1)

        print("\n[통과] 모든 Ground Truth 케이스 일치.")

        if args.commit:
            commit_new_stats(db, grouped)
        else:
            print(
                "\n[dry-run 모드] 검증만 수행했고 DB는 변경되지 않았습니다. "
                "실제 반영하려면 --commit 옵션을 붙여 재실행하세요."
            )
    except Exception as e:
        print(f"오류: {e}")
        db.rollback()
    finally:
        db.close()
