import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from naver_api import fetch_naver_trend
from forecaster import forecast_trend, evaluate_trend_accuracy
from naver_ad_api import fetch_search_ad_volume
try:
    from meta_api import get_meta_accounts
except ImportError:
    get_meta_accounts = None

from weather_api import fetch_weather_data

def _get_scale_multiplier(data_list: list, monthly_volume: float, days_queried: int, time_unit: str = "date") -> float:
    """네이버 비율값(0~100)을 실제 검색 건수로 환산하기 위한 배수를 계산합니다."""
    if monthly_volume <= 0 or not data_list:
        return 1.0
        
    # 광고 데이터(monthly_volume)가 '최근 30일' 기준이므로, 비율 총합도 '최근 30일' 치만 사용해야 10년 치 왜곡이 없습니다.
    recent_data = data_list[-30:] if len(data_list) >= 30 else data_list
    recent_days = len(recent_data)
    
    if time_unit == 'week':
        recent_days *= 7
    elif time_unit == 'month':
        recent_days *= 30
        
    total_ratio = sum(item["ratio"] for item in recent_data)
    estimated_monthly = (total_ratio / max(1, recent_days)) * 30
    return monthly_volume / estimated_monthly if estimated_monthly > 0 else 1.0

def _apply_scaling(items: list, multiplier: float, keys=("ratio", "yhat_lower", "yhat_upper")):
    """데이터 리스트의 지정된 키들에 배수를 곱합니다."""
    for item in items:
        for key in keys:
            if key in item:
                item[key] = round(item[key] * multiplier, 0)

# 가속도 랭킹 모듈 임포트 (언제든 뗄 수 있는 독립 구조)
try:
    from pipeline.velocity_model import get_velocity_ranking
except ImportError:
    get_velocity_ranking = None

# Weak Signal 감지 엔진 모듈 임포트
try:
    from pipeline.services.trend_detector import detect_weak_signals
except ImportError:
    detect_weak_signals = None

try:
    from pipeline.services.early_signal_detector import detect_early_signals
except ImportError:
    detect_early_signals = None

app = FastAPI(title="네이버 데이터랩 트렌드 예측 API", description="네이버 검색어 트렌드를 수집하고 시계열 예측을 제공하는 서비스")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === [SNS Sensing MVP (YouTube) 라우터 마운트] ===
import sys
# Backend 폴더가 아닌 최상위 루트 폴더를 경로에 추가해야 sns_sensing을 찾을 수 있습니다.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from sns_sensing.api.main import router as sns_router
    app.include_router(sns_router, prefix="/api/sns", tags=["SNS Sensing MVP"])
except ImportError as e:
    print(f"SNS Sensing 모듈을 불러올 수 없습니다: {e}")
# ===============================================


@app.on_event("startup")
def startup_event():
    try:
        from pipeline.scheduler import init_scheduler
        init_scheduler()
    except ImportError as e:
        print(f"Scheduler module not found: {e}")


# API 요청 스키마 정의
class KeywordGroup(BaseModel):
    groupName: str
    keywords: List[str]

class PredictRequest(BaseModel):
    startDate: str = Field(..., description="조회 시작 날짜 (YYYY-MM-DD)")
    endDate: str = Field(..., description="조회 종료 날짜 (YYYY-MM-DD)")
    timeUnit: str = Field("date", description="구간 단위 (date, week, month)")
    keywordGroups: List[KeywordGroup] = Field(..., description="비교 분석할 키워드 그룹 목록")
    device: Optional[str] = Field(None, description="기기 구분 (pc/mobile, 생략 시 전체)")
    gender: Optional[str] = Field(None, description="성별 구분 (f/m, 생략 시 전체)")
    ages: Optional[List[str]] = Field(None, description="연령대 목록 (생략 시 전체)")
    forecastSteps: int = Field(30, description="예측할 기간의 수 (일/주/월 단위)")

class PredictKeywordRequest(BaseModel):
    keyword: str = Field(..., description="조회할 단일 키워드")
    forecastSteps: int = Field(30, description="예측할 기간(일)의 수")

class EvaluateRequest(BaseModel):
    keyword: str = Field(..., description="백테스트할 단일 키워드")
    testDays: int = Field(15, description="테스트 구간 일수 (기본: 15일)")

