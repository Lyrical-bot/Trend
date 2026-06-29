import os
import httpx
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

# Backend/key/.env 경로를 동적으로 지정하여 환경 변수 로드
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

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(NAVER_API_URL, json=body, headers=headers, timeout=10.0)
            if response.status_code == 200:
                return response.json()
            # 429 (Too Many Requests) 또는 403 (Forbidden, 한도초과 등) 발생 시 예비 키로 Fallback
            elif response.status_code in [429, 403] and NAVER_CLIENT_ID2 and NAVER_CLIENT_SECRET2:
                print(f"[Info] 메인 네이버 API 키 오류({response.status_code}). 예비 키(Key 2)로 재시도합니다...")
                headers_fallback = {
                    "X-Naver-Client-Id": NAVER_CLIENT_ID2,
                    "X-Naver-Client-Secret": NAVER_CLIENT_SECRET2,
                    "Content-Type": "application/json"
                }
                response2 = await client.post(NAVER_API_URL, json=body, headers=headers_fallback, timeout=10.0)
                if response2.status_code == 200:
                    return response2.json()
                else:
                    error_msg = f"네이버 API 예비 키 호출 실패 (상태 코드: {response2.status_code}): {response2.text}"
                    raise Exception(error_msg)
            else:
                error_msg = f"네이버 API 호출 실패 (상태 코드: {response.status_code}): {response.text}"
                raise Exception(error_msg)
        except httpx.RequestError as exc:
            raise Exception(f"네이버 API 요청 중 네트워크 오류가 발생했습니다: {exc}")

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
    end_date_str = datetime.now().strftime("%Y-%m-%d")
    start_date_str = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://datalab.naver.com/shoppingInsight/sCategory.naver',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    all_keywords = []
    # 최대 페이지 수 계산 (한 페이지당 20개)
    pages = (count + 19) // 20
    
    async with httpx.AsyncClient() as client:
        try:
            for p in range(1, pages + 1):
                data = f"cid={cid}&timeUnit=date&startDate={start_date_str}&endDate={end_date_str}&age=&gender=&device=&page={p}&count=20"
                response = await client.post(url, headers=headers, content=data, timeout=10.0)
                if response.status_code == 200:
                    res_data = response.json()
                    ranks = res_data.get("ranks", [])
                    page_keywords = [item["keyword"] for item in ranks]
                    all_keywords.extend(page_keywords)
                    if len(all_keywords) >= count:
                        break
                else:
                    print(f"[Warning] 인기검색어 조회 실패 (상태 코드 {response.status_code}) - page {p}: {response.text[:100]}")
                    break
                await asyncio.sleep(0.1) # Rate limit 방어
            return all_keywords[:count]
        except Exception as e:
            print(f"[Error] 인기검색어 스크래핑 중 예외 발생: {e}")
            return all_keywords[:count]
