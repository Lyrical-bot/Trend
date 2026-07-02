import os
import time
import hmac
import hashlib
import base64
import httpx
from typing import List, Dict
from dotenv import load_dotenv
import json
import sys
from datetime import datetime

# Ensure sns_sensing is importable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sns_sensing.database.db import SessionLocal
from sns_sensing.models.models import ApiCache

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(dotenv_path=dotenv_path)

async def fetch_search_ad_volume(keywords: List[str]) -> Dict[str, float]:
    """
    네이버 검색광고 API(keywordstool)를 호출하여 각 키워드의 최근 한 달간 검색량(PC + 모바일)을 반환합니다.
    (키가 없을 경우 에러를 내지 않고 0.0을 반환하여 기존 기능이 마비되지 않도록 함)
    """
    license_key = os.getenv("NAVER_AD_LICENSE", "").strip()
    secret_key = os.getenv("NAVER_AD_SECRET", "").strip()
    customer_id = os.getenv("NAVER_AD_CUSTOMER_ID", "").strip()

    license_key2 = os.getenv("NAVER_AD_LICENSE2", "").strip()
    secret_key2 = os.getenv("NAVER_AD_SECRET2", "").strip()
    customer_id2 = os.getenv("NAVER_AD_CUSTOMER_ID2", "").strip()

    results = {k: 0.0 for k in keywords}

    if not license_key or not secret_key or not customer_id:
        print("[Warning] 네이버 검색광고 API 키가 설정되지 않아 절대 수치 환산을 건너뜁니다.")
        return results

    base_url = "https://api.searchad.naver.com"
    uri = "/keywordstool"
    method = "GET"

    # API 1회 호출 시 키워드 5개씩 나누어 조회 (안정성)
    chunk_size = 5
    for i in range(0, len(keywords), chunk_size):
        chunk = keywords[i:i+chunk_size]
        
        # 네이버 광고 API는 키워드 내의 공백(띄어쓰기)을 허용하지 않으므로 임시로 제거하여 조회합니다.
        query_chunk = [k.replace(" ", "") for k in chunk]
        mapping = {k.replace(" ", ""): k for k in chunk}
        hint_keywords = ",".join(query_chunk)
        
        # --- DB Caching Logic Start ---
        # 캐시 매핑 키는 사용자가 요청한 원본 텍스트(공백 포함) 기준으로 유지합니다.
        original_hint_keywords = ",".join(chunk)
        request_hash_str = json.dumps({"hintKeywords": original_hint_keywords}, sort_keys=True)
        request_hash = hashlib.sha256(request_hash_str.encode('utf-8')).hexdigest()
        date_key = datetime.now().strftime("%Y-%m-%d")
        
        db = SessionLocal()
        cached_result = None
        try:
            cached_record = db.query(ApiCache).filter(
                ApiCache.api_name == "naver_ad_volume",
                ApiCache.request_hash == request_hash,
                ApiCache.date_key == date_key
            ).first()
            if cached_record:
                cached_result = json.loads(cached_record.response_data)
        finally:
            db.close()
            
        if cached_result is not None:
            print(f"[Info] 캐시된 네이버 검색광고 API 데이터를 불러옵니다. ({original_hint_keywords})")
            for kw, vol in cached_result.items():
                if kw in results:
                    results[kw] = vol
            continue
        # --- DB Caching Logic End ---

        def _get_headers(l_key, s_key, c_id):
            ts = str(int(time.time() * 1000))
            msg = f"{ts}.{method}.{uri}"
            sig = hmac.new(
                s_key.encode("utf-8"),
                msg.encode("utf-8"),
                hashlib.sha256
            ).digest()
            sign = base64.b64encode(sig).decode("utf-8")
            return {
                "X-Timestamp": ts,
                "X-API-KEY": l_key,
                "X-Customer": c_id,
                "X-Signature": sign
            }

        headers = _get_headers(license_key, secret_key, customer_id)

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

                        if isinstance(pc_cnt, str) and '<' in pc_cnt:
                            pc_cnt = 5
                        if isinstance(mo_cnt, str) and '<' in mo_cnt:
                            mo_cnt = 5

                        # 공백이 제거된 응답 키워드를 매핑을 통해 원본 공백 포함 키워드로 환원
                        original_kw = mapping.get(kw)
                        if original_kw and original_kw in results:
                            results[original_kw] = float(pc_cnt) + float(mo_cnt)
                            
                    # --- DB Caching Save Start ---
                    db = SessionLocal()
                    try:
                        chunk_results = {k: results[k] for k in chunk if k in results}
                        new_cache = ApiCache(
                            api_name="naver_ad_volume",
                            request_hash=request_hash,
                            date_key=date_key,
                            response_data=json.dumps(chunk_results, ensure_ascii=False)
                        )
                        db.add(new_cache)
                        db.commit()
                    except Exception as e:
                        pass
                    finally:
                        db.close()
                    # --- DB Caching Save End ---
                    
                elif response.status_code == 429 and license_key2 and secret_key2 and customer_id2:
                    print(f"[Info] 메인 검색광고 API 키 오류({response.status_code}). 예비 키(Key 2)로 재시도합니다...")
                    headers_fallback = _get_headers(license_key2, secret_key2, customer_id2)
                    response2 = await client.get(base_url + uri, headers=headers_fallback, params=params, timeout=10.0)
                    if response2.status_code == 200:
                        data_list2 = response2.json().get('keywordList', [])
                        for item in data_list2:
                            kw = item.get('relKeyword')
                            pc_cnt = item.get('monthlyPcQcCnt', 0)
                            mo_cnt = item.get('monthlyMobileQcCnt', 0)
                            if isinstance(pc_cnt, str) and '<' in pc_cnt: pc_cnt = 5
                            if isinstance(mo_cnt, str) and '<' in mo_cnt: mo_cnt = 5
                            
                            original_kw = mapping.get(kw)
                            if original_kw and original_kw in results:
                                results[original_kw] = float(pc_cnt) + float(mo_cnt)
                                
                        # --- DB Caching Save Start ---
                        db = SessionLocal()
                        try:
                            chunk_results = {k: results[k] for k in chunk if k in results}
                            new_cache = ApiCache(
                                api_name="naver_ad_volume",
                                request_hash=request_hash,
                                date_key=date_key,
                                response_data=json.dumps(chunk_results, ensure_ascii=False)
                            )
                            db.add(new_cache)
                            db.commit()
                        except Exception as e:
                            pass
                        finally:
                            db.close()
                        # --- DB Caching Save End ---
                    else:
                        print(f"[Error] 검색광고 예비 키 호출 실패 (상태 코드 {response2.status_code}): {response2.text}")
                else:
                    print(f"[Error] 검색광고 API 호출 실패 (상태 코드 {response.status_code}): {response.text}")
            except Exception as e:
                print(f"[Error] 검색광고 API 호출 중 예외 발생: {e}")
                
    return results
