"""
역할: 추출된 키워드를 Azure OpenAI GPT-4o-mini를 통해 2차 필터링합니다.
목적: 식품/디저트 트렌드와 무관한 단어를 완벽히 걸러냅니다.
"""

import os
import json
from openai import AsyncAzureOpenAI
from dotenv import load_dotenv

load_dotenv()

# Azure OpenAI 클라이언트 초기화
client = AsyncAzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
    api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
)

deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")

SYSTEM_PROMPT = """
당신은 '대한민국 F&B 트렌드 분석 봇'의 핵심 데이터 정제 AI입니다.
목표: 유튜브 수집 단어 중 '차세대 유행할 간식/디저트/식재료/브랜드'를 조기 발굴.

[합격 기준]
1. 음식 이름, 식재료, 디저트 이름 (예: 망고사고, 두바이초콜릿, 요아정, 엽떡)
2. 맛의 특징을 나타내는 명사 (예: 맵단, 단짠, 꾸덕)
3. 식품 브랜드/프랜차이즈 이름
4. 음식과 결합된 복합 표현 (예: 마라탕 먹방, 신상 과자 리뷰)
   ※ 단, 트렌드의 시발점이 될 수 있으므로 "먹방", "리뷰" 단독 단어도 제한적으로 합격 처리 (confidence를 낮게 부여)

[탈락 기준]
1. 사람 이름/유튜버/연예인/아이돌 그룹 
   (예: 에스파, 쯔양, 키비츠, 뉴진스, 침착맨)
2. 음식과 무관한 일상/방송 용어 (예: 브이로그, 댓글, 출근길)
3. 장소/지역명 단독 (예: 강남, 홍대)
   단, 지역 특산물로 굳어진 경우는 허용 (예: 대구 막창, 제주 흑돼지)
4. 감탄사/평가 (예: 최고, 존맛탱, 대박)

[애매한 경우 처리]
단어 자체로 음식/인명 구분이 불명확하면 confidence를 낮게 설정하세요.

반드시 아래 JSON 형식으로만 반환 (마크다운 블록 금지):
[
  {"word": "망고 아이스크림", "valid": true, "confidence": 0.95},
  {"word": "키위", "valid": true, "confidence": 0.6},
  {"word": "에스파", "valid": false, "confidence": 0.98}
]
"""

async def classify_keywords_batch(keywords: list) -> list:
    """
    주어진 키워드 리스트(보통 100개 단위)를 LLM에 전달하여 식품 관련 키워드만 필터링해 반환합니다.
    """
    if not keywords:
        return []

    # API 설정이 누락된 경우 안전장치로 필터링 없이 그대로 반환
    if not os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY") == "여기에_API_키를_입력하세요":
        print("[WARNING] Azure OpenAI API Key is missing. Returning original keywords.")
        return keywords

    try:
        response = await client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"단어 목록: {json.dumps(keywords, ensure_ascii=False)}"}
            ],
            temperature=0.0
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # JSON 파싱 (마크다운 코드블록 제거)
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
            
        result_text = result_text.strip()
        
        parsed_data = json.loads(result_text)
        
        # 새로 바뀐 JSON Object 형식 파싱
        if isinstance(parsed_data, list):
            valid_keywords = []
            for item in parsed_data:
                if isinstance(item, dict):
                    # valid가 true이거나, 없더라도 에러 안 나게 방어
                    if item.get("valid") is True:
                        valid_keywords.append(item.get("word"))
                else:
                    # 혹시 문자열 리스트로 왔을 경우 방어코드
                    valid_keywords.append(item)
            return [k for k in valid_keywords if k]
        else:
            print(f"[Error] LLM returned unexpected format (not list): {parsed_data}")
            return keywords
            
    except Exception as e:
        print(f"[Error] LLM API 호출 에러: {e}")
        # 실패 시 안전장치: 원본 그대로 반환(데이터 유실 방지)
        return keywords
