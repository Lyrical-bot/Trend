"""
역할: 영상 제목 및 설명 텍스트에서 주요 명사(트렌드 키워드)를 추출합니다.
목적: 노이즈가 많은 유튜브 데이터에서 의미 있는 키워드(예: 버터떡, 두바이초콜릿)만 선별합니다.
"""

from kiwipiepy import Kiwi
import re

# Kiwi 형태소 분석기 전역 초기화 (싱글톤)
kiwi = Kiwi()

# 식품 관련 불용어(Stopwords) 사전에 등록
STOPWORDS = {
    "리뷰", "먹방", "추천", "영상", "오늘", "내일", "어제", "이번", "저번",
    "진짜", "너무", "완전", "대박", "미쳤", "정말", "솔직", "후기", "유튜브",
    "구독", "좋아요", "알림", "설정", "채널", "브이로그", "일상",
    "신상", "편의점", "다이소", "올리브영", "최고", "최악", "가성비", "존맛탱",
    "감성", "개봉", "느낌", "분위기", "브이로그", "언박싱", "하울",
    "웨이팅", "맛집", "과자", "우유", "디저트", "신상과자", "조합", "간식", "크림", "출시", "난리", "서울", "식감"
}

def clean_text(text: str) -> str:
    """텍스트에서 특수문자나 이모지를 제거합니다."""
    if not text:
        return ""
    # 간단한 정규식으로 알파벳, 한글, 숫자, 공백만 남김
    text = re.sub(r'[^a-zA-Z0-9가-힣\s]', ' ', text)
    return text

def extract_keywords(text: str) -> list:
    """
    텍스트를 입력받아 NNG(일반명사), NNP(고유명사)만 추출하여 반환합니다.
    불용어(STOPWORDS)와 1글자 단어는 제거합니다.
    """
    text = clean_text(text)
    if not text.strip():
        return []
        
    extracted = []
    # 형태소 분석
    result = kiwi.tokenize(text)
    
    for token in result:
        # 일반명사(NNG) 또는 고유명사(NNP) 인 경우
        if token.tag in ['NNG', 'NNP']:
            word = token.form
            
            # 1글자는 보통 의미가 부족하므로 제외 ('빵' 같은 예외가 있지만 일단 안전하게)
            if len(word) < 2:
                continue
                
            # 불용어 사전에 있으면 제외
            if word in STOPWORDS:
                continue
                
            extracted.append(word)
            
    # 중복 제거 후 반환 (한 영상에서 여러 번 언급된 건 1회로 침)
    return list(set(extracted))