@app.post("/api/predict")
async def predict_trend(payload: PredictRequest):
    try:
        # 0. 모든 키워드를 수집하여 검색광고 API(절대 검색량) 비동기 호출
        all_keywords = []
        for g in payload.keywordGroups:
            all_keywords.extend(g.keywords)
        all_keywords = list(set(all_keywords)) # 중복 제거
        
        ad_volumes = await fetch_search_ad_volume(all_keywords)

        # 1. 네이버 데이터랩 API 및 기상청 API 병렬 호출
        import asyncio
        groups = [{"groupName": g.groupName, "keywords": g.keywords} for g in payload.keywordGroups]
        
        naver_task = fetch_naver_trend(
            start_date=payload.startDate,
            end_date=payload.endDate,
            time_unit=payload.timeUnit,
            keyword_groups=groups,
            device=payload.device,
            gender=payload.gender,
            ages=payload.ages
        )
        weather_task = fetch_weather_data(
            start_date=payload.startDate,
            end_date=payload.endDate
        )
        
        naver_response, weather_data = await asyncio.gather(naver_task, weather_task)

        results = naver_response.get("results", [])
        response_data = []

        # 2. 각 키워드 그룹별로 과거 데이터 정제 및 미래 예측 수행
        for group in results:
            title = group.get("title")
            keywords = group.get("keywords")
            data = group.get("data", [])

            # 그룹 내 키워드들의 총 실제 검색량 합산 (월간 기준)
            group_monthly_volume = sum([ad_volumes.get(k, 0.0) for k in keywords])

            # 과거 데이터에 isForecast: False 설정
            historical = []
            for item in data:
                historical.append({
                    "period": item["period"],
                    "ratio": item["ratio"],
                    "isForecast": False
                })

            # 시계열 예측 모델 수행
            forecasted, summary = forecast_trend(
                historical_data=historical,
                time_unit=payload.timeUnit,
                forecast_steps=payload.forecastSteps
            )

            # --- 전조 감지: 스케일링 적용 전에 원본 비율값(0~100)으로 수행 ---
            signals = detect_early_signals(historical) if detect_early_signals else []

            # --- 스케일링 로직 추가 (비율 0~100 -> 실제 검색량(건)) ---
            multiplier = _get_scale_multiplier(historical, group_monthly_volume, len(historical), payload.timeUnit)
            if multiplier != 1.0:
                _apply_scaling(historical, multiplier)
                _apply_scaling(forecasted, multiplier)
                
                # summary 수치 업데이트
                summary["lastHistoricalValue"] = round(summary["lastHistoricalValue"] * multiplier, 0)
                summary["lastForecastValue"] = round(summary["lastForecastValue"] * multiplier, 0)
                summary["maxRatio"] = round(summary["maxRatio"] * multiplier, 0)

                # signal 내부의 volume 값도 스케일링
                for sig in signals:
                    if "volume" in sig:
                        sig["volume"] = round(sig["volume"] * multiplier, 0)

            # 과거 + 예측 데이터 병합
            combined_data = historical + forecasted

            response_data.append({
                "title": title,
                "keywords": keywords,
                "data": combined_data,
                "signals": signals,
                "summary": summary
            })

        return {
            "startDate": naver_response.get("startDate"),
            "endDate": naver_response.get("endDate"),
            "timeUnit": naver_response.get("timeUnit"),
            "results": response_data,
            "weather": weather_data
        }

    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

# === [가속도 랭킹 API 연동부] ===
@app.get("/api/velocity-ranking")
async def get_velocity_ranking_api(start_date: Optional[str] = None, end_date: Optional[str] = None, use_live: bool = True):
    """
    날짜를 지정하면 해당 기간 기준으로 재계산하고, 날짜가 없거나 실시간 데이터가 부족하면 최신 캐시를 반환합니다.
    """
    from pipeline.scheduler import VELOCITY_CACHE, LOCK_FILE
    import json
    
    has_custom_range = bool(start_date and end_date)

    # 1. 캐시 데이터가 존재하면 우선적으로 캐시를 반환하여 데이터 유실 404 에러를 방지합니다.
    if os.path.exists(VELOCITY_CACHE):
        with open(VELOCITY_CACHE, "r", encoding="utf-8") as f:
            return json.load(f)

    # 2. 캐시가 없고 실시간 분석 모듈이 존재하면 실시간 분석을 수행합니다.
    if get_velocity_ranking is not None:
        result = get_velocity_ranking(start_date, end_date)
        if "error" not in result:
            return result

    # 3. 폴백 반환
    if os.path.exists(LOCK_FILE):
        return {"message": "현재 500개의 식품 트렌드 데이터를 수집 및 분석 중입니다. 약 2~3분 후 새로고침 해주세요.", "data": []}
        
    return {"error": "데이터가 없습니다. 서버 백그라운드 수집을 기다려주세요.", "data": []}
# ===============================

