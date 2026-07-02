import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from retriever import retrieve_trend_context
from anthropic import AsyncAnthropic

router = APIRouter()

class InterpretRequest(BaseModel):
    keyword: str

class InterpretResponse(BaseModel):
    keyword: str
    context: str
    interpretation: str

@router.post("/interpret", response_model=InterpretResponse)
async def interpret_trend(payload: InterpretRequest):
    keyword = payload.keyword
    
    # 1. RAG 컨텍스트 데이터 검색
    try:
        context_data = await retrieve_trend_context(keyword)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"데이터 수집 중 오류 발생: {str(e)}")
        
    # 2. Anthropic API 키 로드
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        print("[WARNING] ANTHROPIC_API_KEY가 환경 변수에 설정되어 있지 않아 모의 분석을 제공합니다.")
        mock_interpretation = (
            f"🤖 [AI 시뮬레이션 모드]\n"
            f"검색하신 F&B 트렌드 키워드 '{keyword}'는 최근 유튜브 언급 증가율과 언급 채널의 다양성이 동시에 임계값을 넘어서며 강력한 확산 신호를 보이고 있습니다. "
            f"기존 네이버 월간 검색량 대비 소셜 미디어상의 바이럴 비율이 기하급수적으로 높아, 기획 상의 '블루오션 골든타임' 상태에 해당합니다. "
            f"최근 3일간의 온화한 날씨 평균 지표 역시 해당 식품 소비 및 활발한 야외 식음료 유입을 활성화하고 있어, 신제품 출시와 소셜 채널 마케팅 캠페인을 즉시 기획할 것을 제언합니다."
        )
        return InterpretResponse(
            keyword=keyword,
            context=context_data,
            interpretation=mock_interpretation
        )
        
    # 3. Anthropic API 호출
    try:
        client = AsyncAnthropic(api_key=api_key)
        
        system_prompt = (
            "당신은 대한민국 최고 수준의 F&B(식음료) 비즈니스 트렌드 분석가입니다. "
            "주어진 네이버 및 유튜브 트렌드 통계 정보와 날씨 데이터를 기반으로, "
            "기획자가 직관적으로 이해할 수 있는 3~4문장의 명확하고 논리적인 트렌드 원인 분석 및 제품 개발/마케팅 제언을 제공하세요. "
            "인사말이나 사족은 생략하고 즉시 요약 분석 결과만 비즈니스 리포트 스타일로 출력하세요."
        )
        
        user_message = f"다음은 실시간 수집된 트렌드 원천 데이터 컨텍스트입니다. 이를 바탕으로 트렌드를 심층 해석해 주세요:\n\n{context_data}"
        
        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=800,
            temperature=0.3,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
        
        interpretation_text = response.content[0].text.strip()
        
        return InterpretResponse(
            keyword=keyword,
            context=context_data,
            interpretation=interpretation_text
        )
        
    except Exception as e:
        print(f"[RAG Router] Anthropic API call failed: {e}")
        fallback_interpretation = (
            f"⚠️ [API 호출 실패 폴백 응답]\n"
            f"데이터 분석 결과, 최근 '{keyword}'에 대한 유튜브 4대 확산 지표와 채널 다변성 비율이 긍정적인 추세를 보이고 있습니다. "
            f"소셜 멘션 가속도가 붙고 있으므로, 시장을 신속히 선점하기 위해 핵심 타겟 연령층을 고려한 제품 개발 및 타겟 광고 캠페인 런칭이 비즈니스적으로 유효할 것입니다."
        )
        return InterpretResponse(
            keyword=keyword,
            context=context_data,
            interpretation=fallback_interpretation
        )