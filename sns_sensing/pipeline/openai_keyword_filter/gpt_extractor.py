"""
gpt_extractor.py 에 그대로 붙여넣어 사용하는 시스템 프롬프트 + 구조화 출력 스키마.

역할 경계 (중요):
- 이 모듈은 "트렌드 여부"를 판단하지 않는다. 오직 (1) F&B 카테고리 여부,
  (2) is_compound(구체성) 여부만 판단한다.
- "진짜 트렌드인가"는 이후 스파이크 필터(3일 급증 + 절대 하한선)가 판단한다.
- 이 경계가 무너지면(=추출기가 다시 뉘앙스로 트렌드를 판단하면) 텍스트 뉘앙스에
  좌우되는 문제가 재발하고, 스파이크 집계용 원본 데이터도 깎여나간다.
"""

from pydantic import BaseModel, Field
from typing import Literal


# ------------------------------------------------------------------
# 1. 구조화 출력 스키마 (OpenAI Structured Outputs 용)
# ------------------------------------------------------------------

class ExtractedKeyword(BaseModel):
    keyword: str = Field(..., description="정규화된 키워드 표면형 (canonical name 우선 사용)")
    is_compound: bool = Field(
        ...,
        description="true=구체적 조합형/고유명사, false=단일 일반 식재료명. "
                    "애매하면 true로 관대하게 판단할 것."
    )


class VideoKeywords(BaseModel):
    video_id: str = Field(..., description="입력으로 받은 배치 안에 실제 존재하는 video_id만 사용")
    keywords: list[ExtractedKeyword] = Field(default_factory=list)


class BatchExtractionResult(BaseModel):
    results: list[VideoKeywords]


# ------------------------------------------------------------------
# 2. 시스템 프롬프트
# ------------------------------------------------------------------

SYSTEM_PROMPT = """\
너는 유튜브 영상 제목/설명에서 "식품·디저트·외식(F&B)" 관련 키워드만 뽑아내는 추출기다.
너의 역할은 "이 영상이 지금 유행 중인가?"를 판단하는 것이 아니다.
그 판단은 너의 몫이 아니라 이후 통계 파이프라인(스파이크 필터)의 몫이다.
너는 오직 아래 두 가지만 판단한다.

============================================================
[판단 1] 카테고리 필터 — F&B 관련 키워드인가?
============================================================
- F&B 관련이면 추출한다. 정보성 영상(보관법, 레시피, 꿀팁 등)이어도 상관없이 추출한다.
  "이게 트렌드처럼 보이는가"는 절대 고려하지 마라. 식재료/음식/조리/제품명이면 무조건 추출.
- 다음은 F&B가 아니므로 추출하지 않는다 (카테고리 노이즈):
  - 아이돌/가수/배우 등 인명, 팀명, 곡 제목 (예: "방탄소년단 버터", "뉴진스 하입보이")
  - 브이로그의 배경일 뿐인 지명, 날씨, 일상 잡담
  - 게임, IT 기기, 뷰티 등 F&B와 무관한 카테고리

주의: "방탄소년단 버터"처럼 F&B 단어(버터)가 문자열에 포함되어 있어도,
문맥이 명백히 엔터테인먼트(곡 제목, 무대 직캠 등)라면 추출하지 않는다.

============================================================
[판단 2] is_compound — 구체성 판별
============================================================
"이 키워드가 심사위원/마케팅 담당자에게 '이건 그냥 흔한 식재료잖아요'라는
반박을 들을 만큼 단일 일반명사인가, 아니면 구체적인 트렌드 대상을 가리키는가"를 판단한다.

- is_compound = false 인 경우 (단일 일반 식재료/메뉴 카테고리명, 수식어 없음):
  버터, 우유, 치킨, 계란, 빵, 커피, 초콜릿, 아이스크림 ...

- is_compound = true 인 경우:
  (a) 수식어(브랜드/지역/제조법/신조어)가 결합되어 특정 트렌드 대상을 가리키는 경우
      예: 기버터, 두바이초콜릿, 발효버터 식단, 크루키(크루아상+쿠키)
  (b) 원래부터 하나의 고유 요리/메뉴명으로 굳어진 복합어 (사전에 없어도 관용적으로 붙여 씀)
      예: 떡볶이, 탕후루, 마라탕, 붕어빵

판단이 애매한 경우 (예: "버터 보관법"처럼 수식어가 트렌드성이 아니라 단순 정보성 행동인 경우):
→ false로 성급히 확정하지 말고 true로 관대하게 처리하라.
   (false 오판은 진짜 트렌드를 영원히 묻어버리지만, true 오판은 이후 스파이크 필터가
    자연스럽게 걸러주므로 리스크가 훨씬 작다.)

============================================================
[판단 참고 예시]
============================================================
- 버터 → 추출 O, is_compound: false
- 기버터 → 추출 O, is_compound: true
- 발효버터 식단 → 추출 O, is_compound: true
- 버터 보관법 → 추출 O, is_compound: true (애매하므로 관대하게 처리)
- 방탄소년단 버터 직캠 → 추출 X (카테고리 노이즈, F&B 아님)
- 떡볶이 → 추출 O, is_compound: true (고유 복합 요리명)
- 치킨 → 추출 O, is_compound: false
- 두바이초콜릿 → 추출 O, is_compound: true
- 탕후루 → 추출 O, is_compound: true

============================================================
[출력 규칙]
============================================================
- 반드시 입력받은 배치 안에 존재하는 video_id만 사용한다. 없는 video_id를 만들어내지 마라.
- 하나의 영상에서 여러 키워드가 나올 수 있다.
- 키워드는 가능한 한 입력으로 함께 제공된 canonical name 목록의 표기를 우선 사용해서
  표면형이 파편화되지 않도록 하라 (예: "두바이 초콜릿"이 아니라 "두바이초콜릿"으로 통일).
- 지정된 JSON 스키마 외의 텍스트(설명, 마크다운 등)는 절대 출력하지 마라.
"""


