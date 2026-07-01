# 🚀 Trend Forecast & SNS Sensing Project

네이버 데이터랩 트렌드 예측과 유튜브 SNS 반응 데이터를 종합 분석하여, 미래 시장 예측과 현재의 진짜 핫한 트렌드를 대시보드에 띄워주는 종합 플랫폼입니다.

---

## 📁 전체 프로젝트 청사진 (디렉토리 트리 & 상호작용)

```text
new/                                    # 🚀 최상위 프로젝트 폴더
│
├── 📂 Backend/                         # FastAPI 기반 백엔드 코어 (데이터 예측 및 외부 API 연동)
│   ├── 📂 pipeline/                    # 백그라운드 자동화 파이프라인
│   │   ├── scheduler.py                # [naver_api.py, datasets/ 연동] 3/6시간 주기 자동 수집 지휘자
│   │   ├── data_collector.py           # 각종 지표 및 데이터 원본 수집 유틸리티
│   │   ├── velocity_model.py           # 키워드 급상승(Velocity) 산출 모델
│   │   ├── 📂 feature_engine/          # 트렌드 피처 엔지니어링 모듈
│   │   │   ├── acceleration.py         # 가속도(Acceleration) 점수 산출
│   │   │   ├── burst.py                # 단기 폭발성(Burst) 점수 산출
│   │   │   ├── growth.py               # 성장률(Growth) 점수 산출
│   │   │   ├── persistence.py          # 지속성(Persistence) 점수 산출
│   │   │   ├── stability.py            # 안정성(Stability) 점수 산출
│   │   │   ├── trend_scorer.py         # 6개 피처 기반 최종 트렌드 스코어 종합 산출
│   │   │   └── volume.py               # 검색량 볼륨(Volume) 점수 산출
│   │   ├── 📂 models/                  # 데이터 모델 정의 폴더
│   │   │   └── trend_result.py         # 트렌드 분석 결과 데이터 구조체 정의
│   │   └── 📂 services/                # 실질적인 비즈니스 로직 서비스 폴더
│   │       ├── early_signal_detector.py# 트렌드 초기의 미세 신호(Weak Signal) 감지
│   │       └── trend_detector.py       # 최종 트렌드 유무 판별 로직
│   ├── 📂 datasets/                    # 스케줄러가 수집한 JSON 데이터 캐시 보관소
│   │   ├── cached_youtube_seeds.json   # [runner.py 연동] 유튜브 탐색을 위한 2500개 시드 키워드 목록
│   │   ├── cached_food_signals.json    # 식품 카테고리 Weak Signal 분석 캐시
│   │   ├── cached_food_velocity.json   # 식품 카테고리 급상승(Velocity) 캐시
│   │   └── historical_fb_data.csv      # 페이스북 과거 데이터 보관용 (확장/백업용)
│   ├── 📂 data/                        # 과거 원본 데이터(CSV) 보관소
│   │   ├── 1.20250629~20260628정리.csv # [분석용] 2025~2026년 트렌드 데이터 백업
│   │   ├── 2.20240629~20250628정리.csv # [분석용] 2024~2025년 트렌드 데이터 백업
│   │   ├── 3.20230629~20240628정리.csv # [분석용] 2023~2024년 트렌드 데이터 백업
│   │   ├── 4.20220629~20230628정리.csv # [분석용] 2022~2023년 트렌드 데이터 백업
│   │   └── 5.20210629~20220628정리.csv # [분석용] 2021~2022년 트렌드 데이터 백업
│   ├── main.py                         # [forecaster.py, sns_sensing 연동] 핵심 백엔드 서버 진입점
│   ├── forecaster.py                   # [naver_api.py, weather_api.py 연동] Prophet 기반 네이버 검색량 예측 AI
│   ├── naver_api.py                    # [scheduler.py 연동] 네이버 데이터랩(검색어/쇼핑) API 수집기
│   ├── naver_ad_api.py                 # 네이버 검색광고 API 수집 (상대값을 절대 검색량으로 환산)
│   ├── weather_api.py                  # 기상청 API 연동 (날씨 변수 추가 학습용)
│   ├── meta_api.py                     # 메타(인스타/페이스북) API 연동 모듈 (확장 대기용)
│   ├── get_cid.py                      # 네이버 쇼핑 카테고리 ID 조회를 위한 단발성 스크립트
│   ├── get_naver_popular.py            # 네이버 실시간 인기 검색어 수집 스크립트
│   ├── get_rank.py                     # 임시 랭킹 추출 유틸리티
│   ├── clear_cache.py                  # [DB 연동] DB 내의 낡은 API 응답 캐시 초기화 스크립트
│   ├── check.ipynb                     # 개발자가 데이터와 로직을 뜯어보는 테스트용 노트북
│   └── requirements.txt                # 백엔드 파이썬 라이브러리 목록
│
├── 📂 sns_sensing/                     # 🔥 2주차 핵심! 유튜브 SNS 반응 감지 및 분석 엔진
│   ├── __init__.py                     # 파이썬 패키지 인식용 초기화 파일
│   ├── 📂 api/                         # 프론트엔드 통신 API 폴더
│   │   └── main.py                     # [signal_engine.py 연동] 프론트엔드에 거품 제거된 스코어 제공
│   ├── 📂 data/                        # 분석용 로컬 데이터 폴더
│   │   └── trend_data.db               # (구버전/백업용) 레거시 트렌드 데이터베이스 파일
│   ├── 📂 database/                    # 데이터베이스 보관소
│   │   └── sns_trends.db               # 수집된 유튜브 영상과 키워드가 쌓이는 핵심 SQLite DB
│   ├── 📂 models/                      # 데이터 모델 정의 폴더
│   │   └── models.py                   # DB 테이블(Video, Keyword 등)의 스키마 정의
│   ├── 📂 tests/                       # 유닛 테스트 폴더
│   │   └── test_youtube_growth.py      # 베이지안 스무딩 및 급증도 로직 검증용 테스트 코드
│   └── 📂 pipeline/                    # 유튜브 수집 및 정제 파이프라인
│       ├── runner.py                   # [youtube, keyword_filter 연동] 유튜브 수집 통제 오케스트레이터
│       ├── candidate_selector.py       # 수많은 키워드 중 PMI(연관성)가 높은 가치 있는 후보만 골라내는 로직
│       ├── keyword_detector.py         # 수집된 텍스트 안에서 특정 키워드가 얼마나 언급되었는지 탐지
│       ├── keyword_extractor.py        # 명사 위주로 단순 키워드를 형태소 단위로 분리 및 추출
│       ├── clean_db_retroactive.py     # DB 내의 찌꺼기/불량 데이터를 소급하여 정리하는 스크립트
│       ├── backfill_from_db.py         # 과거 수집 데이터를 신형 로직(GPT)으로 다시 돌려넣는 스크립트
│       ├── 📂 youtube/                 # 유튜브 전용 수집 및 분석 모듈
│       │   ├── 📂 discovery/           # 영상 및 키워드 발굴 모듈
│       │   │   ├── seed_collector.py   # 시드 키워드를 유튜브 API에 검색하여 최신 영상을 끌어옴
│       │   │   └── keyword_discovery.py# 영상 제목/설명에서 새로운 연관 키워드를 발굴
│       │   └── 📂 analytics/           # 수식 계산 모듈
│       │       └── signal_engine.py    # 다양성 산출 및 베이지안 스무딩 기반 급증도 계산 엔진
│       └── 📂 openai_keyword_filter/   # GPT 기반 노이즈 필터링 모듈
│           └── keyword_filter.py       # GPT-4o-mini를 호출해 쓸모없는 단어를 버리고 핵심 명사만 정제
│
├── 📂 Frontend/                        # 💻 사용자 대시보드 UI 화면
│   ├── 📂 css/                         # 스타일시트 폴더
│   │   └── style.css                   # 화면을 모던하게 꾸며주는 글로벌 스타일시트
│   ├── 📂 js/                          # 자바스크립트 로직 폴더
│   │   ├── app.js                      # 메인 로직 (차트 렌더링, 칩 생성 및 비동기 통신)
│   │   └── chart-helper.js             # Plotly 차트 및 그래프 관련 렌더링 헬퍼 함수 모음
│   └── index.html                      # 화면 레이아웃과 DOM 구조를 잡는 뼈대 문서
│
├── 📂 pipeline/                        # (Deprecated) 구버전 파이프라인 폴더
│   ├── 📂 feature_engine/              # (구) 데이터 피처 엔지니어링 모듈
│   ├── 📂 models/                      # (구) 머신러닝 모델 폴더
│   └── 📂 services/                    # (구) 서비스 로직 폴더
│
├── 📂 scripts/                         # 🛠️ 개발 및 관리용 외부 스크립트
│   └── youtube_backfill.py             # 특정 키워드의 과거 유튜브 데이터를 강제로 채워넣는(Backfill) 도구
│
├── 📂 scratch/                         # 실험용 1회성 코드 조각 모음 공간
├── 📂 .github/                         # GitHub Actions 워크플로우 등 GitHub 전용 설정
├── 📂 .agents/                         # AI 에이전트 설정 파일 등 관련 폴더
│
├── run.bat                             # ⚡ 원클릭 서버 구동 스크립트 (포트 정리 및 백/프론트 동시 구동)
├── CHANGELOG.md                        # 시스템 패치 내용(베이지안 스무딩 등) 기록
├── AGENT_INSTRUCTIONS.md               # AI 코딩 어시스턴트용 규칙과 룰북
├── README.md                           # 📌 지금 읽고 있는 프로젝트 청사진 파일
├── .gitignore                          # Git 업로드 제외 목록 (venv, 시크릿 등)
├── .env                                # 환경 변수 및 외부 API 시크릿 키 보관 (깃허브 배포 시 제외됨)
├── all_cids.json                       # [테스트용] 네이버 쇼핑 CID 원본 덤프 파일
├── response.json                       # [테스트용] API 응답 구조 원본 덤프 파일
├── cat_out.txt                         # [로깅용] 스크립트 임시 출력 로그
├── output.txt                          # [로깅용] 파이프라인 임시 출력 로그
└── rank_out.txt                        # [로깅용] 랭킹 결과 임시 출력 로그
```
