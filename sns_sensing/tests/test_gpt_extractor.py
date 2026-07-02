import os
import sys
import pytest
from openai import OpenAI
from pydantic import BaseModel

# 상위 디렉토리(Trend)를 파이썬 경로에 추가
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from sns_sensing.pipeline.openai_keyword_filter.gpt_extractor import run_gpt_extractor, force_compound_flag

def test_gpt_extractor_regression():
    """
    GPT 추출기가 사용자 피드백에서 지적된 3대 리스크를 정확히 방어하는지 검증하는 E2E 테스트입니다.
    이 테스트는 실제 OpenAI API를 호출하므로 OPENAI_API_KEY 환경변수가 필요합니다.
    """
    from dotenv import load_dotenv
    dotenv_path = os.path.join(parent_dir, "..", ".env")
    load_dotenv(dotenv_path)
    
    api_key = os.getenv("OPENAI_API_KEY")
    azure_key = os.getenv("AZURE_OPENAI_API_KEY")
    
    if not api_key and not azure_key:
        pytest.skip("API KEY가 설정되지 않아 실제 API 테스트를 건너뜁니다.")
        
    if azure_key:
        from openai import AzureOpenAI
        client = AzureOpenAI(
            api_key=azure_key,
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
    else:
        client = OpenAI(api_key=api_key)
    
    # 3대 함정 케이스 비디오 데이터 준비
    test_videos = [
        {
            "video_id": "v1_noise",
            "title": "[직캠] 방탄소년단 버터 (BTS Butter) 무대 교차편집",
            "description": "버터 컴백 무대 직캠입니다. 많이 사랑해주세요! #방탄소년단 #버터 #직캠"
        },
        {
            "video_id": "v2_pending",
            "title": "여름철 버터 보관법 꿀팁! 냉동실? 냉장실?",
            "description": "더운 여름, 비싼 버터를 녹지 않고 신선하게 보관하는 꿀팁 대방출! #버터보관 #살림꿀팁"
        },
        {
            "video_id": "v3_fragmentation",
            "title": "cu 두바이 초콜릿 먹방 리뷰",
            "description": "드디어 구했습니다. 편의점 신상 두바이초콜릿을 직접 먹어봤습니다."
        }
    ]
    
    # DB 앵커링 역할을 할 Canonical Name 리스트 시뮬레이션
    canonical_names = ["두바이초콜릿", "크루키", "요아정"]
    
    # 1. 추출 실행
    results = run_gpt_extractor(client, test_videos, canonical_names)
    
    # 결과를 video_id 기준으로 딕셔너리화
    result_dict = {v["video_id"]: v["keywords"] for v in results}
    
    # 검증 1: 카테고리 노이즈 (추출 안 됨)
    # 방탄소년단 버터는 엔터테인먼트이므로 식품 키워드(버터)가 추출되지 않아야 함.
    v1_keywords = result_dict.get("v1_noise", [])
    assert len(v1_keywords) == 0, f"엔터 노이즈 영상에서 추출 발생: {v1_keywords}"
    
    # 검증 2: 일반 명사 구체성 필터 작동 확인 (PENDING 유지용)
    # 버터 보관법은 정보성이므로 버터가 추출되어야 하지만, is_compound=False여야 함.
    v2_keywords = result_dict.get("v2_pending", [])
    assert len(v2_keywords) > 0, "정보성 영상에서 추출이 실패함 (너무 엄격한 판단)"
    butter_kw = next((k for k in v2_keywords if k["keyword"] == "버터"), None)
    assert butter_kw is not None, "일반 식재료 '버터'가 추출되지 않음"
    
    final_is_compound = force_compound_flag(butter_kw["keyword"], butter_kw["is_compound"])
    assert final_is_compound is False, "'버터'가 is_compound=True로 오탐지되어 스파이크 승격 위험 발생"
    
    # 검증 3: 표면형 정규화 성공 (파편화 방지)
    # 두바이 초콜릿과 두바이초콜릿이 섞인 텍스트에서 앵커링된 '두바이초콜릿'으로 통일되어 추출되어야 함.
    v3_keywords = result_dict.get("v3_fragmentation", [])
    dubai_kw = next((k for k in v3_keywords if "두바이" in k["keyword"]), None)
    assert dubai_kw is not None, "두바이초콜릿 추출 실패"
    assert dubai_kw["keyword"] == "두바이초콜릿", f"표기 정규화 실패. 기대값: '두바이초콜릿', 실제값: '{dubai_kw['keyword']}'"
    
    final_dubai_compound = force_compound_flag(dubai_kw["keyword"], dubai_kw["is_compound"])
    assert final_dubai_compound is True, "트렌드인 '두바이초콜릿'이 is_compound=False로 판별되어 승격 불가됨"

if __name__ == "__main__":
    test_gpt_extractor_regression()
    print("모든 회귀 테스트를 완벽하게 통과했습니다! (방어 체계 정상 작동)")