# ------------------------------------------------------------------
# 3. 자주 나오는 고유 요리명 화이트리스트
# ------------------------------------------------------------------

COMPOUND_WHITELIST = {
    "떡볶이", "탕후루", "마라탕", "붕어빵", "호떡", "타코야키",
    "크루키", "두바이초콜릿", "약과", "인절미토스트", "흑당버블티",
    "마카롱", "티라미수", "크로플", "베이글", "소금빵",
}


def force_compound_flag(keyword: str, is_compound: bool) -> bool:
    """화이트리스트에 있으면 GPT 판단과 무관하게 True로 강제 override."""
    if keyword in COMPOUND_WHITELIST:
        return True
    return is_compound


# ------------------------------------------------------------------
# 4. Canonical Name 샘플링
# ------------------------------------------------------------------

import random
from collections import defaultdict


def get_canonical_names_sample(
    canonical_keywords: list[dict],
    total_limit: int = 50,
) -> list[str]:
    """
    canonical_keywords: [{"canonical_name": str, "category": str, "created_at": datetime}, ...]
    """
    by_category: dict[str, list[str]] = defaultdict(list)
    for item in canonical_keywords:
        # 모델 컬럼명인 'canonical_name'을 사용하도록 수정
        name = item.get("canonical_name") or item.get("name")
        if name:
            by_category[item.get("category", "기타")].append(name)

    categories = list(by_category.keys())
    random.shuffle(categories)

    sampled: list[str] = []
    idx = 0
    while len(sampled) < total_limit and categories:
        progressed = False
        for cat in categories:
            pool = by_category[cat]
            if idx < len(pool):
                sampled.append(pool[idx])
                progressed = True
                if len(sampled) >= total_limit:
                    break
        if not progressed:
            break
        idx += 1

    random.shuffle(sampled)
    return sampled[:total_limit]


# ------------------------------------------------------------------
# 5. 유저 메시지(배치) 조립
# ------------------------------------------------------------------

def build_user_message(videos: list[dict], canonical_names: list[str]) -> str:
    """
    videos: [{"video_id": ..., "title": ..., "description": ...}, ...]
    """
    import re

    lines = []
    lines.append("다음은 기존 DB에 저장된 표준 키워드 표기 예시다 (가능하면 이 표기를 우선 사용):")
    lines.append(", ".join(canonical_names) if canonical_names else "(아직 없음)")
    lines.append("")
    lines.append("아래 영상 목록에서 키워드를 추출하라.\n")

    for v in videos:
        desc = v.get("description", "") or ""
        hashtags = re.findall(r"#\S+", desc)
        desc_head = desc[:200]
        combined_desc = f"{desc_head} {' '.join(hashtags)}".strip()

        lines.append(f"[video_id: {v['video_id']}]")
        lines.append(f"제목: {v['title']}")
        lines.append(f"설명(앞 200자+해시태그): {combined_desc}")
        lines.append("")

    return "\n".join(lines)

def run_gpt_extractor(client, videos: list[dict], canonical_names: list[str]) -> list[dict]:
    """
    OpenAI 클라이언트를 활용하여 실제 API를 호출하는 헬퍼 함수
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_message(videos, canonical_names)}
    ]
    
    import os
    from openai import AzureOpenAI
    
    try:
        client = AzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION")
        )
    except Exception as e:
        print(f"[Warning] AzureOpenAI 환경변수가 누락되어 GPT 추출기가 비활성화됩니다: {e}")
        client = None

    model_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")
    
    response = client.beta.chat.completions.parse(
        model=model_name,
        messages=messages,
        response_format=BatchExtractionResult,
        temperature=0.0
    )
    
    result = response.choices[0].message.parsed
    # Pydantic 객체를 dict로 변환
    return result.model_dump()["results"]
