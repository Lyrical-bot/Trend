import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

def forecast_trend(
    historical_data: List[Dict[str, Any]],
    time_unit: str,
    forecast_steps: int = 30
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    과거 트렌드 데이터를 입력받아 미래 트렌드를 예측합니다.
    - historical_data: [{'period': '2023-01-01', 'ratio': 23.5}, ...] 형식
    - time_unit: 'date', 'week', 'month' 중 하나
    - forecast_steps: 예측할 구간의 개수 (일/주/월 단위에 따름)
    
    반환값:
    - 예측된 데이터 목록: [{'period': '2023-05-01', 'ratio': 25.4, 'isForecast': True}, ...]
    - 예측 관련 요약 정보 (최고점 예상 시기, 성장세 분석 등)
    """
    if not historical_data or len(historical_data) < 5:
        # 데이터가 너무 적을 경우 예측을 수행할 수 없으므로 과거 데이터 그대로 반환하거나 단순 복사
        return [], {"error": "예측을 수행하기에 과거 데이터가 충분하지 않습니다. (최소 5개 이상의 데이터 포인트 필요)"}

    # 1. Pandas DataFrame으로 변환
    df = pd.DataFrame(historical_data)
    df['period_dt'] = pd.to_datetime(df['period'])
    df['ratio'] = df['ratio'].astype(float)
    df = df.sort_values('period_dt').reset_index(drop=True)

    # 2. 날짜 간격 설정
    if time_unit == 'date':
        freq = 'D'
        date_offset = timedelta(days=1)
    elif time_unit == 'week':
        freq = 'W'
        # 네이버 주간 데이터는 보통 월요일 또는 일요일 기준. 이전 간격 분석하여 오프셋 설정
        if len(df) > 1:
            days_diff = (df['period_dt'].iloc[1] - df['period_dt'].iloc[0]).days
            date_offset = timedelta(days=days_diff)
        else:
            date_offset = timedelta(weeks=1)
    else: # month
        freq = 'M'
        date_offset = timedelta(days=30) # 대략적인 오프셋 (실제 날짜 생성 시 pd.date_range 활용)

    # 마지막 관측 날짜 및 값
    last_date = df['period_dt'].iloc[-1]
    
    # 미래 예측 날짜 생성
    if time_unit == 'month':
        forecast_dates = pd.date_range(start=last_date + pd.DateOffset(months=1), periods=forecast_steps, freq='MS')
    else:
        forecast_dates = [last_date + (i + 1) * date_offset for i in range(forecast_steps)]

    # 예측값 저장할 배열
    forecast_ratios = np.zeros(forecast_steps)
    model_used = "Linear/Polynomial Regression"

    # 3. 예측 모델 적용
    # 데이터가 14개 이상일 경우 시계열 Holt-Winters 지수평활법 시도
    # (주간/일간 데이터 등 계절성 주기가 뚜렷한 경우 적합)
    success = False
    if len(df) >= 14:
        try:
            # 계절성 주기 설정 (일간: 7, 주간: 4 또는 52, 월간: 12)
            seasonal_periods = 7 if time_unit == 'date' else (12 if time_unit == 'month' else 4)
            
            # 데이터 수에 비해 계절성 주기가 적절한지 판단
            if len(df) > seasonal_periods * 2:
                model = ExponentialSmoothing(
                    df['ratio'], 
                    trend='add', 
                    seasonal='add', 
                    seasonal_periods=seasonal_periods,
                    initialization_method="estimated"
                )
            else:
                model = ExponentialSmoothing(
                    df['ratio'], 
                    trend='add', 
                    seasonal=None,
                    initialization_method="estimated"
                )
                
            fit_model = model.fit()
            forecast_ratios = fit_model.forecast(steps=forecast_steps).values
            model_used = "Holt-Winters Exponential Smoothing"
            success = True
        except Exception as e:
            # 에러 발생 시 Regression 모델로 Fallback
            success = False

    if not success:
        # Fallback & Simple Model: Polynomial Regression (다항 회귀)
        # 데이터의 전반적인 추세를 맞추기 위해 2차 다항 회귀 적용
        X = np.arange(len(df)).reshape(-1, 1)
        y = df['ratio'].values
        
        # 데이터가 너무 적으면 1차 선형 회귀, 적절하면 2차 다항 회귀
        degree = 2 if len(df) >= 10 else 1
        poly = PolynomialFeatures(degree=degree)
        X_poly = poly.fit_transform(X)
        
        reg = LinearRegression()
        reg.fit(X_poly, y)
        
        X_forecast = np.arange(len(df), len(df) + forecast_steps).reshape(-1, 1)
        X_forecast_poly = poly.transform(X_forecast)
        
        forecast_ratios = reg.predict(X_forecast_poly)
        model_used = f"Polynomial Regression (Degree {degree})"

    # 4. 결과 보정 (검색 비율은 0~100 사이여야 하므로 제한)
    forecast_ratios = np.clip(forecast_ratios, 0, 100)
    
    # 5. 결과 리스트 포맷팅
    forecast_list = []
    for i, date in enumerate(forecast_dates):
        date_str = date.strftime('%Y-%m-%d')
        forecast_list.append({
            "period": date_str,
            "ratio": round(float(forecast_ratios[i]), 2),
            "isForecast": True
        })

    # 6. 예측 분석 리포트 생성 요약 정보
    # 전체 과거 및 미래 데이터를 합쳐서 최고점 시점 찾기
    all_ratios = list(df['ratio']) + list(forecast_ratios)
    all_dates = list(df['period_dt']) + list(forecast_dates)
    
    max_idx = np.argmax(all_ratios)
    max_date = all_dates[max_idx].strftime('%Y-%m-%d')
    max_ratio = round(float(all_ratios[max_idx]), 2)
    
    # 예측된 추세 판단 (마지막 과거 값 대비 마지막 예측 값 비교)
    last_hist_val = df['ratio'].iloc[-1]
    last_fore_val = forecast_ratios[-1]
    trend_diff = last_fore_val - last_hist_val
    
    if trend_diff > 15:
        trend_status = "급격한 상승세"
    elif trend_diff > 5:
        trend_status = "완만한 상승세"
    elif trend_diff < -15:
        trend_status = "급격한 하락세"
    elif trend_diff < -5:
        trend_status = "완만한 하락세"
    else:
        trend_status = "보합세 (유지)"

    summary = {
        "modelUsed": model_used,
        "trendStatus": trend_status,
        "maxDate": max_date,
        "maxRatio": max_ratio,
        "lastHistoricalValue": round(float(last_hist_val), 2),
        "lastForecastValue": round(float(last_fore_val), 2)
    }

    return forecast_list, summary
