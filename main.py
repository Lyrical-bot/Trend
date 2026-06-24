import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from naver_api import fetch_naver_trend
from forecaster import forecast_trend
from naver_ad_api import fetch_search_ad_volume

app = FastAPI(title="네이버 데이터랩 트렌드 예측 API", description="네이버 검색어 트렌드를 수집하고 시계열 예측을 제공하는 서비스")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.post("/api/predict")
async def predict_trend(payload: PredictRequest):
    try:
        # 0. 모든 키워드를 수집하여 검색광고 API(절대 검색량) 비동기 호출
        all_keywords = []
        for g in payload.keywordGroups:
            all_keywords.extend(g.keywords)
        all_keywords = list(set(all_keywords)) # 중복 제거
        
        ad_volumes = await fetch_search_ad_volume(all_keywords)

        # 1. 네이버 데이터랩 API 호출
        groups = [{"groupName": g.groupName, "keywords": g.keywords} for g in payload.keywordGroups]
        naver_response = await fetch_naver_trend(
            start_date=payload.startDate,
            end_date=payload.endDate,
            time_unit=payload.timeUnit,
            keyword_groups=groups,
            device=payload.device,
            gender=payload.gender,
            ages=payload.ages
        )

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

            # --- 스케일링 로직 추가 (비율 0~100 -> 실제 검색량(건)) ---
            if group_monthly_volume > 0 and len(historical) > 0:
                # 과거 데이터 전체 합계를 바탕으로 30일(월간) 기준 비율 총합 추정
                total_historical_ratio = sum(item["ratio"] for item in historical)
                days_queried = len(historical)
                
                # 분석 단위에 따른 일수 환산
                if payload.timeUnit == 'week':
                    days_queried *= 7
                elif payload.timeUnit == 'month':
                    days_queried *= 30
                    
                if days_queried == 0:
                    days_queried = 1
                
                # 30일(한 달) 동안의 예상 비율 합계
                estimated_monthly_ratio_sum = (total_historical_ratio / days_queried) * 30
                
                if estimated_monthly_ratio_sum > 0:
                    # 환산 배수 계산
                    multiplier = group_monthly_volume / estimated_monthly_ratio_sum
                    
                    # 과거 및 예측 데이터 스케일링
                    for item in historical:
                        item["ratio"] = round(item["ratio"] * multiplier, 0) # 건수이므로 정수화
                    for item in forecasted:
                        item["ratio"] = round(item["ratio"] * multiplier, 0)
                        
                    # summary 수치 업데이트
                    summary["lastHistoricalValue"] = round(summary["lastHistoricalValue"] * multiplier, 0)
                    summary["lastForecastValue"] = round(summary["lastForecastValue"] * multiplier, 0)
                    summary["maxRatio"] = round(summary["maxRatio"] * multiplier, 0)

            # 과거 + 예측 데이터 병합
            combined_data = historical + forecasted

            response_data.append({
                "title": title,
                "keywords": keywords,
                "data": combined_data,
                "summary": summary
            })

        return {
            "startDate": naver_response.get("startDate"),
            "endDate": naver_response.get("endDate"),
            "timeUnit": naver_response.get("timeUnit"),
            "results": response_data
        }

    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

# 프론트엔드 정적 파일 서빙을 위한 설정
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

@app.get("/")
async def read_index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "대시보드 index.html 파일을 작성 중입니다. 잠시 후 새로고침해 주세요."}

# static 폴더 마운트 (index.html 이외의 css, js 리소스 제공)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
