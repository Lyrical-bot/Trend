import asyncio
from naver_api import fetch_naver_trend

async def test():
    print("API 10년치 일간 데이터 연결 테스트를 시작합니다...")
    try:
        keyword_groups = [
            {"groupName": "테스트", "keywords": ["테스트"]}
        ]
        response = await fetch_naver_trend(
            start_date="2016-06-29",
            end_date="2026-06-29",
            time_unit="date",
            keyword_groups=keyword_groups
        )
        print("API 호출 성공! 응답 데이터 수:", len(response.get("results", [])[0].get("data", [])))
    except Exception as e:
        print("API 호출 실패! 에러 발생:")
        print(e)

if __name__ == "__main__":
    asyncio.run(test())