# === [Weak Signal 감지 API 연동부] ===
@app.get("/api/weak-signals")
async def get_weak_signals_api(target_date: Optional[str] = None, use_live: bool = True):
    """
    고도화된 AI 피처 엔진을 통해 넥스트 히트 상품(Weak Signal) 랭킹 캐시를 반환합니다.
    """
    from pipeline.scheduler import WEAK_SIGNALS_CACHE, LOCK_FILE
    import json
    
    # 1. 약점 신호 캐시가 존재하면 우선 반환합니다.
    if os.path.exists(WEAK_SIGNALS_CACHE):
        with open(WEAK_SIGNALS_CACHE, "r", encoding="utf-8") as f:
            return json.load(f)
            
    # 2. 캐시가 없을 시 실시간 랭킹 연산을 수행합니다.
    if detect_weak_signals is not None:
        try:
            results = detect_weak_signals(target_date)
            return {"data": results}
        except Exception:
            pass
            
    # 3. 폴백 반환
    if os.path.exists(LOCK_FILE):
        return {"message": "현재 500개의 식품 트렌드 데이터를 수집 및 분석 중입니다. 약 2~3분 후 새로고침 해주세요.", "data": []}
        
    return {"error": "데이터가 없습니다. 서버 백그라운드 수집을 기다려주세요.", "data": []}
# ===============================

# === [Prophet 단일 키워드 예측 API 연동부] ===
class PredictKeywordRequest(BaseModel):
    keyword: str = Field(..., description="조회할 단일 키워드")
    forecastSteps: int = Field(30, description="예측할 기간(일)의 수")

@app.post("/api/predict-keyword")
async def predict_single_keyword(payload: PredictKeywordRequest):
    try:
        from datetime import datetime, timedelta
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=3652)
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        ad_volumes = await fetch_search_ad_volume([payload.keyword])
        group_monthly_volume = ad_volumes.get(payload.keyword, 0.0)

        import asyncio
        
        naver_task = fetch_naver_trend(
            start_date=start_date_str,
            end_date=end_date_str,
            time_unit="date",
            keyword_groups=[{"groupName": payload.keyword, "keywords": [payload.keyword]}]
        )
        weather_task = fetch_weather_data(
            start_date=start_date_str,
            end_date=end_date_str
        )
        
        naver_response, weather_data = await asyncio.gather(naver_task, weather_task)

        results = naver_response.get("results", [])
        if not results:
            return {"error": "데이터를 찾을 수 없습니다."}
            
        data = results[0].get("data", [])
        
        historical = []
        for item in data:
            historical.append({
                "period": item["period"],
                "ratio": item["ratio"],
                "isForecast": False
            })

        forecasted, summary = forecast_trend(
            historical_data=historical,
            time_unit="date",
            forecast_steps=payload.forecastSteps
        )

        # --- 전조 감지: 스케일링 적용 전에 원본 비율값(0~100)으로 수행 ---
        signals = detect_early_signals(historical) if detect_early_signals else []

        # 스케일링 로직
        multiplier = _get_scale_multiplier(historical, group_monthly_volume, len(historical))
        if multiplier != 1.0:
            _apply_scaling(historical, multiplier)
            _apply_scaling(forecasted, multiplier)
            
            summary["lastHistoricalValue"] = round(summary["lastHistoricalValue"] * multiplier, 0)
            summary["lastForecastValue"] = round(summary["lastForecastValue"] * multiplier, 0)
            summary["maxRatio"] = round(summary["maxRatio"] * multiplier, 0)

            # signal 내부의 volume 값도 스케일링
            for sig in signals:
                if "volume" in sig:
                    sig["volume"] = round(sig["volume"] * multiplier, 0)

        combined_data = historical + forecasted

        return {
            "keyword": payload.keyword,
            "data": combined_data,
            "signals": signals,
            "summary": summary,
            "weather": weather_data
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/api/evaluate-keyword")
async def evaluate_single_keyword(payload: PredictKeywordRequest):
    try:
        from datetime import datetime, timedelta
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=3652)
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        ad_volumes = await fetch_search_ad_volume([payload.keyword])
        group_monthly_volume = ad_volumes.get(payload.keyword, 0.0)

        naver_response = await fetch_naver_trend(
            start_date=start_date_str,
            end_date=end_date_str,
            time_unit="date",
            keyword_groups=[{"groupName": payload.keyword, "keywords": [payload.keyword]}]
        )

        results = naver_response.get("results", [])
        if not results:
            return {"error": "데이터를 찾을 수 없습니다."}
            
        data = results[0].get("data", [])
        
        historical = []
        for item in data:
            historical.append({
                "period": item["period"],
                "ratio": item["ratio"]
            })

        evaluated_data, summary = evaluate_trend_accuracy(
            historical_data=historical,
            test_days=15
        )

        # 스케일링 로직
        multiplier = _get_scale_multiplier(historical, group_monthly_volume, len(historical))
        if multiplier != 1.0:
            _apply_scaling(evaluated_data, multiplier)

        return {
            "keyword": payload.keyword,
            "data": evaluated_data,
            "summary": summary
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
# ===============================

@app.get("/api/meta-accounts")
def read_meta_accounts():
    if get_meta_accounts is None:
        raise HTTPException(status_code=500, detail="Meta API 모듈을 찾을 수 없습니다.")
    return get_meta_accounts()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000)
