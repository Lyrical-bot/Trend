import os
import httpx
import logging
from dotenv import load_dotenv
from typing import List, Dict, Any

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .env 경로 지정
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "key", ".env")
load_dotenv(dotenv_path=dotenv_path)

ASOS_ENDPOINT = os.getenv("ASOS_ENDPOINT")
DATA_GO_KEY = os.getenv("DATA_GO_KEY")

async def _fetch_weather_data_chunk(start_date: str, end_date: str, stn_id: str = "108") -> List[Dict[str, Any]]:
    """
    1회 요청에 대한 기상청 단일 청크 데이터를 수집하는 헬퍼 함수
    """
    if not ASOS_ENDPOINT or not DATA_GO_KEY:
        logger.warning("기상청 API 엔드포인트 또는 인증키가 설정되지 않았습니다.")
        return []
        
    start_dt = start_date.replace("-", "")
    end_dt = end_date.replace("-", "")
    
    from datetime import datetime
    try:
        d1 = datetime.strptime(start_date, "%Y-%m-%d")
        d2 = datetime.strptime(end_date, "%Y-%m-%d")
        num_rows = max(10, abs((d2 - d1).days) + 10)
    except Exception:
        num_rows = 365
    
    url = f"{ASOS_ENDPOINT.rstrip('/')}/getWthrDataList"
    
    params = {
        "serviceKey": DATA_GO_KEY,
        "numOfRows": num_rows,
        "pageNo": 1,
        "dataType": "JSON",
        "dataCd": "ASOS",
        "dateCd": "DAY",
        "startDt": start_dt,
        "endDt": end_dt,
        "stnIds": stn_id
    }
    
    import asyncio
    
    async with httpx.AsyncClient() as client:
        max_retries = 3
        for retry in range(max_retries):
            try:
                response = await client.get(url, params=params, timeout=15.0)
                
                if response.status_code != 200:
                    raise Exception(f"기상청 API 상태 코드 오류: {response.status_code}")
                    
                res_data = response.json()
                body = res_data.get("response", {}).get("body", {})
                if not body:
                    raise Exception("기상청 API 응답 바디가 비어있습니다.")
                    
                items = body.get("items", {}).get("item", [])
                if isinstance(items, dict):
                    items = [items]
                    
                weather_list = []
                for item in items:
                    period = item.get("tm", "")
                    avg_ta = item.get("avgTa", "")
                    sum_rn = item.get("sumRn", "")
                    
                    try:
                        avg_ta = float(avg_ta) if avg_ta else 0.0
                    except ValueError:
                        avg_ta = 0.0
                        
                    try:
                        sum_rn = float(sum_rn) if sum_rn else 0.0
                    except ValueError:
                        sum_rn = 0.0
                        
                    weather_list.append({
                        "period": period,
                        "avgTa": avg_ta,
                        "sumRn": sum_rn
                    })
                    
                return weather_list
                
            except (httpx.RequestError, Exception) as exc:
                logger.warning(f"기상청 API 요청 실패 (시도 {retry + 1}/{max_retries}): {exc}")
                if retry == max_retries - 1:
                    logger.error(f"기상청 API 최종 수집 실패 (시도 {max_retries}회 모두 실패): {exc}")
                    return []
                # 일시적 오류 완화를 위해 0.5초 대기 후 재시도
                await asyncio.sleep(0.5)

async def fetch_weather_data(start_date: str, end_date: str, stn_id: str = "108") -> List[Dict[str, Any]]:
    """
    기간을 360일 단위 청크로 분할하여 기상청 API를 병렬(asyncio.gather)로 호출하고 병합 정렬하여 반환합니다.
    (동시 호출 수 제한을 위해 Semaphore를 적용하여 네트워크 오류를 방지합니다.)
    """
    from datetime import datetime, timedelta
    import asyncio
    
    # 오늘/미래 날짜는 기상청 API 차단(resultCode 99)을 유발하므로 최대 어제 날짜로 엄격히 제한
    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    if end_date >= today_str:
        end_date = yesterday_str
        
    try:
        d1 = datetime.strptime(start_date, "%Y-%m-%d")
        d2 = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        logger.error(f"잘못된 날짜 포맷입니다. start_date: {start_date}, end_date: {end_date}")
        return []
        
    if d1 > d2:
        return []
        
    # 기상청 API 동시 접속 제한(세마포어 2개) 설정
    sem = asyncio.Semaphore(2)
    
    async def sem_fetch(s_date: str, e_date: str):
        async with sem:
            return await _fetch_weather_data_chunk(s_date, e_date, stn_id)
        
    tasks = []
    curr = d1
    while curr <= d2:
        next_curr = min(curr + timedelta(days=360), d2)
        
        task = sem_fetch(
            curr.strftime("%Y-%m-%d"), 
            next_curr.strftime("%Y-%m-%d")
        )
        tasks.append(task)
        
        curr = next_curr + timedelta(days=1)
        
    results = await asyncio.gather(*tasks)
    
    # 모든 청크 결과 병합
    combined = []
    for r in results:
        combined.extend(r)
        
    # 날짜 중복 제거 및 정렬
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
        print("기상청 API 로컬 테스트 구동...")
        data = await fetch_weather_data("2025-06-01", "2025-06-10")
        print(f"조회된 데이터 수: {len(data)}")
        if data:
            print("첫 데이터 샘플:", data[0])
            
    asyncio.run(test())
