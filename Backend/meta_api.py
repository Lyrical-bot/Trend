import os
import httpx
from dotenv import load_dotenv

# 1. key/.env 폴더에 있는 설정 값을 읽어옵니다.
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(dotenv_path=dotenv_path)

# 2. 메타 액세스 토큰 값 불러오기
meta_token = os.getenv("META_ACCESS_TOKEN")

# 3. 호출할 메타 주소
url = "https://graph.facebook.com/v20.0/me/accounts"

# 4. f-string 문법을 이용하여 실제 토큰 주입
headers = {
    'Authorization': f'Bearer {meta_token}'
}

def get_meta_accounts():
    try:
        with httpx.Client() as client:
            response = client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json() # 성공하면 데이터를 돌려줌
            else:
                return {"error": response.status_code, "message": response.text}
    except Exception as e:
        return {"error": "Connection Failed", "message": str(e)}