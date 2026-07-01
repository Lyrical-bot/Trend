import os
import json
from openai import AsyncAzureOpenAI
from dotenv import load_dotenv

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv(os.path.join(root_dir, ".env"))

client = AsyncAzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
    api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
)

deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")

def build_system_prompt(recent_canonicals: list) -> str:
    canonicals_str = ", ".join(recent_canonicals) if recent_canonicals else "없음"
    
    return f"""
당신은 '대한민국 F&B 트렌드 분석 봇'의 데이터 추출 및 정규화 AI입니다.
유망 후보 키워드와 해당 키워드가 등장한 [원본 문맥(context)] 목록이 주어지면, 각 항목에 대해 아래 JSON 배열 형식으로 구조화된 데이터를 반환하세요.

[내부 체크리스트 판단 로직 (매우 중요)]
각 후보마다 아래 체크를 속으로(출력하지 않음) 수행한 후, 모두 통과한 경우에만 `valid: true`로 설정합니다.
1. 이 표현이 실제 음식명/상품명인가? (소비자가 주문하거나 구매할 수 있는가?)
2. 형태소 오류 가능성은 없는가? (예: 파편화된 단어, 의미 불명확)
3. 수식어(극, 강, 존, 개, 대박, 미친 등)나 광고 문구를 제거하고도 객관적인 상품명이 남는가? (단, '카라멜', '불닭', '명란', '아보카도' 등은 단순 수식어가 아니라 핵심 재료이므로 제거하면 안 되며, 이를 포함한 전체가 유효한 상품명입니다.)
4. 단순히 영상 제목의 일부이거나, 감탄사, 평가, 밈이 아닌가?

위 조건 중 하나라도 만족하지 못하거나 '확신할 수 없는 경우'에는 무조건 `valid: false` 처리하세요.

[유효하지 않은(valid: false) 항목의 예시]
- 상품명이 아님: "추천", "리뷰", "존맛탱"
- 문법/형태소 오류: "강치즈", "쥬얼초코", "극강치즈", "비주얼치즈", "미친케이크"
- 광고성/감정적 수식어: "대박쿠키", "존맛치즈", "레전드피자"
※ `valid: false`인 경우, `canonical_name`을 포함한 다른 모든 속성은 `null`이어야 합니다.

[유효한(valid: true) 항목의 예시]
- "브라운치즈", "브라운 치즈 크로플", "두바이초콜릿", "말차크림도넛", "소금빵", "생크림카스텔라"
- "카라멜 치즈 토스트", "불닭 치즈 떡볶이", "아보카도 명란 비빔밥" (핵심 재료가 결합된 구체적 메뉴명)

[표기 통합 (Canonical Name) 규칙 및 엑스/오(O/X) 대조 예시]
1. Canonicalization(표기 통합)은 **오직 같은 대상의 표기 차이(띄어쓰기, 외래어 표기, 오탈자)만 통일**하는 작업입니다.
   - (O) "치즈토스트", "치즈 토스트", "치즈-토스트" -> `canonical_name: "치즈토스트"` (동일 대상 표기 차이)
   - (O) "크루키", "크로키", "croookie" -> `canonical_name: "크루키"` (오탈자 및 외래어 통합)
2. **절대 금지 사항**: 구체적인 수식어나 다른 재료가 결합된 별개의 메뉴를 포괄적인 상위 개념으로 뭉개거나 축소(Truncate)하지 마세요.
   - (X) "카라멜 치즈 토스트" -> `canonical_name: "치즈토스트"` (금지! 카라멜이라는 핵심 재료가 삭제됨)
   - (O) "카라멜 치즈 토스트" -> `canonical_name: "카라멜 치즈 토스트"` (핵심 수식어 보존)
   - (X) "불닭 치즈 떡볶이" -> `canonical_name: "떡볶이"` (금지!)
   - (O) "불닭 치즈 떡볶이" -> `canonical_name: "불닭 치즈 떡볶이"` (보존)

3. 아래 [최근 확정된 대표 키워드 목록]이 제공됩니다. 
   - **주의**: 이 목록의 단어들은 오직 **"표기만 다르고 의미가 완전히 동일한 항목"**일 때만 우선 사용하세요.
   - (예: 목록에 "치즈토스트"가 있을 때, 후보가 "치즈 토스트"면 사용 O. 하지만 후보가 "카라멜 치즈 토스트"면 느슨한 유사성으로 억지로 편입시키지 말고 "카라멜 치즈 토스트"로 독립시키세요.)
   
[최근 확정된 대표 키워드 목록]
{canonicals_str}

반드시 아래 JSON 배열 형식으로만 반환하세요 (마크다운 블록 금지, 다른 설명 추가 금지):
[
  {{
    "raw_keyword": "강치즈",
    "valid": false,
    "brand": null,
    "item": null,
    "category": null,
    "action": null,
    "canonical_name": null
  }},
  {{
    "raw_keyword": "CU 두바이 쿠키",
    "valid": true,
    "brand": "CU",
    "item": "두바이쫀득쿠키",
    "category": "편의점 디저트",
    "action": "리뷰",
    "canonical_name": "두바이초콜릿"
  }}
]
"""

async def extract_keywords_info(candidates: list, recent_canonicals: list = None) -> dict:
    if not candidates:
        return {}
        
    if not recent_canonicals:
        recent_canonicals = []

    if not os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY") == "여기에_API_키를_입력하세요":
        print("[WARNING] Azure OpenAI API Key is missing.")
        return {}

    results = {}
    chunk_size = 50
    
    for i in range(0, len(candidates), chunk_size):
        chunk = candidates[i:i + chunk_size]
        system_prompt = build_system_prompt(recent_canonicals)
        
        try:
            response = await client.chat.completions.create(
                model=deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"분석 대상: {json.dumps(chunk, ensure_ascii=False)}"}
                ],
                temperature=0.0
            )
            
            result_text = response.choices[0].message.content.strip()
            
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
                
            result_text = result_text.strip()
            parsed_data = json.loads(result_text)
            
            if isinstance(parsed_data, list):
                for item in parsed_data:
                    if isinstance(item, dict) and item.get("valid") is True:
                        raw_kw = item.get("raw_keyword")
                        if raw_kw:
                            results[raw_kw] = {
                                "brand": item.get("brand"),
                                "item": item.get("item"),
                                "category": item.get("category"),
                                "action": item.get("action"),
                                "canonical_name": item.get("canonical_name") or raw_kw
                            }
        except Exception as e:
            print(f"[Error] LLM API 호출 에러 (chunk {i}): {e}")
            continue
            
    return results
