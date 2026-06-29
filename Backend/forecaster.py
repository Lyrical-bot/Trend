import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from prophet import Prophet

MIN_TRAIN_POINTS = 30

def _smooth_outliers(df: pd.DataFrame, column: str = 'y', factor: float = 2.0) -> pd.DataFrame:
    """IQR 기반으로 극단적 이상치를 상한/하한 경계로 클램핑합니다."""
    df = df.copy()
    Q1 = df[column].quantile(0.25)
    Q3 = df[column].quantile(0.75)
    IQR = Q3 - Q1
    if IQR == 0:
        return df
    lower = max(0, Q1 - factor * IQR)
    upper = Q3 + factor * IQR
    df[column] = df[column].clip(lower=lower, upper=upper)
    return df

def _prepare_dataframe(historical_data: List[Dict[str, Any]], weather_data: List[Dict[str, Any]] = None) -> pd.DataFrame:
    df = pd.DataFrame(historical_data)
    df = df.rename(columns={'period': 'ds', 'ratio': 'y'})
    df['ds'] = pd.to_datetime(df['ds'])
    df['y'] = df['y'].astype(float).clip(lower=0)
    
    # 기상 데이터 병합 및 정제
    if weather_data:
        w_df = pd.DataFrame(weather_data)
        if not w_df.empty:
            w_df = w_df.rename(columns={'period': 'ds', 'avgTa': 'temp', 'sumRn': 'rain'})
            w_df['ds'] = pd.to_datetime(w_df['ds'])
            w_df['temp'] = w_df['temp'].astype(float)
            w_df['rain'] = w_df['rain'].astype(float)
            
            # 날짜 기준으로 병합
            df = pd.merge(df, w_df[['ds', 'temp', 'rain']], on='ds', how='left')
            # 결측치 보간 처리 (선형 보간 후 양방향 채우기, 최악의 경우 기본값)
            df['temp'] = df['temp'].interpolate(method='linear').ffill().bfill().fillna(15.0)
            df['rain'] = df['rain'].interpolate(method='linear').ffill().bfill().fillna(0.0)
            
    return df.sort_values('ds').reset_index(drop=True)

def _freq_for_time_unit(time_unit: str) -> str:
    if time_unit == 'date':
        return 'D'
    if time_unit == 'week':
        return 'W'
    return 'MS'

def _use_yearly_seasonality(df: pd.DataFrame) -> bool:
    data_span_days = (df['ds'].max() - df['ds'].min()).days
    return data_span_days >= 700

def _build_model(time_unit: str, use_yearly: bool, add_regressors: bool = False) -> Prophet:
    model = Prophet(
        daily_seasonality=False,
        weekly_seasonality=True if time_unit == 'date' else False,
        yearly_seasonality=use_yearly,
        changepoint_prior_scale=0.01,
        seasonality_prior_scale=5.0,
        holidays_prior_scale=2.0
    )
    if add_regressors:
        model.add_regressor('temp')
        model.add_regressor('rain')
    try:
        model.add_country_holidays(country_name='KR')
    except Exception:
        pass
    return model

def _fit_model(df: pd.DataFrame, time_unit: str) -> Prophet:
    use_yearly = _use_yearly_seasonality(df)
    # 10년 치 데이터(계절성 있음)일 경우 정상적인 여름 피크가 아웃라이어로 잘려나가는 것을 방지
    if use_yearly:
        train_df = df.copy()
    else:
        train_df = _smooth_outliers(df)
    
    add_regressors = 'temp' in train_df.columns and 'rain' in train_df.columns
    model = _build_model(time_unit, use_yearly, add_regressors)
    model.fit(train_df)
    return model

def _inverse_forecast_value(value: float) -> float:
    return max(0, float(value))

