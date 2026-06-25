import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from prophet import Prophet

def forecast_trend(
    historical_data: List[Dict[str, Any]],
    time_unit: str,
    forecast_steps: int = 30
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    과거 트렌드 데이터를 입력받아 Facebook Prophet 모델로 미래 트렌드를 예측합니다.
    """
    if not historical_data or len(historical_data) < 5:
        return [], {"error": "예측을 수행하기에 과거 데이터가 충분하지 않습니다. (최소 5개 이상의 데이터 포인트 필요)"}

    # 1. Prophet을 위한 데이터프레임 변환 (ds, y)
    df = pd.DataFrame(historical_data)
    df = df.rename(columns={'period': 'ds', 'ratio': 'y'})
    df['ds'] = pd.to_datetime(df['ds'])
    df['y'] = df['y'].astype(float)
    df = df.sort_values('ds').reset_index(drop=True)

    # 2. Prophet 모델 설정 및 학습
    model = Prophet(
        daily_seasonality=False,
        weekly_seasonality=True if time_unit == 'date' else False,
        yearly_seasonality=True
    )
    model.fit(df)

    # 3. 미래 날짜 생성
    if time_unit == 'date':
        freq = 'D'
    elif time_unit == 'week':
        freq = 'W'
    else:
        freq = 'MS'

    future = model.make_future_dataframe(periods=forecast_steps, freq=freq)
    
    # 4. 예측 수행
    forecast = model.predict(future)

    # 미래 예측 기간만 필터링
    last_hist_date = df['ds'].max()
    future_forecast = forecast[forecast['ds'] > last_hist_date]

    # 5. 결과 리스트 포맷팅 (최소 0 이상으로 제한)
    forecast_list = []
    for _, row in future_forecast.iterrows():
        val = max(0, row['yhat'])
        forecast_list.append({
            "period": row['ds'].strftime('%Y-%m-%d'),
            "ratio": round(float(val), 2),
            "isForecast": True,
            "yhat_lower": round(float(max(0, row['yhat_lower'])), 2),
            "yhat_upper": round(float(max(0, row['yhat_upper'])), 2)
        })

    # 6. 예측 분석 리포트 요약 정보
    model_used = "Facebook Prophet"
    
    all_y = list(df['y']) + [f['ratio'] for f in forecast_list]
    all_ds = list(df['ds']) + [pd.to_datetime(f['period']) for f in forecast_list]
    
    max_idx = np.argmax(all_y)
    max_date = all_ds[max_idx].strftime('%Y-%m-%d')
    max_ratio = round(float(all_y[max_idx]), 2)
    
    last_hist_val = df['y'].iloc[-1]
    last_fore_val = forecast_list[-1]['ratio'] if forecast_list else last_hist_val
    trend_diff = last_fore_val - last_hist_val
    
    # 절대 수치 변화량을 비율 추세로 보정해서 판단
    diff_percent = (trend_diff / max(1, last_hist_val)) * 100
    
    if diff_percent > 15:
        trend_status = "급격한 상승세"
    elif diff_percent > 5:
        trend_status = "완만한 상승세"
    elif diff_percent < -15:
        trend_status = "급격한 하락세"
    elif diff_percent < -5:
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

def evaluate_trend_accuracy(
    historical_data: List[Dict[str, Any]],
    test_days: int = 15
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    과거 트렌드 데이터를 바탕으로 모델 정확도를 백테스트합니다.
    - historical_data: [{'period': '2023-01-01', 'ratio': 23.5}, ...] 형식 (보통 60일치)
    - test_days: 분리할 Test 데이터의 개수 (예: 최근 15일)
    """
    if not historical_data or len(historical_data) <= test_days:
        return [], {"error": "백테스트를 수행하기에 데이터가 충분하지 않습니다."}

    # 1. Pandas DataFrame 변환
    df = pd.DataFrame(historical_data)
    df = df.rename(columns={'period': 'ds', 'ratio': 'y'})
    df['ds'] = pd.to_datetime(df['ds'])
    df['y'] = df['y'].astype(float)
    df = df.sort_values('ds').reset_index(drop=True)

    # 2. Train / Test 분리
    train_df = df.iloc[:-test_days]
    test_df = df.iloc[-test_days:]

    # 3. Train 데이터로 모델 학습
    model = Prophet(
        daily_seasonality=False,
        weekly_seasonality=True,
        yearly_seasonality=True
    )
    model.fit(train_df)

    # 4. 미래(Test) 날짜 예측
    future = model.make_future_dataframe(periods=test_days, freq='D')
    forecast = model.predict(future)

    # 5. 결과 매핑
    result_list = []
    
    # 학습 구간 데이터 추가 (과거 데이터)
    for _, row in train_df.iterrows():
        result_list.append({
            "period": row['ds'].strftime('%Y-%m-%d'),
            "ratio": round(float(row['y']), 2),
            "isForecast": False,
            "type": "train"
        })

    # Test 구간 데이터 (실제 vs 예측) 비교 추가
    test_forecast = forecast[forecast['ds'] > train_df['ds'].max()]
    
    y_true = []
    y_pred = []
    
    for i, (_, t_row) in enumerate(test_df.iterrows()):
        actual_val = t_row['y']
        
        # 예측값 찾기
        f_row = test_forecast.iloc[i]
        predicted_val = max(0, f_row['yhat'])
        
        y_true.append(actual_val)
        y_pred.append(predicted_val)
        
        result_list.append({
            "period": t_row['ds'].strftime('%Y-%m-%d'),
            "ratio": round(float(actual_val), 2),
            "isForecast": False,
            "type": "actual"
        })
        result_list.append({
            "period": f_row['ds'].strftime('%Y-%m-%d'),
            "ratio": round(float(predicted_val), 2),
            "isForecast": True,
            "type": "predicted",
            "yhat_lower": round(float(max(0, f_row['yhat_lower'])), 2),
            "yhat_upper": round(float(max(0, f_row['yhat_upper'])), 2)
        })

    # 6. 오차율 (MAPE) 계산
    y_true_arr = np.array(y_true)
    y_pred_arr = np.array(y_pred)
    
    mask = y_true_arr != 0
    if np.sum(mask) > 0:
        mape = np.mean(np.abs((y_true_arr[mask] - y_pred_arr[mask]) / y_true_arr[mask])) * 100
    else:
        mape = 0.0
        
    accuracy = max(0, 100 - mape)

    summary = {
        "modelUsed": "Facebook Prophet (백테스트 모드)",
        "trainDays": len(train_df),
        "testDays": test_days,
        "mape": round(float(mape), 2),
        "accuracy": round(float(accuracy), 2)
    }

    return result_list, summary
