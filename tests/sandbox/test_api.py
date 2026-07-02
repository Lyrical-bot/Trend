import asyncio
from naver_api import fetch_naver_trend
from weather_api import fetch_weather_data
from forecaster import forecast_trend, evaluate_trend_accuracy

async def test():
    print("기상 변수 결합 Prophet 모델 예측 및 백테스트 통합 테스트를 시작합니다...")
    try:
        start_date = "2024-06-29"
        end_date = "2026-06-29"
        
        # 1. 네이버 및 날씨 API 병렬 호출 (최근 2년치 테스트)
        print("1. 네이버 데이터 및 기상 데이터 수집 중...")
        naver_task = fetch_naver_trend(
            start_date=start_date,
            end_date=end_date,
            time_unit="date",
            keyword_groups=[{"groupName": "초콜릿", "keywords": ["초콜릿"]}]
        )
        weather_task = fetch_weather_data(
            start_date=start_date,
            end_date=end_date
        )
        
        naver_response, weather_data = await asyncio.gather(naver_task, weather_task)
        
        results = naver_response.get("results", [])
        if not results:
            print("네이버 검색어 데이터를 받아오지 못했습니다.")
            return
            
        data = results[0].get("data", [])
        historical = [{"period": item["period"], "ratio": item["ratio"]} for item in data]
        
        print(f"  -> 수집 완료 (네이버 트렌드 데이터 수: {len(historical)}, 날씨 데이터 수: {len(weather_data)})")
        
        # 2. forecast_trend (날씨 결합 미래 예측)
        print("2. 날씨 변수 결합 Prophet 미래 예측(30일) 연산 중...")
        forecasted, summary = forecast_trend(
            historical_data=historical,
            time_unit="date",
            forecast_steps=30,
            weather_data=weather_data
        )
        print("  -> 미래 예측 완료! 요약 정보:")
        print(summary)
        print(f"  -> 미래 예측 데이터 수: {len(forecasted)}")
        
        # 3. evaluate_trend_accuracy (날씨 결합 백테스트)
        print("3. 날씨 변수 결합 백테스트 검증(15일) 연산 중...")
        result_list, evaluate_summary = evaluate_trend_accuracy(
            historical_data=historical,
            test_days=15,
            weather_data=weather_data
        )
        print("  -> 백테스트 검증 완료! 요약 정보:")
        print(evaluate_summary)
        print(f"  -> 검증 데이터 리스트 수: {len(result_list)}")
        
        print("[SUCCESS] 모든 테스트가 에러 없이 성공적으로 완료되었습니다!")
        
    except Exception as e:
        print("[ERROR] 테스트 중 예외가 발생했습니다:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