def _format_forecast_row(row: pd.Series) -> Dict[str, Any]:
    return {
        "period": row['ds'].strftime('%Y-%m-%d'),
        "ratio": round(_inverse_forecast_value(row['yhat']), 2),
        "isForecast": True,
        "yhat_lower": round(_inverse_forecast_value(row['yhat_lower']), 2),
        "yhat_upper": round(_inverse_forecast_value(row['yhat_upper']), 2)
    }

def _calculate_metrics(y_true: List[float], y_pred: List[float]) -> Dict[str, float]:
    y_true_arr = np.array(y_true, dtype=float)
    y_pred_arr = np.array(y_pred, dtype=float)
    if len(y_true_arr) == 0:
        return {"mape": 0.0, "smape": 0.0, "mae": 0.0, "directionAccuracy": 0.0}

    mask = y_true_arr != 0
    mape = np.mean(np.abs((y_true_arr[mask] - y_pred_arr[mask]) / y_true_arr[mask])) * 100 if np.sum(mask) > 0 else 0.0

    denom = (np.abs(y_true_arr) + np.abs(y_pred_arr)) / 2
    smape_mask = denom != 0
    smape = np.mean(np.abs(y_true_arr[smape_mask] - y_pred_arr[smape_mask]) / denom[smape_mask]) * 100 if np.sum(smape_mask) > 0 else 0.0
    mae = np.mean(np.abs(y_true_arr - y_pred_arr))

    if len(y_true_arr) >= 2:
        actual_direction = np.sign(np.diff(y_true_arr))
        pred_direction = np.sign(np.diff(y_pred_arr))
        direction_accuracy = np.mean(actual_direction == pred_direction) * 100
    else:
        direction_accuracy = 0.0

    return {
        "mape": round(float(mape), 2),
        "smape": round(float(smape), 2),
        "mae": round(float(mae), 2),
        "directionAccuracy": round(float(direction_accuracy), 2)
    }

def _predict_periods(train_df: pd.DataFrame, periods: int, time_unit: str = 'date', weather_df: pd.DataFrame = None) -> pd.DataFrame:
    model = _fit_model(train_df, time_unit)
    future = model.make_future_dataframe(periods=periods, freq=_freq_for_time_unit(time_unit))
    
    # 추가 설명 변수 매핑 처리
    if 'temp' in train_df.columns and 'rain' in train_df.columns:
        if weather_df is not None:
            future = pd.merge(future, weather_df[['ds', 'temp', 'rain']], on='ds', how='left')
        else:
            future = pd.merge(future, train_df[['ds', 'temp', 'rain']], on='ds', how='left')
            
        # 미래 NaN 날씨 채우기 (작년 동기간 365일 전의 데이터를 복사)
        for idx, row in future[future['temp'].isna() | future['rain'].isna()].iterrows():
            target_date = row['ds']
            last_year_date = target_date - timedelta(days=365)
            
            prev_temp = 15.0
            prev_rain = 0.0
            
            source_df = weather_df if weather_df is not None else train_df
            match = source_df[source_df['ds'] == last_year_date]
            if not match.empty:
                prev_temp = match.iloc[0]['temp']
                prev_rain = match.iloc[0]['rain']
            else:
                closest = source_df.iloc[(source_df['ds'] - last_year_date).abs().argsort()[:1]]
                if not closest.empty:
                    prev_temp = closest.iloc[0]['temp'] if 'temp' in closest.columns else 15.0
                    prev_rain = closest.iloc[0]['rain'] if 'rain' in closest.columns else 0.0
                    
            future.loc[idx, 'temp'] = prev_temp
            future.loc[idx, 'rain'] = prev_rain
            
        future['temp'] = future['temp'].interpolate(method='linear').ffill().bfill().fillna(15.0)
        future['rain'] = future['rain'].interpolate(method='linear').ffill().bfill().fillna(0.0)
        
    forecast = model.predict(future)
    return forecast[forecast['ds'] > train_df['ds'].max()].reset_index(drop=True)

