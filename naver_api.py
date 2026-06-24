import os
import httpx
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

load_dotenv()

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
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
            else:
                error_msg = f"네이버 API 호출 실패 (상태 코드: {response.status_code}): {response.text}"
                raise Exception(error_msg)
        except httpx.RequestError as exc:
            raise Exception(f"네이버 API 요청 중 네트워크 오류가 발생했습니다: {exc}")
