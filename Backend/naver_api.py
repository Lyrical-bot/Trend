import os
import httpx
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
import json
import hashlib
from datetime import datetime
import sys

# Ensure sns_sensing is importable from Backend/naver_api.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sns_sensing.database.db import SessionLocal
from sns_sensing.models.models import ApiCache

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(dotenv_path=dotenv_path)

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
NAVER_CLIENT_ID2 = os.getenv("NAVER_CLIENT_ID2")
NAVER_CLIENT_SECRET2 = os.getenv("NAVER_CLIENT_SECRET2")
NAVER_API_URL = "https://openapi.naver.com/v1/datalab/search"

async def fetch_naver_trend(
    start_date: str,
    end_date: str,
    time_unit: str,
    keyword_groups: List[Dict[str, Any]],
    device: Optional[str] = None,
    gender: Optional[str] = None,
    ages: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    네이버 통합 검색어 트렌드 API를 호출하여 과거 데이터를 수집합니다.
    """
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET or NAVER_CLIENT_ID.startswith("YOUR_") or NAVER_CLIENT_SECRET.startswith("YOUR_"):
        raise ValueError("네이버 API 클라이언트 ID 및 Secret이 올바르게 설정되지 않았습니다. .env 파일을 확인해 주세요.")

    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        "Content-Type": "application/json"
    }

    body = {
        "startDate": start_date,
        "endDate": end_date,
        "timeUnit": time_unit,
        "keywordGroups": keyword_groups
    }

    if device:
        body["device"] = device
    if gender:
        body["gender"] = gender
    if ages:
        body["ages"] = ages

    # --- DB Caching Logic Start ---
    request_hash_str = json.dumps(body, sort_keys=True)
    request_hash = hashlib.sha256(request_hash_str.encode('utf-8')).hexdigest()
    date_key = datetime.now().strftime("%Y-%m-%d")
    
    db = SessionLocal()
    try:
        cached_record = db.query(ApiCache).filter(
            ApiCache.api_name == "naver_trend",
            ApiCache.request_hash == request_hash,
            ApiCache.date_key == date_key
        ).first()
        
        if cached_record:
            print("[Info] 캐시된 네이버 트렌드 API 데이터를 불러옵니다.")
            return json.loads(cached_record.response_data)
    finally:
        db.close()
    # --- DB Caching Logic End ---

    import asyncio
    
    async with httpx.AsyncClient() as client:
        max_retries = 3
        for retry in range(max_retries):
            try:
                response = await client.post(NAVER_API_URL, json=body, headers=headers, timeout=20.0)
                if response.status_code == 200:
                    res_json = response.json()
                    # --- DB Caching Save Start ---
                    db = SessionLocal()
                    try:
                        new_cache = ApiCache(
                            api_name="naver_trend",
                            request_hash=request_hash,
                            date_key=date_key,
                            response_data=json.dumps(res_json, ensure_ascii=False)
                        )
                        db.add(new_cache)
                        db.commit()
                    except Exception as e:
                        print(f"[Warning] 캐시 저장 실패: {e}")
                    finally:
                        db.close()
                    # --- DB Caching Save End ---
                    return res_json
                # 429 (Too Many Requests) 또는 403 (Forbidden, 한도초과 등) 발생 시 예비 키로 Fallback
                elif response.status_code in [429, 403] and NAVER_CLIENT_ID2 and NAVER_CLIENT_SECRET2:
                    print(f"[Info] 메인 네이버 API 키 오류({response.status_code}). 예비 키(Key 2)로 재시도합니다...")
                    headers_fallback = {
                        "X-Naver-Client-Id": NAVER_CLIENT_ID2,
                        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET2,
                        "Content-Type": "application/json"
                    }
                    response2 = await client.post(NAVER_API_URL, json=body, headers=headers_fallback, timeout=20.0)
                    if response2.status_code == 200:
                        res_json2 = response2.json()
                        db = SessionLocal()
                        try:
                            new_cache = ApiCache(
                                api_name="naver_trend",
                                request_hash=request_hash,
                                date_key=date_key,
                                response_data=json.dumps(res_json2, ensure_ascii=False)
                            )
                            db.add(new_cache)
                            db.commit()
                        except Exception as e:
                            pass
                        finally:
                            db.close()
                        return res_json2
                    else:
                        error_msg = f"네이버 API 예비 키 호출 실패 (상태 코드: {response2.status_code}): {response2.text}"
                        raise Exception(error_msg)
                else:
                    error_msg = f"네이버 API 호출 실패 (상태 코드: {response.status_code}): {response.text}"
                    raise Exception(error_msg)
            except httpx.RequestError as exc:
                if retry == max_retries - 1:
                    raise Exception(f"네이버 API 요청 중 네트워크 오류가 발생했습니다 ({type(exc).__name__}): {exc}")
                await asyncio.sleep(0.5)

async def fetch_datalab_top_keywords(
    cid: str = "50022619", # 기본값: 스낵/과자 카테고리
    count: int = 20,
    days_ago: int = 30
) -> List[str]:
    """
    네이버 데이터랩 쇼핑인사이트 웹 페이지의 숨겨진 내부 API를 호출하여,
    해당 카테고리의 실제 인기 검색어(Top 순위)를 동적으로 스크래핑합니다.
    """
    from datetime import datetime, timedelta
    
    import asyncio
    
    url = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
    # 안정적인 데이터 조회를 위해 '오늘'이 아닌 완전히 마감된 '어제'를 기준으로 삼습니다.
    end_date = datetime.now() - timedelta(days=1)
    end_date_str = end_date.strftime("%Y-%m-%d")
    start_date_str = (end_date - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://datalab.naver.com/shoppingInsight/sCategory.naver',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    # --- DB Caching Logic Start ---
    request_params = {"cid": cid, "count": count, "days_ago": days_ago}
    request_hash_str = json.dumps(request_params, sort_keys=True)
    request_hash = hashlib.sha256(request_hash_str.encode('utf-8')).hexdigest()
    date_key = datetime.now().strftime("%Y-%m-%d")
    
    db = SessionLocal()
    try:
        cached_record = db.query(ApiCache).filter(
            ApiCache.api_name == "naver_datalab_top",
            ApiCache.request_hash == request_hash,
            ApiCache.date_key == date_key
        ).first()
        
        if cached_record:
            print("[Info] 캐시된 네이버 데이터랩 탑 키워드 데이터를 불러옵니다.")
            return json.loads(cached_record.response_data)
    finally:
        db.close()
    # --- DB Caching Logic End ---

    all_keywords = []
    # 최대 페이지 수 계산 (한 페이지당 20개)
    pages = (count + 19) // 20
    
    async with httpx.AsyncClient() as client:
        try:
            for p in range(1, pages + 1):
                data = f"cid={cid}&timeUnit=date&startDate={start_date_str}&endDate={end_date_str}&age=&gender=&device=&page={p}&count=20"
                
                # 재시도 로직
                max_retries = 3
                for retry in range(max_retries):
                    response = await client.post(url, headers=headers, content=data, timeout=10.0)
                    if response.status_code == 200:
                        res_data = response.json()
                        ranks = res_data.get("ranks", [])
                        page_keywords = [item["keyword"] for item in ranks]
                        all_keywords.extend(page_keywords)
                        break
                    elif response.status_code == 429:
                        print(f"[Warning] 429 Rate Limit 도달 (page {p}). 2초 대기 후 재시도 ({retry+1}/{max_retries})...")
                        await asyncio.sleep(2.0)
                        if retry == max_retries - 1:
                            print(f"[Error] 최대 재시도 횟수 초과. 스크래핑 중단.")
                    else:
                        print(f"[Warning] 인기검색어 조회 실패 (상태 코드 {response.status_code}) - page {p}: {response.text[:100]}")
                        break
                
                if response.status_code != 200:
                    break
                    
                if len(all_keywords) >= count:
                    break
                await asyncio.sleep(0.5) # Rate limit 방어 (0.3 -> 0.5)
            
            # --- DB Caching Save Start ---
            result_keywords = all_keywords[:count]
            db = SessionLocal()
            try:
                new_cache = ApiCache(
                    api_name="naver_datalab_top",
                    request_hash=request_hash,
                    date_key=date_key,
                    response_data=json.dumps(result_keywords, ensure_ascii=False)
                )
                db.add(new_cache)
                db.commit()
            except Exception as e:
                pass
            finally:
                db.close()
            # --- DB Caching Save End ---
            
            return result_keywords

        except Exception as e:
            print(f"[Error] 인기검색어 스크래핑 중 예외 발생: {e}")
            return all_keywords[:count]
