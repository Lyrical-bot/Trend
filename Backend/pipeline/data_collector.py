import os
import sys
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 부모 폴더(프로젝트 최상위)를 시스템 경로에 추가하여 기존 API 모듈 임포트 가능하게 함
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from naver_api import fetch_naver_trend
from naver_ad_api import fetch_search_ad_volume

# 환경변수 로드
load_dotenv(os.path.join(parent_dir, '.env'))

# 사용자님이 요청하신 핵심 5개 키워드 + F&B 15개 키워드 (총 20개)
KEYWORDS = [
    "봄동비빔밥", "버터떡", "두쫀쿠", "두바이쫀득쿠키", "창억떡", 
    "피스타치오", "카다이프", "요아정", "약과", "두바이초콜릿", 
    "마라탕", "탕후루", "황치즈", "흑임자", "납작당면", 
    "엽떡", "불닭볶음면", "크룽지", "소금빵", "탕종식빵"
]

async def collect_data():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] F&B 타겟 키워드 {len(KEYWORDS)}개 데이터 수집 시작...")
    
    # 1. 수집 기간: 오늘로부터 과거 3년 3개월 (약 1185일)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1185)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # 2. 검색광고 API를 이용해 최근 한 달간의 절대 검색량(건수) 일괄 조회
    print("▶ 네이버 검색광고 API (절대 건수) 조회 중...")
    ad_volumes = await fetch_search_ad_volume(KEYWORDS)
    print("▶ 네이버 검색광고 API 수집 완료.")
    
    all_records = []
    
    # 네이버 데이터랩 API는 한 번 요청 시 최대 5개 키워드까지만 허용됨. 5개씩 쪼개서 요청 (총 4번)
    chunk_size = 5
    for i in range(0, len(KEYWORDS), chunk_size):
        chunk = KEYWORDS[i:i+chunk_size]
        # 각 키워드를 개별 그룹으로 묶어 요청 (그래야 키워드별 개별 그래프가 나옴)
        groups = [{"groupName": kw, "keywords": [kw]} for kw in chunk]
        
        print(f"▶ 데이터랩 API (트렌드 비율) 조회 중... ({i+1}~{min(i+chunk_size, len(KEYWORDS))}/{len(KEYWORDS)})")
        
        try:
            naver_response = await fetch_naver_trend(
                start_date=start_str,
                end_date=end_str,
                time_unit="date", # 일별 데이터 수집
                keyword_groups=groups,
                device="",
                gender="",
                ages=[]
            )
            
            results = naver_response.get("results", [])
            for group in results:
                keyword = group.get("title")
                data = group.get("data", [])
                
                monthly_volume = ad_volumes.get(keyword, 0.0)
                
                # 스케일링을 위해 가장 최근 30일(1달)치 비율의 총합을 구함
                recent_30_data = data[-30:] if len(data) >= 30 else data
                total_ratios = sum(item["ratio"] for item in recent_30_data)
                
                multiplier = 0.0
                if total_ratios > 0 and monthly_volume > 0:
                    multiplier = monthly_volume / total_ratios
                
                for item in data:
                    all_records.append({
                        "keyword": keyword,
                        "date": item["period"],
                        "ratio_raw": item["ratio"], # 순수 트렌드 퍼센트
                        "search_volume_est": round(item["ratio"] * multiplier, 0) # 실제 건수 환산 수치
                    })
                    
        except Exception as e:
            print(f"[오류 발생] {chunk} 조회 중 실패: {e}")
            
        # 네이버 API 호출 제한(Rate Limit)을 피하기 위해 1.5초 대기
        await asyncio.sleep(1.5)

    # 3. 수집된 모든 데이터를 Pandas 데이터프레임으로 변환하여 CSV 저장
    if all_records:
        df = pd.DataFrame(all_records)
        dataset_dir = os.path.join(parent_dir, "datasets")
        if not os.path.exists(dataset_dir):
            os.makedirs(dataset_dir)
            
        csv_path = os.path.join(dataset_dir, "historical_fb_data.csv")
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 총 {len(df)}건의 일자별 데이터 수집 및 CSV 저장 완료!")
        print(f"저장 경로: {csv_path}")
    else:
        print("\n수집된 데이터가 없어 CSV 파일을 생성하지 못했습니다.")

if __name__ == "__main__":
    asyncio.run(collect_data())
