import asyncio
from naver_api import fetch_naver_trend

async def test():
    print("API 연결 테스트를 시작합니다...")
    try:
        # 간단한 테스트 키워드 그룹 설정
        keyword_groups = [
            {"groupName": "테스트", "keywords": ["테스트"]}
        ]
        response = await fetch_naver_trend(
            start_date="2026-01-01",
            end_date="2026-06-01",
            time_unit="month",
            keyword_groups=keyword_groups
        )
        print("API 호출 성공! 응답 데이터 일부:")
        print(str(response)[:300] + "...")
    except Exception as e:
        print("API 호출 실패! 에러 발생:")
        print(e)

if __name__ == "__main__":
    asyncio.run(test())
