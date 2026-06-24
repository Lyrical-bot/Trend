import os
import time
import hmac
import hashlib
import base64
import httpx
from typing import List, Dict

async def fetch_search_ad_volume(keywords: List[str]) -> Dict[str, float]:
    """
    네이버 검색광고 API(keywordstool)를 호출하여 각 키워드의 최근 한 달간 검색량(PC + 모바일)을 반환합니다.
    (키가 없을 경우 에러를 내지 않고 0.0을 반환하여 기존 기능이 마비되지 않도록 함)
    """
    license_key = os.getenv("NAVER_AD_LICENSE", "").strip()
    secret_key = os.getenv("NAVER_AD_SECRET", "").strip()
    customer_id = os.getenv("NAVER_AD_CUSTOMER_ID", "").strip()

    results = {k: 0.0 for k in keywords}

    if not license_key or not secret_key or not customer_id:
        print("[Warning] 네이버 검색광고 API 키가 설정되지 않아 절대 수치 환산을 건너뜁니다.")
        return results

    base_url = "https://api.naver.com"
    uri = "/keywordstool"
    method = "GET"

    # API 1회 호출 시 키워드 5개씩 나누어 조회 (안정성)
    chunk_size = 5
    for i in range(0, len(keywords), chunk_size):
        chunk = keywords[i:i+chunk_size]
        hint_keywords = ",".join(chunk)

        # 서명 생성 로직 (HMAC-SHA256)
        timestamp = str(int(time.time() * 1000))
        message = f"{timestamp}.{method}.{uri}"
        signature = hmac.new(
            secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).digest()
        sign = base64.b64encode(signature).decode("utf-8")

        headers = {
            "X-Timestamp": timestamp,
            "X-API-KEY": license_key,
            "X-Customer": customer_id,
            "X-Signature": sign
        }

        params = {
            "hintKeywords": hint_keywords,
            "showDetail": "1"
        }

        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                response = await client.get(base_url + uri, headers=headers, params=params, timeout=10.0)
                if response.status_code == 200:
                    data_list = response.json().get('keywordList', [])
                    for item in data_list:
                        kw = item.get('relKeyword')
                        pc_cnt = item.get('monthlyPcQcCnt', 0)
                        mo_cnt = item.get('monthlyMobileQcCnt', 0)

                        # '< 10' 과 같이 숫자가 아닐 경우를 대비
                        if isinstance(pc_cnt, str) and '<' in pc_cnt:
                            pc_cnt = 5
                        if isinstance(mo_cnt, str) and '<' in mo_cnt:
                            mo_cnt = 5

                        if kw in results:
                            results[kw] = float(pc_cnt) + float(mo_cnt)
                else:
                    print(f"[Error] 검색광고 API 호출 실패 (상태 코드 {response.status_code}): {response.text}")
            except Exception as e:
                print(f"[Error] 검색광고 API 호출 중 예외 발생: {e}")
                
    return results
