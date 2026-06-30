import os
import csv
import httpx
import logging
from dotenv import load_dotenv
from typing import List, Dict, Any

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .env 경로 지정 (주석 처리)
# dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
# load_dotenv(dotenv_path=dotenv_path)

# ASOS_ENDPOINT = os.getenv("ASOS_ENDPOINT")
# DATA_GO_KEY = os.getenv("DATA_GO_KEY")

# [주석 처리] 기상청 Open API 외부 호출 함수 비활성화
# async def _fetch_weather_data_chunk(start_date: str, end_date: str, stn_id: str = "108") -> List[Dict[str, Any]]:
#     if not ASOS_ENDPOINT or not DATA_GO_KEY:
#         logger.warning("기상청 API 엔드포인트 또는 인증키가 설정되지 않았습니다.")
#         return []
#         
#     start_dt = start_date.replace("-", "")
#     end_dt = end_date.replace("-", "")
#     
#     from datetime import datetime
#     try:
#         d1 = datetime.strptime(start_date, "%Y-%m-%d")
#         d2 = datetime.strptime(end_date, "%Y-%m-%d")
#         num_rows = max(10, abs((d2 - d1).days) + 10)
#     except Exception:
#         num_rows = 365
#     
#     url = f"{ASOS_ENDPOINT.rstrip('/')}/getWthrDataList"
#     
#     params = {
#         "serviceKey": DATA_GO_KEY,
#         "numOfRows": num_rows,
#         "pageNo": 1,
#         "dataType": "JSON",
#         "dataCd": "ASOS",
#         "dateCd": "DAY",
#         "startDt": start_dt,
#         "endDt": end_dt,
#         "stnIds": stn_id
#     }
#     
#     import asyncio
#     
#     async with httpx.AsyncClient() as client:
#         max_retries = 3
#         for retry in range(max_retries):
#             try:
#                 response = await client.get(url, params=params, timeout=15.0)
#                 if response.status_code != 200:
#                     raise Exception(f"기상청 API 상태 코드 오류: {response.status_code}")
#                     
#                 res_data = response.json()
#                 body = res_data.get("response", {}).get("body", {})
#                 if not body:
#                     raise Exception("기상청 API 응답 바디가 비어있습니다.")
#                     
#                 items = body.get("items", {}).get("item", [])
#                 if isinstance(items, dict):
#                     items = [items]
#                     
#                 weather_list = []
#                 for item in items:
#                     period = item.get("tm", "")
#                     avg_ta = item.get("avgTa", "")
#                     sum_rn = item.get("sumRn", "")
#                     
#                     try:
#                         avg_ta = float(avg_ta) if avg_ta else 0.0
#                     except ValueError:
#                         avg_ta = 0.0
#                         
#                     try:
#                         sum_rn = float(sum_rn) if sum_rn else 0.0
#                     except ValueError:
#                         sum_rn = 0.0
#                         
#                     weather_list.append({
#                         "period": period,
#                         "avgTa": avg_ta,
#                         "sumRn": sum_rn
#                     })
#                 return weather_list
#             except (httpx.RequestError, Exception) as exc:
#                 logger.warning(f"기상청 API 요청 실패 (시도 {retry + 1}/{max_retries}): {exc}")
#                 if retry == max_retries - 1:
#                     logger.error(f"기상청 API 최종 수집 실패 (시도 {max_retries}회 모두 실패): {exc}")
#                     return []
#                 await asyncio.sleep(0.5)

async def fetch_weather_data(start_date: str, end_date: str, stn_id: str = "108") -> List[Dict[str, Any]]:
    """
    기존 기상청 Open API 외부 호출을 전면 비활성화(주석 처리)하고, 
    Backend/data 폴더 하위의 5개년 로컬 날씨 CSV 데이터셋 파일들을 직접 파싱·정제하여 반환합니다.
    """
    # -------------------------------------------------------------
    # [추가 및 수정일자: 2026-06-30]
    # [수정내용: 기상 데이터 CSV 로드 시 매번 파일 I/O를 수행해
    #            속도가 심각하게(30~40초) 지연되던 병목을 해결하기 위해,
    #            서버 시작(모듈 로드) 시점에 5개년치 로컬 CSV 파일 전체를
    #            메모리에 전역 캐싱(_WEATHER_CACHE)하는 기법 도입.]
    # -------------------------------------------------------------
    global _WEATHER_CACHE
    
    # 캐시가 비어있으면 단 1회 로드합니다.
    if not _WEATHER_CACHE:
        _load_all_weather_to_cache()

    # 날짜 포맷 검증
    try:
        from datetime import datetime
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        logger.error(f"잘못된 날짜 포맷입니다. start_date: {start_date}, end_date: {end_date}")
        return []
        
    # 메모리에서 범위에 부합하는 날씨 데이터 슬라이싱 필터링 수행
    filtered_list = [
        w for w in _WEATHER_CACHE 
        if start_date <= w["period"] <= end_date
    ]
    return filtered_list

# 전역 기상 데이터 캐시 리스트
_WEATHER_CACHE: List[Dict[str, Any]] = []

def _load_all_weather_to_cache():
    """
    [추가 및 수정일자: 2026-06-30]
    [수정내용: Backend/data 폴더 아래의 모든 5개년 날씨 CSV 파일을 읽어 전역 캐시에 적재합니다.]
    """
    global _WEATHER_CACHE
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(current_dir, "data")
    
    if not os.path.exists(data_dir):
        logger.error(f"로컬 기상 데이터 디렉토리를 찾을 수 없습니다: {data_dir}")
        return
        
    combined = []
    csv_files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    
    for csv_file in csv_files:
        file_path = os.path.join(data_dir, csv_file)
        try:
            with open(file_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    period = row.get("날짜")
                    if not period:
                        continue
                    period = period.strip()
                    
                    avg_ta_str = row.get("기온(°C)", "0.0")
                    sum_rn_str = row.get("강수량(mm)", "0.0")
                    
                    try:
                        avg_ta = float(avg_ta_str) if avg_ta_str else 0.0
                    except ValueError:
                        avg_ta = 0.0
                        
                    try:
                        sum_rn = float(sum_rn_str) if sum_rn_str else 0.0
                    except ValueError:
                        sum_rn = 0.0
                        
                    combined.append({
                        "period": period,
                        "avgTa": avg_ta,
                        "sumRn": sum_rn
                    })
        except Exception as e:
            logger.error(f"기상 데이터 파일 {csv_file} 파싱 에러: {e}")
            
    # 중복 제거 및 날짜순 정렬
    seen = set()
    final_list = []
    for w in combined:
        if w["period"] not in seen:
            seen.add(w["period"])
            final_list.append(w)
            
    _WEATHER_CACHE = sorted(final_list, key=lambda x: x["period"])
    logger.info(f"기상 데이터 메모리 전역 캐시 적재 완료 (총 {len(_WEATHER_CACHE)}건)")

# 최초 기동 시 캐싱 미리 수행
_load_all_weather_to_cache()


if __name__ == "__main__":
    # 작동 테스트
    import asyncio
    
    async def test():
        print("로컬 5개년 CSV 기상 데이터 테스트 구동...")
        # 2022~2023년 데이터 일부 테스트 추출
        data = await fetch_weather_data("2022-07-01", "2022-07-10")
        print(f"조회된 데이터 수: {len(data)}")
        if data:
            print("첫 데이터 샘플:", data[0])
            print("마지막 데이터 샘플:", data[-1])
            
    asyncio.run(test())
