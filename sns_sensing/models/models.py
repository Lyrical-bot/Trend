"""
역할: Trend Bot에서 사용하는 데이터베이스 스키마(테이블)를 정의합니다.
목적: 원시 데이터 보존, 키워드 추출 결과 저장, 그리고 핵심 지표 계산을 위한 통계 테이블을 명세합니다.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from sns_sensing.database.db import Base

class Video(Base):
    """
    # videos 테이블
    #
    # 1. 목적 (왜 필요한 테이블인지):
    # YouTube에서 수집한 원본 데이터(Raw Data)를 변경 없이 저장합니다.
    # 키워드 추출 로직이나 형태소 분석기(Kiwi) 규칙이 변경되더라도,
    # 원본 데이터를 재활용하여 API 재호출 없이 DB 내에서 다시 추출하기 위함입니다.
    #
    # 2. 이유 (각 컬럼이 왜 존재하는지):
    # - video_id (PK): YouTube 영상의 고유 식별자. 중복 수집을 방지하기 위함.
    # - title, description: 형태소 분석 및 키워드 추출의 대상이 되는 원본 텍스트.
    # - published_at: 영상이 실제 업로드된 시간. 트렌드 확산 시점을 파악하기 위한 기준.
    # - channel_id, channel_title: 채널 다양성(Channel Diversity) 분석을 위해, 어떤 채널에서 올렸는지 식별.
    # - collected_at: 시스템이 해당 데이터를 수집한 시간. 디버깅 및 수집 주기를 관리.
    #
    # 3. 활용처 (이 테이블을 어떤 기능에서 사용하는지):
    # - Kiwi Keyword Extraction 파이프라인 단계에서 원본 텍스트를 가져올 때 사용합니다.
    # - 전체 데이터 수집 현황(대시보드)을 집계할 때 사용합니다.
    """
    __tablename__ = "videos"

    video_id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    published_at = Column(DateTime, nullable=False)
    channel_id = Column(String, nullable=False)
    channel_title = Column(String, nullable=False)
    subscriber_count = Column(Integer, nullable=True, default=0)
    collected_at = Column(DateTime, default=func.now())


class VideoStat(Base):
    """
    # video_stats 테이블
    #
    # 1. 목적 (왜 필요한 테이블인지):
    # 개별 영상의 시간대별 조회수, 좋아요, 댓글수 성장세(Velocity)를 추적하기 위한 시계열 테이블입니다.
    # 단순 스냅샷이 아닌, '시간 흐름에 따른 증가폭'과 '참여도(Engagement)'를 계산하는 기반이 됩니다.
    """
    __tablename__ = "video_stats"
    __table_args__ = (
        Index('idx_video_hour', 'video_id', 'hour'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String, ForeignKey("videos.video_id"), nullable=False)
    hour = Column(DateTime, nullable=False)
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)


class Keyword(Base):
    """
    # keywords 테이블
    #
    # 1. 목적 (왜 필요한 테이블인지):
    # Kiwi 형태소 분석기를 통해 개별 영상에서 추출된 키워드 목록을 저장합니다.
    #
    # 2. 이유 (각 컬럼이 왜 존재하는지):
    # - id (PK): 고유 식별자.
    # - video_id (FK): 어떤 영상에서 이 키워드가 추출되었는지 출처를 추적하기 위함.
    # - keyword: 추출된 실제 단어/명사 텍스트.
    # - extracted_at: 추출 작업이 수행된 시간. 재처리 여부를 확인할 때 유용함.
    #
    # 3. 활용처 (이 테이블을 어떤 기능에서 사용하는지):
    # - New Keyword Detection(신규 키워드 감지) 기능에서 DB에 처음 등장한 키워드인지 확인할 때 사용.
    # - 시간대별 통계(keyword_stats)를 집계하기 위한 원천 데이터로 사용.
    """
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String, ForeignKey("videos.video_id"), nullable=False)
    keyword = Column(String, nullable=False, index=True)
    extracted_at = Column(DateTime, default=func.now())


class KeywordStat(Base):
    """
    # keyword_stats 테이블
    #
    # 1. 목적 (왜 필요한 테이블인지):
    # 원시 추출 데이터(keywords)를 매번 집계하면 성능이 저하되므로,
    # 시간(hour) 단위로 키워드의 언급량 및 채널 수를 미리 집계하여 저장합니다.
    #
    # 2. 이유 (각 컬럼이 왜 존재하는지):
    # - id (PK): 고유 식별자.
    # - hour: 집계 기준 시간 단위 (예: 2026-06-28 09:00:00). 시계열 분석을 위한 기준점.
    # - keyword: 분석 대상 키워드.
    # - mention_count: 해당 시간대에 이 키워드가 언급된 영상의 총 개수 (Growth, Burst 계산용).
    # - channel_count: 해당 시간대에 이 키워드를 언급한 고유 채널의 수 (Channel Diversity 계산용).
    #
    # 3. 활용처 (이 테이블을 어떤 기능에서 사용하는지):
    # - Growth Calculation (언급 증가율 계산)
    # - Burst Detection (급증 정도 계산)
    # - Keyword Timeline API (대시보드 차트 렌더링)에서 직접 조회하는 대상 테이블.
    """
    __tablename__ = "keyword_stats"
    __table_args__ = (
        Index('idx_keyword_hour', 'keyword', 'hour'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    hour = Column(DateTime, nullable=False)
    keyword = Column(String, nullable=False)
    mention_count = Column(Integer, default=0)
    channel_count = Column(Integer, default=0)

class ApiCache(Base):
    """
    # api_cache 테이블
    #
    # 1. 목적:
    # 네이버 API(트렌드 검색어, 쇼핑 인기검색어) 등 외부 API의 호출 결과를 캐싱합니다.
    # API 일일 호출 한도(Rate Limit)를 방어하고 개발 시 빠른 응답 속도를 확보합니다.
    #
    # 2. 이유:
    # - id (PK): 고유 식별자
    # - api_name: 호출한 API의 종류 (예: 'naver_trend', 'naver_datalab_top')
    # - request_hash: 파라미터를 해싱한 문자열. 동일한 요청인지 구분하는 고유 키.
    # - date_key: 'YYYY-MM-DD' 형식. 하루에 한 번만 갱신하기 위한 기준.
    # - response_data: API 응답 원본 JSON 문자열.
    """
    __tablename__ = "api_cache"
    __table_args__ = (
        Index('idx_api_cache_lookup', 'api_name', 'request_hash', 'date_key'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    api_name = Column(String, nullable=False)
    request_hash = Column(String, nullable=False)
    date_key = Column(String, nullable=False)
    response_data = Column(String, nullable=False)
    created_at = Column(DateTime, default=func.now())

class BrandDictionary(Base):
    __tablename__ = "brand_dictionary"
    id = Column(Integer, primary_key=True, autoincrement=True)
    brand_name = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=func.now())

class CanonicalKeyword(Base):
    __tablename__ = "canonical_keywords"
    id = Column(Integer, primary_key=True, autoincrement=True)
    canonical_name = Column(String, nullable=False, unique=True, index=True)
    brand_name = Column(String, nullable=True)
    category = Column(String, nullable=True)
    action = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())

class RawKeywordMapping(Base):
    __tablename__ = "raw_keyword_mapping"
    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_keyword = Column(String, nullable=False, unique=True, index=True)
    canonical_id = Column(Integer, ForeignKey("canonical_keywords.id"), nullable=False)
    created_at = Column(DateTime, default=func.now())

class CoOccurrence(Base):
    __tablename__ = "co_occurrence"
    __table_args__ = (
        Index('idx_co_occurrence', 'keyword', 'co_keyword', unique=True),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String, nullable=False)
    co_keyword = Column(String, nullable=False)
    count = Column(Integer, default=1)
