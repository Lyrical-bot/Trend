import httpx

# 1. 호출할 메타 주소
url = "https://graph.facebook.com/v20.0/me/accounts"

# 2. headers = {} 부분을 아래와 같이 수정합니다 (중요!)
headers = {
    'Authorization': 'Bearer EAATy814RCQcBR3OGYhvZChw8zNbZCJVadH2YJIGpZCM2VDY6IqDuQ5tjVDfJrqL28COZCSQeHXOqJDiJmgXwnPuWTMI7bftOPGNMj3jaPC15TsqKZBlu7SoM04YqkJvhXwEfw6WcGpIqJR7N589hlNiQCHrsV2VstJrMx9i8cFfzo0HzA4Ps9GILTZBQpHB1ZAC1ppzF657I0vjz6479ASGn1kuxreY47EtZAaZCa'
}

# 3. 메타에 요청을 보내서 응답을 받아오는 함수로 포장합니다
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