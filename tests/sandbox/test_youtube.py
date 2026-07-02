import os
from dotenv import load_dotenv
from googleapiclient.discovery import build

# .env 파일에서 YOUTUBE_API_KEY 로드
load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")

if not API_KEY:
    print("Error: YOUTUBE_API_KEY가 설정되지 않았습니다.")
else:
    print("유튜브 API 연결 테스트 중...")
    youtube = build("youtube", "v3", developerKey=API_KEY)

    request = youtube.search().list(
        q="버터쿠키",
        part="snippet",
        maxResults=5
    )

    response = request.execute()

    # 결과를 예쁘게 출력
    import json
    print(json.dumps(response, indent=2, ensure_ascii=False))