def _rolling_backtest(df: pd.DataFrame, test_days: int, folds: int = 3, weather_df: pd.DataFrame = None) -> Dict[str, Any]:
    max_folds = min(folds, max(0, (len(df) - MIN_TRAIN_POINTS) // test_days))
    fold_results = []

    for fold in range(max_folds, 0, -1):
        test_start = len(df) - (fold * test_days)
        test_end = test_start + test_days
        if test_start < MIN_TRAIN_POINTS:
            continue

        train_df = df.iloc[:test_start].copy()
        test_df = df.iloc[test_start:test_end].copy()
        test_forecast = _predict_periods(train_df, len(test_df), 'date', weather_df)

        y_true = test_df['y'].tolist()
        y_pred = [_inverse_forecast_value(row['yhat']) for _, row in test_forecast.iterrows()]
        metrics = _calculate_metrics(y_true, y_pred)
        metrics["startDate"] = test_df['ds'].iloc[0].strftime('%Y-%m-%d')
        metrics["endDate"] = test_df['ds'].iloc[-1].strftime('%Y-%m-%d')
        fold_results.append(metrics)

    if not fold_results:
        return {"folds": 0, "results": []}

    return {
        "folds": len(fold_results),
        "avgMape": round(float(np.mean([r["mape"] for r in fold_results])), 2),
        "avgSmape": round(float(np.mean([r["smape"] for r in fold_results])), 2),
        "avgMae": round(float(np.mean([r["mae"] for r in fold_results])), 2),
        "avgDirectionAccuracy": round(float(np.mean([r["directionAccuracy"] for r in fold_results])), 2),
        "results": fold_results
    }

def forecast_trend(
    historical_data: List[Dict[str, Any]],
    time_unit: str,
    forecast_steps: int = 30,
    weather_data: List[Dict[str, Any]] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    과거 트렌드 데이터를 입력받아 Facebook Prophet 모델로 미래 트렌드를 예측합니다.
    """
    if not historical_data or len(historical_data) < 5:
        return [], {"error": "예측을 수행하기에 과거 데이터가 충분하지 않습니다. (최소 5개 이상의 데이터 포인트 필요)"}

    # weather_df 준비
    weather_df = None
    if weather_data:
        weather_df = pd.DataFrame(weather_data)
        if not weather_df.empty:
            weather_df = weather_df.rename(columns={'period': 'ds', 'avgTa': 'temp', 'sumRn': 'rain'})
            weather_df['ds'] = pd.to_datetime(weather_df['ds'])
            weather_df['temp'] = weather_df['temp'].astype(float)
            weather_df['rain'] = weather_df['rain'].astype(float)

    df = _prepare_dataframe(historical_data, weather_data)
    model = _fit_model(df, time_unit)
    future = model.make_future_dataframe(periods=forecast_steps, freq=_freq_for_time_unit(time_unit))
    
    # 추가 설명 변수 매핑 처리
    if 'temp' in df.columns and 'rain' in df.columns:
        if weather_df is not None:
            future = pd.merge(future, weather_df[['ds', 'temp', 'rain']], on='ds', how='left')
        else:
            future = pd.merge(future, df[['ds', 'temp', 'rain']], on='ds', how='left')
            
        # 미래 NaN 날씨 채우기 (작년 동기간 365일 전의 데이터를 복사)
        for idx, row in future[future['temp'].isna() | future['rain'].isna()].iterrows():
            target_date = row['ds']
            last_year_date = target_date - timedelta(days=365)
            
            prev_temp = 15.0
            prev_rain = 0.0
            
            source_df = weather_df if weather_df is not None else df
            match = source_df[source_df['ds'] == last_year_date]
            if not match.empty:
                prev_temp = match.iloc[0]['temp']
                prev_rain = match.iloc[0]['rain']
            else:
                closest = source_df.iloc[(source_df['ds'] - last_year_date).abs().argsort()[:1]]
                if not closest.empty:
                    prev_temp = closest.iloc[0]['temp'] if 'temp' in closest.columns else 15.0
                    prev_rain = closest.iloc[0]['rain'] if 'rain' in closest.columns else 0.0
                    
            future.loc[idx, 'temp'] = prev_temp
            future.loc[idx, 'rain'] = prev_rain
            
        future['temp'] = future['temp'].interpolate(method='linear').ffill().bfill().fillna(15.0)
        future['rain'] = future['rain'].interpolate(method='linear').ffill().bfill().fillna(0.0)
        
    forecast = model.predict(future)

    # 미래 예측 기간만 필터링
    last_hist_date = df['ds'].max()
    future_forecast = forecast[forecast['ds'] > last_hist_date]

    # 5. 결과 리스트 포맷팅 (최소 0 이상으로 제한)
    forecast_list = []
    for _, row in future_forecast.iterrows():
        forecast_list.append(_format_forecast_row(row))

    # 6. 예측 분석 리포트 요약 정보
    model_used = "Facebook Prophet + IQR Smoothing"
    if 'temp' in df.columns and 'rain' in df.columns:
        model_used = "Facebook Prophet (날씨 기상 변수 결합 모델)"
    
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
        "lastForecastValue": round(float(last_fore_val), 2),
        "recommendedHorizon": "7~14일 방향성 중심"
    }

    return forecast_list, summary

def evaluate_trend_accuracy(
    historical_data: List[Dict[str, Any]],
    test_days: int = 15,
    weather_data: List[Dict[str, Any]] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    과거 트렌드 데이터를 바탕으로 모델 정확도를 백테스트합니다.
    - historical_data: [{'period': '2023-01-01', 'ratio': 23.5}, ...] 형식
    - test_days: 분리할 Test 데이터의 개수
    """
    if not historical_data or len(historical_data) <= test_days:
        return [], {"error": "백테스트를 수행하기에 데이터가 충분하지 않습니다."}

    # weather_df 준비
    weather_df = None
    if weather_data:
        weather_df = pd.DataFrame(weather_data)
        if not weather_df.empty:
            weather_df = weather_df.rename(columns={'period': 'ds', 'avgTa': 'temp', 'sumRn': 'rain'})
            weather_df['ds'] = pd.to_datetime(weather_df['ds'])
            weather_df['temp'] = weather_df['temp'].astype(float)
            weather_df['rain'] = weather_df['rain'].astype(float)

    df = _prepare_dataframe(historical_data, weather_data)

    # 2. Train / Test 분리
    train_df = df.iloc[:-test_days]
    test_df = df.iloc[-test_days:]

    forecast = _predict_periods(train_df, test_days, 'date', weather_df)

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
        predicted_val = _inverse_forecast_value(f_row['yhat'])
        
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
            "yhat_lower": round(_inverse_forecast_value(f_row['yhat_lower']), 2),
            "yhat_upper": round(_inverse_forecast_value(f_row['yhat_upper']), 2)
        })

    metrics = _calculate_metrics(y_true, y_pred)
    rolling = _rolling_backtest(df, test_days=test_days, weather_df=weather_df)
    mape = metrics["mape"]
    accuracy = max(0, 100 - mape)

    model_used = "Facebook Prophet + IQR Smoothing (백테스트 모드)"
    if 'temp' in df.columns and 'rain' in df.columns:
        model_used = "Facebook Prophet (날씨 기상 변수 결합 백테스트 모델)"

    summary = {
        "modelUsed": model_used,
        "trainDays": len(train_df),
        "testDays": test_days,
        "mape": round(float(mape), 2),
        "smape": metrics["smape"],
        "mae": metrics["mae"],
        "directionAccuracy": metrics["directionAccuracy"],
        "accuracy": round(float(accuracy), 2),
        "rollingBacktest": rolling
    }

    return result_list, summary
