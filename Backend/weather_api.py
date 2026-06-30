import os
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
    import csv
    
    # 1. 5개년 날씨 CSV 파일들이 저장된 디렉토리 경로 지정
    #    os.path.dirname(os.path.abspath(__file__))를 사용하면 이 파일(weather_api.py)이 속한 Backend 폴더의 절대 경로를 얻습니다.
    #    그 아래 'data' 폴더 내의 CSV 파일들을 찾기 위해 os.path.join으로 최종 경로(Backend/data)를 생성합니다.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(current_dir, "data")
    
    # data 폴더가 실제로 존재하지 않으면 로그를 찍고 빈 리스트를 반환하여 에러 발생을 방지합니다.
    if not os.path.exists(data_dir):
        logger.error(f"로컬 기상 데이터 디렉토리를 찾을 수 없습니다: {data_dir}")
        return []
        
    # 2. API 호출 측에서 넘겨받은 날짜(start_date, end_date) 포맷이 'YYYY-MM-DD' 형식인지 문법 검증합니다.
    #    포맷이 틀리면 datetime 변환 시 ValueError가 발생하며 에러를 반환합니다.
    try:
        from datetime import datetime
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        logger.error(f"잘못된 날짜 포맷입니다. start_date: {start_date}, end_date: {end_date}")
        return []
        
    # 파싱된 최종 날씨 객체들을 임시 저장할 리스트
    combined = []
    
    # 3. data_dir 폴더 내에 있는 파일들 중 확장자가 '.csv'로 끝나는 모든 날씨 CSV 파일명을 스캔합니다.
    #    예: ['1.20250629~20260628정리.csv', '2.20240629~20250628정리.csv', ...]
    csv_files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    
    # 4. 각 CSV 파일들을 하나씩 순회하며 열어서 파싱합니다.
    for csv_file in csv_files:
        file_path = os.path.join(data_dir, csv_file)
        try:
            # utf-8-sig 인코딩은 한글 Excel 등에서 CSV 저장 시 붙는 3바이트 BOM(\ufeff)을 자동으로 제거해줍니다.
            with open(file_path, mode="r", encoding="utf-8-sig") as f:
                # csv.DictReader는 CSV의 첫 행(헤더)을 Key로 사용하여 행 단위 데이터를 딕셔너리로 읽어줍니다.
                reader = csv.DictReader(f)
                for row in reader:
                    # CSV 헤더 컬럼명 매핑: '날짜', '기온(°C)', '습도(%)', '강수량(mm)'
                    period = row.get("날짜")
                    if not period:
                        continue
                        
                    period = period.strip()
                    # 5. 사용자가 요청한 날짜 범위 [start_date, end_date] 사이에 속하는 행(Row)만 필터링합니다.
                    #    문자열 형식의 날짜('YYYY-MM-DD')는 알파벳 순서대로 대소비교(<=, >=)가 완벽히 가능합니다.
                    if start_date <= period <= end_date:
                        avg_ta_str = row.get("기온(°C)", "0.0")
                        sum_rn_str = row.get("강수량(mm)", "0.0")
                        
                        # 6. 문자열 기온값을 실수(float) 형태로 파싱합니다. (결측이나 공백 시 0.0으로 폴백)
                        try:
                            avg_ta = float(avg_ta_str) if avg_ta_str else 0.0
                        except ValueError:
                            avg_ta = 0.0
                            
                        # 7. 문자열 강수량값을 실수(float) 형태로 파싱합니다. (결측이나 공백 시 0.0으로 폴백)
                        try:
                            sum_rn = float(sum_rn_str) if sum_rn_str else 0.0
                        except ValueError:
                            sum_rn = 0.0
                            
                        # 기존 백엔드 API 호환 규격에 맞춰 period(날짜), avgTa(기온), sumRn(강수량) 필드로 변환합니다.
                        combined.append({
                            "period": period,
                            "avgTa": avg_ta,
                            "sumRn": sum_rn
                        })
        except Exception as e:
            logger.error(f"기상 데이터 파일 {csv_file} 파싱 에러: {e}")
            
    # 8. 서로 다른 csv 파일들 간에 날짜가 겹칠 수 있으므로 중복 날짜를 방지합니다.
    seen = set()
    final_list = []
    for w in combined:
        if w["period"] not in seen:
            seen.add(w["period"])
            final_list.append(w)
            
    return sorted(final_list, key=lambda x: x["period"])


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
