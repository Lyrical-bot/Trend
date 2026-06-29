# 📋 CHANGELOG — 프로젝트 업데이트 이력

> 이 문서는 초창기 `AGENT_INSTRUCTIONS.md` 작성 이후 진행된 모든 주요 변경 사항을 기록합니다.
> 프로젝트의 **현재 상태**를 파악하려면 이 문서를 기준으로 삼으세요.

---

## 🏷️ v3.3 — 네이버 API 데이터 무결성 확보 및 캐싱 고도화 (2026-06-29)

### 주요 개선 사항
1. **네이버 API 데이터 무결성 확보 (중요)**
   - `fetch_datalab_top_keywords`, `predict_single_keyword` 등 네이버 데이터랩 조회 시 기준일을 '오늘'에서 **'어제(마감된 날짜)'**로 전면 수정하여, 일일 데이터 미집계로 인한 지표 왜곡 방지
2. **네이버 API DB 캐싱 적용 (API 호출량 방어)**
   - `trend_data.db`에 `api_cache` 테이블을 신설하여 네이버 데이터랩 트렌드, 검색광고 볼륨, 인기 검색어 결과를 하루 단위로 캐싱 (동일 쿼리 중복 호출 완벽 차단)
3. **백그라운드 스케줄러 최신화 방어 로직 추가**
   - 서버 재시작 시 `cached_food_signals.json` 결과 파일이 단순히 '존재'하는지만 검사하던 로직에서, **생성된 지 6시간 이상 경과**했는지 확인하여 즉시 재수집을 트리거하도록 수정
4. **수동 캐시 삭제 스크립트 추가**
   - `Backend/clear_cache.py` (sqlite3 기반) 유틸리티를 추가하여 필요 시 언제든 즉시 DB API 캐시를 초기화하고 강제 갱신할 수 있는 환경 마련

---

## 🏷️ v3.2 — 트렌드 노이즈 필터링 고도화 (TF-IDF 및 Stopwords) (2026-06-29)

### 주요 개선 사항
1. **TF-IDF 알고리즘 도입 (수학적 통계 필터링)**
   - `/api/sns/discovered-keywords` 엔드포인트에 TF-IDF 가중치 로직 적용
   - 전체 수집 비디오 수 대비 등장 빈도(IDF)를 계산하여, "편의점", "리뷰" 등 흔한 단어에 페널티를 주고 "두바이초콜릿" 등 유니크한 단어의 랭킹을 상승시킴
2. **불용어(Stopwords) 사전 대폭 강화**
   - `keyword_discovery.py`에 "감성", "개봉", "느낌", "분위기", "브이로그", "언박싱", "하울" 등 식품 트렌드와 무관한 노이즈 단어 대거 추가
3. **사용자 경험(UX) 개선 및 네이버 절대수치 교차검증**
   - 기존의 혼동을 주던 `채널 다양성(건전성)` 비율(0.0~1.0) 대신, 직관적인 유니크 채널 개수(`N개 채널`) 노출 방식으로 프론트엔드 및 백엔드 파이프라인 수정
   - 네이버 검색광고 API를 활용하여, 데이터랩(상대비율)이 아닌 **월간 절대 검색량(예: 5000건)** 기준으로 진짜 대중화 여부를 판별하도록 크로스체크 로직 완벽 변경

## 🏷️ v3.1 — 백엔드 파이프라인 안정화 및 지표 왜곡 버그 수정 (2026-06-29)

### 주요 개선 사항
1. **패키지 인프라 오류 복구 (심각 해결)**
   - `sns_sensing` 및 `pipeline` 하위의 모든 디렉터리에 `__init__.py` 누락 복구
   - `keyword_detector.py` 및 `test_signals.py` 내부의 깨진 패키지 임포트 경로 복구
2. **데이터 지표 및 필터 왜곡 해결 (중요 해결)**
   - **채널 다양성 지표 뻥튀기 방지**: 동시간대 동일 채널 여부를 사전에 체크하여 `channel_count` 중복 집계 방지
   - **대시보드 24시간 필터 오류 해결**: 통계 기준 시간을 영상 업로드 시간(`published_at`)에서 수집 시간(`collected_at`)으로 변경
   - **테스트 잔재 제거**: `signal_engine.py` 내 '버터떡' 키워드에 대한 무조건 150% Growth 강제 반환 로직 삭제
   - **Shorts 전용 전략 도입**: 시드 키워드 검색 시 "리뷰" 텍스트 강제 추가 로직을 제거하고, `videoDuration='short'` 파라미터를 추가하여 쇼츠 영상 우선 수집
3. **안정성 확보 및 클린업 (경고 해결)**
   - **예비 API 키 버그 수정**: `naver_ad_api.py`에서 `CUSTOMER_ID2`를 `NAVER_AD_CUSTOMER_ID2`로 정상 참조하도록 수정
   - **API 오류 크래시 방지**: YouTube 데이터 수집 중 API 할당량(Quota) 초과 시 서버가 멈추지 않도록 예외 처리(`try-except`) 적용
   - **테스트 파일 격리**: 루트에 방치된 `test_youtube.py`, `test_cid.py`, `test_api.py` 등을 `tests/sandbox/` 로 일괄 이동
   - **스케줄러 연동 완료**: 3시간마다 유튜브 파이프라인(`run_pipeline`)이 자동 백그라운드 실행되도록 `scheduler.py`에 등록

---

## 🏷️ v3.0 — Trend Bot MVP 아키텍처 개편 및 핵심 지표 도입 (2026-06-28)

### 주요 개선 사항
1. **신규 기능 격리 및 플랫폼별 모듈 구조 도입 (`sns_sensing` 폴더 격리)**
   - 기존 레거시(네이버 검색어 봇) 코드와의 충돌 방지 및 유지보수성 향상을 위해 신규 MVP 관련 모든 기능(`api`, `database`, `models`, `pipeline`, `tests` 등)을 **`sns_sensing/`** 폴더 하위로 완전히 격리했습니다.
   - 또한, 향후 TikTok, Reddit 확장을 대비하여 `sns_sensing/platforms/` 디렉터리를 생성하고, `youtube/` 모듈 아래에 `collector`, `processor`, `analyzer`를 독립시켰습니다.
2. **원시 데이터(Raw Data) 저장 파이프라인 구축**
   - 형태소 분석기 규칙 변경 시 API 재호출 없이 내부 DB만으로 데이터를 재처리할 수 있도록 `videos` (Raw 데이터), `keywords` (추출 결과), `keyword_stats` (통계)의 3단계 DB 구조를 도입했습니다.
3. **엄격한 SQL 모델 주석 규칙 적용**
   - 모든 SQLAlchemy 모델 선언 시 해당 테이블의 목적, 컬럼의 존재 이유, 활용처를 반드시 주석으로 명시하도록 강제했습니다.
4. **Trend Score 배제 및 4대 핵심 지표 도입**
   - 불확실한 가중치 기반의 Trend Score 대신 신규 키워드 여부(New Keyword), 언급 증가율(Growth), 급증 정도(Burst), 채널 다양성(Channel Diversity = unique channel / video count)을 직관적으로 제공하도록 MVP 방향성을 수정했습니다.
5. **Keyword Timeline API 추가**
   - 프론트엔드에서 즉시 사용할 수 있는 타임라인 데이터 반환용 `GET /keyword/{keyword}` 엔드포인트를 추가했습니다.
6. **파이프라인 로깅 강화 및 회귀 테스트 추가**
   - 디버깅을 위해 영상 수집 -> 키워드 추출 -> 신규 키워드 -> Burst 후보 흐름을 터미널에 명시적으로 출력하도록 하고, 핵심 지표 로직 보호를 위한 회귀 테스트(Regression Test) 항목을 신설했습니다.


## 🏷️ v2.5 — 장기 계절성 예측 오류 해결 및 차트 UI 개편 (2026-06-26)

### 주요 개선 사항

1. **계절성(Seasonality) 예측 정확도 개선: 데이터 수집 기간 1년 → 3년 3개월 확장**
   - 기존 1년(365일)치 데이터만 수집하여 `Prophet` 모델이 여름철/겨울철 등 특정 계절 상품(수박, 오디 등)의 사이클을 단순 하락 추세(Trend)로 오해하던 문제 해결
   - `main.py`와 `pipeline/data_collector.py`의 수집 기간을 3년 3개월(1185일)로 확장하여 `Prophet`이 `yearly_seasonality`를 자동으로 학습하도록 조치
   - _(참고: 초기에 10년 치로 확장했으나 API 응답 속도 및 모델 학습 속도 저하 문제로 2년으로 내렸다가, 완전한 3번의 여름 사이클(23년 4월 말 시작)을 확보하기 위해 최종 3년 3개월로 타협)_
2. **프론트엔드 차트 반응형 X축(시계열) 도입**
   - 10년 치 방대한 데이터 렌더링 시 X축 라벨(날짜)이 겹쳐서 까맣게 뭉개지는 현상 해결
   - `static/js/chart-helper.js`의 ApexCharts 설정에서 `xaxis.type`을 `datetime`으로 변경하여, 축소/확대 줌(Zoom) 비율에 따라 '연/월' 및 '일' 표기가 동적으로 전환되도록 개선
   - 커스텀 툴팁 내장 타임스탬프 값을 `YYYY-MM-DD` 형식으로 자동 포맷팅하도록 방어 로직 추가
3. **네이버 API 통신 Rate Limit(네트워크 오류) 에러 해결**
   - 500개 키워드 배치(Batch) 요청 시 연속적인 호출로 인해 연결이 끊어지는 버그 수정
   - `pipeline/services/trend_detector.py`에 반복문마다 `asyncio.sleep(0.5)` 대기 시간을 추가하여 통신 안정성 완벽 확보
4. **🔴 치명적 버그 수정: 계절성 데이터 예측 급락(Drop) 현상 해결**
   - 10년 치 계절성 데이터 분석 시, 단기 노이즈 제거용 `_smooth_outliers()` 로직이 한여름 트래픽 폭발을 '아웃라이어(이상치)'로 오판하여 강제로 깎아버리던(Clipping) 문제 발견
   - `forecaster.py`에서 `use_yearly_seasonality`가 활성화될 경우 IQR 기반 스무딩 로직을 완전히 우회(Bypass)하도록 수정하여 계절 피크가 AI 학습에 온전히 반영되도록 교정
5. **🔴 치명적 버그 수정: 스케일링 배수(Multiplier) 뻥튀기 현상 해결**
   - 네이버 광고 API(실제 검색 건수)는 '최근 30일' 기준인데, 변환 배수를 계산할 때 '10년 치 전체 평균 비율'을 사용하면서 y축 수치가 천문학적으로 뻥튀기되던 왜곡 현상 발견
   - `main.py`의 `_get_scale_multiplier()` 로직이 전체 비율이 아닌 오직 '최근 30일 치' 비율 합산값만을 추출하여 배수를 계산하도록 수정하여 정확한 실제 건수를 반환하도록 보정

## 🏷️ v2.4 — 전조 감지 정밀도 개선 및 코드 품질 강화 (2026-06-25)

### 주요 개선 사항

1. **🔴 치명적 버그 수정: Signal 감지 순서 교정**
   - `main.py`에서 `detect_early_signals()`가 스케일링(비율→실제 건수 변환) **이후**에 호출되어, Config의 기준값(`min_current_volume=100`)이 사실상 무의미해지던 버그 수정
   - `/api/predict`와 `/api/predict-keyword` 두 엔드포인트 모두에서 **스케일링 전에 원본 비율값(0~100)으로 Signal을 먼저 감지**한 뒤, Signal 내부의 volume 값만 나중에 스케일링하도록 순서 교정
2. **피크(Peak) 뒷북 경보 차단: `max_burst_ratio` 상한선 도입**
   - `EarlySignalConfig`에 `max_burst_ratio = 5.0` 파라미터를 추가
   - 검색량이 평소 대비 5배를 초과한 시점은 "이미 터진 피크"로 간주하여 전조 마커를 찍지 않도록 차단
   - 오직 **1.5배~5배 사이의 예열 구간(Simmering Phase)**에서만 마커가 표시됨
3. **`persistence.py` 개선: 노이즈 내성 강화**
   - 기존: 끝에서부터 "연속 상승일" 카운트 → 하루만 빠져도 **0점**이 되는 취약한 구조
   - 개선: "최근 7일 중 전일 대비 상승한 날의 **비율**"로 측정 → 하루 빠져도 자연스럽게 감점만 됨
4. **`stability.py` 개선: 유행 초입 역설 해소**
   - 기존: 변동계수(CV)로 측정 → 유행 시작 시 검색량이 오르면 변동이 커져 오히려 **감점**되는 모순
   - 개선: "상승 방향의 일관성"을 측정 → 꾸준히 올라가면 **가점**, 오르락내리락하면 감점
5. **Feature Engine 통합: `growth.py` 정식 연동**
   - `early_signal_detector.py`에서 수동으로 `growth_7d`를 계산하던 중복 코드 제거
   - `growth.py` 모듈을 정식 import하여 `trend_detector.py`와 동일한 계산 로직을 공유
6. **차트 커스텀 툴팁 안정화**
   - ApexCharts 커스텀 HTML 툴팁에서 CSS 변수(`var(--card-border)` 등)가 Shadow DOM에서 상속되지 않을 수 있는 문제를 하드코딩 색상으로 교체하여 해결
7. **Config 기준값 보정**
   - `min_current_volume`: `100.0` → `5.0` (비율값 0~100 스케일에 맞게 하향)
   - `min_peak_volume`: `1000.0` → `50.0` (비율값 스케일에 맞게 하향)

---

## 🏷️ v2.3 — 유행 전조 감지 레이어 추가 (2026-06-25)

### 주요 개선 사항

1. **조기 경보 감지 모듈 분리 추가**
   - `pipeline/services/early_signal_detector.py`를 새로 추가하여 Prophet 예측과 독립적인 유행 전조 감지 레이어를 구성
   - `EarlySignalConfig`에 threshold, cooldown, breakout horizon 등을 모아 언제든 수정/삭제하기 쉽게 분리
2. **날짜별 Feature 생성 기반 마련**
   - 각 키워드의 매 날짜를 기준으로 `burstRatio`, `growth7d`, `accelerationScore`, `persistenceScore`, `stabilityScore`, `volumeScore`, `trendScore`를 계산
   - `build_breakout_training_rows()`를 추가하여 향후 ML 분류 모델 학습용 feature/label 데이터셋을 만들 수 있도록 준비
3. **조기 경보 Signal API 연결**
   - `/api/predict`와 `/api/predict-keyword` 응답에 `signals` 필드를 추가
   - 기존 `data`와 `summary` 구조는 유지하여 차트/예측 로직과 독립적으로 제거 가능
4. **차트 전조 마커 표시**
   - `chart-helper.js`에 ApexCharts point annotation을 추가하여 차트 위에 `유행 전조 감지` 마커를 표시
   - 단일 키워드 리포트에도 최초 감지일, 점수, 당시 검색량을 함께 표시
5. **검증**
   - 인공 상승 곡선에서 폭발 전 구간에 조기 경보가 생성되는지 확인
   - `py_compile`, `node --check`로 Python/JS 문법 검증 완료

---

## 🏷️ v2.2 — 유행 아이템 예측 안정화 및 검증 강화 (2026-06-25)

### 주요 개선 사항

1. **예측 전처리 안정화**
   - `forecaster.py`에서 학습 데이터에 IQR 기반 이상치 완화를 명확히 적용하도록 정리
   - 검색량/트렌드 비율 급등락의 영향이 과도하게 커지지 않도록 안전한 IQR Smoothing 중심으로 안정화
   - 실측 스케일을 유지하여 로그-지수 역변환(`log1p`/`expm1`)으로 예측선이 과도하게 증폭되는 문제를 방지
2. **Prophet 모델 구성 보강**
   - 한국 공휴일 효과를 인식할 수 있도록 `add_country_holidays(country_name="KR")` 적용
   - 기존 `changepoint_prior_scale=0.01`, 조건부 연간 계절성 정책은 유지하여 급격한 과적합을 계속 억제
3. **백테스트 지표 확장**
   - 기존 MAPE/정확도 외에 `SMAPE`, `MAE`, 방향성 정확도(`directionAccuracy`)를 추가
     - _`SMAPE` (대칭 평균 절대 백분율 오차)_: 검색량이 적을 때 오차율이 과도하게 뻥튀기되는 기존 MAPE의 단점을 보완한 지표입니다.
     - _`MAE` (평균 절대 오차)_: 퍼센트(%)가 아닌 "실제 검색량 수치(건수)"가 평균적으로 얼마나 차이 났는지 보여주는 직관적인 지표입니다.
     - _방향성 정확도 (`directionAccuracy`)_: 검색량이 내일 오를지 내릴지, 그 '추세의 방향'을 맞춘 확률(%)을 의미합니다.
   - 낮은 검색량 키워드에서 MAPE만 과도하게 흔들리는 문제를 보완
4. **Rolling Backtest 추가**
   - 최근 15일 단일 holdout 평가에 더해 최대 3개 구간 rolling backtest 요약을 제공
   - 한 구간의 일시적 이벤트로 모델 평가가 크게 왜곡되는 문제를 줄임
5. **예측 운영 기준 명시**
   - summary에 `recommendedHorizon: "7~14일 방향성 중심"`을 추가하여 30일 절대값보다 단기 방향성 판단을 우선하도록 안내
6. **의존성 문서화**
   - `requirements.txt`에 `prophet`, `cmdstanpy`를 추가하여 새 환경 설치 시 누락되지 않도록 보강
7. **가속도 랭킹 기간 조회 버그 수정**
   - `/api/velocity-ranking`이 날짜 파라미터를 받아도 최신 캐시만 반환하던 문제를 수정
   - 날짜 범위가 지정된 요청은 캐시를 우회하고 `historical_fb_data.csv` 기준으로 기간별 가속도 랭킹을 재계산
   - 프론트엔드 조회 요청에 `use_live=false`를 명시하여 기간 조회 의도를 분명히 함

---

## 🏷️ v2.1 — 예측 신뢰도 및 코드 구조 개선 (2026-06-25)

### 주요 개선 사항

1. **이상치 스무딩 (Outlier Smoothing)**
   - `forecaster.py`에 IQR 기반 클램핑 함수를 추가하여 TV 방송, 이슈 등으로 하루 반짝 폭등한 데이터가 예측선을 비정상적으로 왜곡하는 현상 방지
2. **Prophet 하이퍼파라미터 튜닝**
   - `changepoint_prior_scale`을 `0.05` → `0.01`로 둔화시켜 자잘한 등락에 과민 반응하지 않도록 안정화
   - `seasonality_prior_scale`을 `10.0` → `5.0`으로 조정
3. **연간 계절성 조건부 활성화**
   - 1년 미만(700일 이하) 데이터에서 `yearly_seasonality=True` 사용 시 발생하는 과적합을 막기 위해, 데이터 기간에 따라 자동으로 활성화되도록 로직 개선
4. **신뢰구간 차트 시각화**
   - `chart-helper.js`를 수정하여 ApexCharts의 `rangeArea` 시리즈를 통해 API가 내려주는 `yhat_lower`, `yhat_upper` 값을 투명한 범위로 시각화
5. **코드 중복 제거 (리팩터링)**
   - `main.py` 내 3곳에 흩어져 있던 스케일링 로직을 `_get_scale_multiplier` 유틸 함수로 추출하여 통합 관리

---

## 🏷️ v2.0 — Prophet 시계열 예측 엔진 전환 (2026-06-25)

### 핵심 변경: 예측 모델 교체

| 항목             | Before (v1.0)                                   | After (v2.0)                                            |
| ---------------- | ----------------------------------------------- | ------------------------------------------------------- |
| 예측 모델        | `statsmodels` Holt-Winters + 다항 회귀 Fallback | **Facebook Prophet** (`prophet` + `cmdstanpy`)          |
| 데이터 수집 범위 | 수동 입력 기간 (프론트엔드에서 지정)            | **과거 1년(365일)** 자동 수집                           |
| 계절성 학습      | 없음                                            | `weekly_seasonality=True`, `yearly_seasonality=True`    |
| 백테스팅 기능    | 없음                                            | Train/Test Split(350일/15일) 기반 MAPE 정확도 검증 추가 |

### 새로 추가된 API 엔드포인트

| 엔드포인트              | 메서드 | 설명                                                                |
| ----------------------- | ------ | ------------------------------------------------------------------- |
| `/api/predict-keyword`  | POST   | 단일 키워드에 대해 과거 1년 데이터 수집 → Prophet 미래 30일 예측    |
| `/api/evaluate-keyword` | POST   | 단일 키워드에 대해 Train/Test 분할 백테스트 수행 (MAPE 오차율 산출) |
| `/api/weak-signals`     | GET    | AI Feature Engine 기반 넥스트 히트 상품 130개 랭킹 (캐시)           |
| `/api/velocity-ranking` | GET    | 가속도(Velocity) 폭발 Top 10 선행 지표 감지기 (캐시)                |

### 새로 추가된 파일

```
📦 new/
├── forecaster.py              ← [수정됨] Prophet 기반으로 전면 재작성
├── naver_ad_api.py            ← [기존] 네이버 검색광고 API (절대 검색량 환산용)
├── CHANGELOG.md               ← [신규] 이 파일
├── pipeline/
│   ├── scheduler.py           ← [기존] 6시간 주기 백그라운드 데이터 수집기
│   ├── velocity_model.py      ← [기존] 가속도(Velocity) 선행 지표 모델
│   ├── data_collector.py      ← [기존] CSV 데이터셋 수집기
│   ├── feature_engine/        ← [기존] Weak Signal AI 피처 엔진
│   │   ├── burst.py           ← 폭발력 (최근 3일 vs 직전 30일)
│   │   ├── persistence.py     ← 지속성 (연속 상승일 수)
│   │   ├── acceleration.py    ← 가속도 (증가폭의 증가)
│   │   ├── stability.py       ← 안정성 (노이즈 적은 정도)
│   │   ├── volume.py          ← 절대 규모 (마이너 키워드 필터)
│   │   ├── growth.py          ← 성장률 (주간 대비 변화율)
│   │   └── trend_scorer.py    ← 종합 점수 산출 및 등급 분류
│   ├── services/
│   │   └── trend_detector.py  ← Weak Signal 감지 오케스트레이터
│   └── models/
│       └── trend_result.py    ← 결과 데이터 타입 정의
├── static/
│   ├── index.html             ← [수정됨] Dual Chart UI (예측 + 백테스트 동시 표시)
│   ├── css/style.css          ← [수정됨] 다크 모드, 글래스모피즘 디자인
│   └── js/
│       ├── app.js             ← [수정됨] Promise.all 병렬 API 호출, 페이지네이션
│       └── chart-helper.js    ← [수정됨] 백테스트 3-Line Chart (학습/실제/예측)
└── datasets/
    ├── historical_fb_data.csv       ← 스케줄러가 수집한 원본 데이터
    ├── cached_food_signals.json     ← Weak Signal 캐시
    └── cached_food_velocity.json    ← Velocity Ranking 캐시
```

### 프론트엔드 UI 변경사항

- **Dual Chart 레이아웃**: 키워드 클릭 시 상단(미래 예측)과 하단(백테스트 검증) 차트가 동시에 렌더링
- **페이지네이션**: Weak Signal 표가 20개 단위 페이지로 분리됨 (하단 1, 2, 3... 버튼)
- **리포트 통합**: 예측 트렌드 요약 + MAPE 정확도 + 모델 오차율이 한 곳에 표시

### 기술 스택 변경 (현재 기준)

| 역할        | 패키지                        |
| ----------- | ----------------------------- |
| 백엔드      | Python 3.11, FastAPI, Uvicorn |
| API 통신    | `httpx` (비동기)              |
| 예측 모델   | **`prophet`**, `cmdstanpy`    |
| 데이터 분석 | `pandas`, `numpy`             |
| 스케줄링    | `apscheduler`                 |
| 환경 변수   | `python-dotenv`               |

---

## ⚠️ 현재 알려진 한계 및 개선 예정 사항

1. **갑작스러운 트렌드 전환(방송/뉴스 이벤트)은 예측 불가** — 시계열 모델의 태생적 한계
2. **한국 공휴일 캘린더 미연동** — 명절/연휴 패턴을 모델이 인식하지 못함

---

## 📌 이전 버전 참고

초창기(v1.0) 설계 문서는 [`AGENT_INSTRUCTIONS.md`](./AGENT_INSTRUCTIONS.md)를 참고하세요.

## 2026-06-25

1. Backend 파일 내부 check.ipynb 파일에 메타 api 직접 연결
2. api 에서 가져온 데이터 날짜, 시간 별로 데이터 저장을 위해서 캐시 설정 및 api 호출 횟수 줄이는 우회 경로 코드 작성

예상 구조도
Backend/
│
├── key/
│ └── .env
│
├── cache/
│ ├── hashtag_cache.json # keyword → hashtag_id
│ └── media_cache/ # 최근 수집 시간
│ ├── 황치즈.json
│ ├── 말차.json
│ └── ...
│
├── data/
│ ├── 2026-06-26.json
│ ├── 2026-06-27.json
│ └── ...
│
└── instagram_collector.py 3. 백엔드 및 프론트엔드 분리 구현 계획
현재 프로젝트(Trend)는 FastAPI 백엔드 코드와 정적 HTML/CSS/JS 프론트엔드 파일이 루트 폴더와 static 폴더에 혼재되어 있습니다. 또한 백엔드 모듈 일부가 루트에 있고, 일부가 Backend/ 폴더에 나누어져 있어서 구조가 직관적이지 못합니다. 이를 백엔드(Backend)와 프론트엔드(Frontend)로 명확히 분리하여 독립적인 구동 및 관리가 가능하도록 개선하고자 합니다.

제안하는 디렉토리 구조

Trend/
├── Backend/ # 백엔드 관련 파일 및 폴더 일체
│ ├── pipeline/ # 기존 pipeline 폴더 이동 (스케줄러, 데이터 수집)
│ ├── datasets/ # 기존 datasets 폴더 이동 (데이터 캐시, CSV)
│ ├── key/ # 기존 key 폴더 (.env 환경 변수 파일 포함)
│ ├── main.py # 최종 백엔드 엔트리포인트 (기존 main.py와 backend.py 병합)
│ ├── forecaster.py # 분석 및 예측 로직
│ ├── naver_api.py # 네이버 트렌드 API 연동
│ ├── naver_ad_api.py # 네이버 검색 광고 API 연동
│ ├── meta_api.py # 메타 광고 API 연동
│ ├── get_cid.py # 유틸리티 스크립트
│ ├── get_naver_popular.py # 유틸리티 스크립트
│ ├── get_rank.py # 유틸리티 스크립트
│ ├── test_api.py # 테스트 스크립트
│ ├── test_cid.py # 테스트 스크립트
│ ├── requirements.txt # 백엔드 의존성 패키지
│ └── (기타 캐시 파일 등)
│
└── Frontend/ # 프론트엔드 관련 파일 및 폴더 일체
├── index.html # 대시보드 화면
├── css/ # 스타일시트 폴더
└── js/ # 자바스크립트 폴더 (API 호출 주소 수정)
├── app.js
└── chart-helper.js
주요 작업 항목

1. 백엔드(Backend) 디렉토리 구성
   파일 이동: 루트에 흩어져 있는 파이썬 파일(\*.py)과 백엔드 디렉토리(pipeline/, datasets/)를 Backend/ 폴더 내부로 이동시킵니다.
   백엔드 소스코드 병합 및 수정:
   기존 main.py와 Backend/backend.py는 둘 다 FastAPI 앱을 띄우는 파일입니다. 두 파일의 엔드포인트를 하나로 통합하여 Backend/main.py로 단일화합니다. (특히 backend.py에 추가되었던 /api/meta-accounts 엔드포인트와 main.py에 있던 Prophet 예측/백테스트 엔드포인트를 병합합니다.)
   백엔드에서 더 이상 프론트엔드 정적 파일(static/)을 마운트하여 서빙하지 않도록 정적 파일 서빙 코드(StaticFiles, FileResponse 등)를 제거합니다.
   기존 파이썬 파일들이 상위 폴더를 참조하기 위해 사용하던 sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(**file**)))) 같은 경로 조작 로직을 제거하거나 로컬 패스에 맞춰 단순화합니다.
   정리 및 삭제: 중복되는 Backend/backend.py는 병합 완료 후 삭제합니다.
2. 프론트엔드(Frontend) 디렉토리 구성
   폴더명 변경: 기존 static/ 폴더를 Frontend/로 이름을 변경합니다.
   API 호출 경로 수정:
   Frontend/js/app.js에서 기존에는 동일 서버 내에서 제공됨을 전제로 상대 경로(/api/predict, /api/velocity-ranking, /api/weak-signals 등)를 통해 API를 호출하고 있었습니다.
   이를 백엔드 서버의 절대 주소(예: http://localhost:8000)를 바라보도록 수정합니다.
   파일 상단에 const API_BASE_URL = 'http://localhost:8000';을 선언하고, 모든 fetch 함수가 ${API_BASE_URL}/api/...를 호출하게 수정합니다.
   직접 file:// 프로토콜로 index.html을 열어 테스트할 수 있도록 app.js 내부의 file:// 차단 방어 코드를 비활성화하거나 수정합니다.
3. 연동 및 CORS 설정 확인
   백엔드와 프론트엔드의 포트 또는 도메인이 분리되므로 브라우저에서 CORS 문제가 발생할 수 있습니다.
   FastAPI 백엔드의 CORSMiddleware가 allow_origins=["*"]로 열려 있는 것을 확인했으므로, 프론트엔드 단독 구동 시에도 문제없이 백엔드 API를 호출할 수 있습니다.
   검증 계획 (Verification Plan)
   수동 검증
   백엔드 서버 실행: Backend 폴더로 이동하여 백엔드 서버를 구동합니다.
   bash

cd Backend
python main.py
서버가 http://127.0.0.1:8000에서 정상적으로 작동하는지 확인합니다.
프론트엔드 실행 및 API 연동 테스트: Frontend/index.html을 브라우저로 직접 열거나 로컬 웹 서버(예: Live Server, Python SimpleHTTPServer)로 실행합니다.
메인 대시보드 화면이 깨짐 없이 잘 나오는지 확인합니다.
키워드 분석을 실행하여 백엔드 API(http://localhost:8000/api/predict)와 통신하고 차트 및 예측 데이터가 잘 그려지는지 확인합니다.
가속도 랭킹 및 AI Weak Signal 리스트가 제대로 수집/렌더링되는지 확인합니다.

실행 방법
🚀 실행 방법 (상세 가이드)
(PowerShell 사용 시 필수) 스크립트 실행 권한 허용
Windows PowerShell에서는 기본적으로 가상환경 스크립트 실행이 차단되어 있을 수 있습니다. 터미널에 아래 명령어를 복사하여 붙여넣고 엔터를 칩니다.

powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
(이 명령은 현재 열려 있는 터미널 창에 한해 가상환경 활성화 권한을 임시로 부여합니다.)

1. 가상환경 활성화
   내가 사용하는 터미널 종류에 맞게 아래 명령어를 입력합니다. (성공하면 경로 앞에 (venv)라는 표시가 붙습니다.)

PowerShell을 사용 중인 경우:
powershell
.\venv\Scripts\Activate.ps1
CMD(명령 프롬프트)를 사용 중인 경우:
cmd
.\venv\Scripts\activate.bat 2. 필요한 라이브러리(패키지) 설치
가상환경이 활성화된 상태 (venv)에서 아래 명령어를 입력하여 Prophet 모델 및 FastAPI 등 필요한 패키지들을 모두 설치합니다.

powershell
pip install -r Backend/requirements.txt
⚠️ 참고 (Prophet 설치 에러 대처법):
만약 설치 중 에러가 발생한다면 pip install --upgrade pip로 pip를 업데이트한 후 pip install prophet을 개별적으로 실행해 보세요.

3단계: 백엔드 API 서버 구동
라이브러리 설치가 끝나면 백엔드 폴더로 이동해 서버를 기동합니다. (가상환경 활성화 상태 유지)

백엔드 폴더로 이동:
powershell
cd Backend
FastAPI 서버 구동:
powershell
python main.py
터미널에 다음과 같은 문구가 뜨면 백엔드가 http://127.0.0.1:8000 주소로 완벽히 켜진 것입니다.
text
INFO: Started server process [XXXX]
INFO: Waiting for application startup.
INFO: Application startup complete.
INFO: Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
IMPORTANT

이 터미널 창은 백엔드 서버가 켜져 있는 창이므로 그대로 켜두셔야 합니다. 다른 명령어를 치려면 새 터미널 창을 하나 더 열어야 합니다.

4단계: 프론트엔드 대시보드 실행 (3가지 방법 중 택 1)
백엔드 서버가 켜진 상태에서 프론트엔드를 실행하는 방법입니다. 편한 방식을 선택해 보세요.

[방법 A] VS Code의 Live Server 사용 (가장 추천 👍)
VS Code 좌측 파일 탐색기에서 Frontend 폴더 아래의 index.html 파일을 마우스 우클릭합니다.
**[Open with Live Server]**를 클릭합니다. (VS Code 화면 우측 하단의 [Go Live] 버튼을 클릭해도 됩니다.)
브라우저가 자동으로 열리며 http://127.0.0.1:5500/index.html 주소로 대시보드가 실행됩니다.
[방법 B] 파이썬 간이 웹 서버 띄우기
VS Code에서 **새 터미널(New Terminal)**을 하나 더 엽니다.
프론트엔드 폴더로 이동합니다:
powershell
cd Frontend
파이썬 기본 웹 서버를 구동합니다:
powershell
python -m http.server 5500
크롬 등 인터넷 브라우저 주소창에 http://127.0.0.1:5500 을 입력하여 접속합니다.

## 2026-06-28

기상청 날씨 데이터 연동 및 트렌드 결합 시각화 구현 계획
기상청 종관기상관측(ASOS) 일자료 오픈 API를 연동하여, 평균 기온 및 강수량 데이터를 네이버 트렌드 데이터와 함께 분석하고 시각화할 수 있는 기능을 추가하고자 합니다.

단위가 다른 두 데이터(검색량 vs 기온/강수량)를 효과적으로 대조하기 위해 이중 Y축(Dual Y-Axis) 차트로 표현합니다.

User Review Required
기상 데이터는 측정 지역(지점)이 필수적입니다.

기본 기상 관측소 지점은 **서울(지점 번호: 108)**을 디폴트로 설정하여 전국 표준 대조군으로 삼겠습니다.
차트 시각화 시, 검색량은 좌측 Y축, 기온/강수량은 우측 Y축에 대응시키고 켜고 끌 수 있는 스위치를 프론트엔드에 추가하겠습니다.
Proposed Changes

1. 백엔드 (Backend)
   [NEW]
   weather_api.py
   공공데이터포털(data.go.kr) 기상청 단기/종관기상관측 일자료 API를 호출하는 서비스 모듈을 생성합니다.
   .env 파일의 ASOS_ENDPOINT 및 DATA_GO_KEY를 로드하여 동작합니다.
   fetch_weather_data(start_date: str, end_date: str, stn_id: str = "108") 함수를 구현합니다.
   요청 날짜 포맷 변환 (YYYY-MM-DD ➔ YYYYMMDD)
   dataType: "JSON", dataCd: "ASOS", dateCd: "DAY" 파라미터 구성
   비동기 httpx.AsyncClient 호출
   JSON 응답에서 날짜(tm), 평균기온(avgTa), 일강수량(sumRn) 리스트 추출 및 반환
   공공데이터포털 트래픽 초과나 인증 오류 발생 시 앱이 마비되지 않도록 예외 처리 후 빈 데이터 반환 안전망 구축
   [MODIFY]
   main.py
   기상청 API 연동 모듈을 불러옵니다: from weather_api import fetch_weather_data
   트렌드 비교 예측 API 엔드포인트 /api/predict (POST)를 수정합니다.
   네이버 데이터랩 트렌드를 가져올 때 기상청 API도 함께 병렬(asyncio.gather 등)로 조회합니다.
   API의 최종 JSON 응답 포맷에 날짜별 날씨 데이터 리스트 weather 키를 통합하여 반환합니다.
   json

"weather": [
{"period": "2023-06-25", "avgTa": 24.5, "sumRn": 0.0},
...
] 2. 프론트엔드 (Frontend)
[MODIFY]
index.html
사이드바 또는 차트 상단 영역에 기상 데이터를 차트에 겹쳐볼 수 있는 옵션 스위치 UI를 추가합니다.
평균 기온 표시 (°C)
일 강수량 표시 (mm)
[MODIFY]
chart-helper.js
ApexCharts 렌더링 구조를 이중 Y축(multi-yaxis) 옵션으로 업그레이드합니다.
첫 번째 Y축 (좌측): 네이버 트렌드 검색량 수치 (0 ~ Max)
두 번째 Y축 (우측): 평균 기온 (-20 ~ 40) 또는 강수량 (0 ~ Max)
기상 변수가 체크되면 차트 데이터 시리즈(Series)에 추가하고, 체크 해제 시 제거하여 실시간 인터랙션을 지원합니다.
기온은 얇은 보라색/오렌지색 **실선(Line)**으로, 강수량은 연한 하늘색 **막대(Column)**로 겹쳐 띄워 시각적 간섭을 최소화합니다.
[MODIFY]
app.js
/api/predict가 내려준 기상 데이터를 글로벌 변수나 인스턴스 멤버에 바인딩하여 보관합니다.
기상 관측 스위치를 조작할 때마다 chartHelper 인스턴스의 차트 갱신 메서드를 재호출하는 핸들러를 바인딩합니다.
Verification Plan
Automated/Manual Verification
백엔드 단위 테스트: weather_api.py를 단독 실행하여 공공데이터포털로부터 서울(108) 지점 날씨 데이터가 JSON으로 파싱되어 올바르게 출력되는지 검증합니다.
이중 축 연동 차트 검증:
http://localhost:5500에 접속하여 '식품' 관련 키워드 그룹(예: '아이스크림', '호빵')을 조회합니다.
차트에서 '평균 기온 표시' 스위치를 켰을 때, 한여름(기온 30도 이상)에 아이스크림 검색량이 오르고, 겨울에 호빵 검색량이 오르는 경향성이 차트 한 화면 상에서 이중 축으로 정상 매칭되는지 눈으로 확인합니다.

2026-06-28
폼 예측 블라인드 해제, 기본 4개월 줌 및 네이버 밝은 초록색 테마 적용 계획
사용자가 키워드를 직접 입력하고 분석을 실행할 때 발생하는 차트 가림 현상과 로딩 중 키워드 불일치 버그를 핫픽스하고, 날씨 옵션 기본 활성화, 디폴트 4개월 줌 화면 포커싱, 그리고 과거 트렌드 꺾은선을 네이버 공식색보다 밝고 선명한 초록색으로 커스터마이징합니다.

User Review Required
IMPORTANT

폼 실행 시 차트 가림막 걷기 패치:
폼 서브밋 핸들러 완료 시점에 차트 가림막(#chart-placeholder)이 완벽히 가려지도록(display = 'none') 조치하여 차트 블라인드 현상을 해결합니다.
로딩 중 사용자 입력 키워드 동적 매핑:
분석 로딩 창이 뜰 때 사용자가 입력한 그룹명/키워드가 동적으로 출력되도록 수정합니다.
평균 기온 / 강수량 기본 체크 상태 설정:
대시보드 최초 로딩 시 날씨 체크박스 2종이 기본적으로 checked 상태로 표기되게 HTML 속성을 부여합니다.
차트 기본 조회 화면 4개월치 설정:
최초 렌더링 시 줌아웃 상태(10년 전체) 대신 최근 4개월(120일) 구간으로 줌인하여 가장 트렌디한 최근 동향을 1차적으로 조명하고, 줌인/줌아웃 버튼을 통한 거시/미시 스팬 조절은 동일하게 제공합니다.
과거 트렌드 초록색 테마 적용:
과거 트렌드 관심도 선을 네이버 공식 그린(#03c75a)보다 조금 더 밝고 선명한 **비비드 초록색 (#02e06b)**으로 전면 전환하여 시인성을 높이고 네이버 데이터랩 본연의 아이덴티티를 극대화합니다.
Proposed Changes

1. 프론트엔드 (Frontend)
   [MODIFY]
   index.html
   평균 기온 및 일강수량 체크박스 인풋에 checked 기본 속성을 추가합니다.
   #chk-weather-temp: <input type="checkbox" id="chk-weather-temp" checked ...>
   #chk-weather-rain: <input type="checkbox" id="chk-weather-rain" checked ...>
   [MODIFY]
   chart-helper.js
   네이버 트렌드 초록색 테마 변경:
   팔레트 색상 배열 this.colors의 첫 번째 색상을 밝은 초록색인 #02e06b 로 변경합니다.
   첫 번째 페이드 컬러 this.colorsFade 도 그에 걸맞게 rgba(2, 224, 107, 0.25) 로 갱신합니다.
   dropShadow의 색상을 첫 번째 활성 라인색(strokeColors[0]인 밝은 초록색)에 맞추어 그림자가 더 아름답게 연출되도록 유지합니다.
   디폴트 줌 범위 4개월(120일) 변경:
   renderChart 의 최초 줌 스팬 연산 기준을 365일에서 **120일**로 축소하여 시작화면을 4개월 기준으로 조준 렌더링합니다.
   [MODIFY]
   app.js
   분석 폼 서브밋 핸들러(forecastForm) 보완:
   폼 실행 시 로딩바의 메시지를 고정 키워드가 아닌 사용자가 입력한 첫 번째 그룹명/키워드를 반영하여 "[그룹명] 분석 수행 중..." 형태로 동적 렌더링합니다.
   API 통신 완료 시점에 #chart-placeholder를 반드시 가리도록(style.display = 'none') 누락된 분기를 패치합니다.
   Verification Plan
   수동 검증
   분석 폼 실행 및 로딩/블라인드 해제 확인:
   검색창에 키워드를 직접 치고 "분석 실행"을 누르면, 로딩 창에 내가 입력한 키워드가 명확히 표시되는지 확인합니다.
   로딩이 끝난 즉시 차트 가림막이 사라지고 선명한 그래프가 차트판에 온전히 팝업되는지 확인합니다.
   기본 4개월 줌 상태 확인:
   차트가 로드되자마자 4개월(약 120일) 구간만 확대해서 표시하는지 확인합니다.
   네이버 밝은 초록색 선 시인성 대조:
   과거 트렌드 선이 네이버 공식 브랜드 컬러보다 화사하고 밝은 초록색(#02e06b)으로 선명하게 수 놓아지는지 확인합니다.

## 추가 변경 사항

메타버스 기본 비교 그룹 제거 및 주황색 전조 포인트 소거 계획
대시보드 최초 진입 및 폼 실행 시 불필요하게 날아오던 메타버스(그룹 2) 과거 데이터를 차단하기 위해 기본 마크업에서 메타버스 필드를 제거하고, 차트 위를 어지럽히던 주황색/빨간색 유행 전조 시그널 마커(Annotations)를 제거하여 깨끗한 꺾은선 뷰를 완성합니다.

User Review Required
IMPORTANT

메타버스(그룹 2) 기본 필드 제거:
index.html 의 기본 키워드 비교 그룹 중 "메타버스"로 자동 지정되어 있던 그룹 2 마크업을 완전히 소거합니다.
첫 페이지 진입 시에는 오직 사용자가 원하는 단일 키워드(그룹 1)만 표시되게 하여, 혼선과 불필요한 과거 데이터 조회를 완전히 차단합니다.
사용자가 원할 경우 기존의 "+ 키워드 그룹 추가" 버튼을 통해 그룹을 동적으로 늘려 비교해 볼 수 있는 유연성은 그대로 유지합니다.
차트 주황색/빨간색 전조 포인트(Annotations) 소거:
chart-helper.js 에서 검색량 변화 구간 위에 주황색/빨간색 도트로 달라붙던 signalAnnotations 생성을 영구 비활성화하여, 깔끔하고 시인성이 극대화된 꺾은선 그래프 본연의 화면을 보여줍니다.
Proposed Changes

1. 프론트엔드 (Frontend)
   [MODIFY]
   index.html
   keyword-groups-container 하위에 기본으로 기입되어 있던 Group 2 (메타버스 입력 영역)를 전면 삭제합니다.
   [MODIFY]
   chart-helper.js
   renderChart 함수 내의 signals.forEach(...) 루프 동작을 주석 처리 또는 제거하여 signalAnnotations 배열로 좌표가 주입되지 않게 처리합니다.
   Verification Plan
   수동 검증
   기본 키워드 필드 확인:
   화면을 새로고침했을 때 왼쪽 사이드바 비교 그룹에 메타버스 관련 그룹 2가 기본적으로 비워진 채 그룹 1만 단독으로 나타나는지 확인합니다.
   차트 내 어노테이션 포인트 소멸 확인:
   키워드를 클릭하거나 조회했을 때, 꺾은선 중간중간에 나타나던 눈에 거슬리는 주황색/빨간색 포인트 도트와 텍스트 라벨이 완벽히 사라졌는지 확인합니다.

## 2026-06-29

날씨 데이터(기온, 강수량)를 Facebook Prophet 모델의 설명 변수(Regressor)로 주입하여 함께 학습하고 예측하는 작업을 완벽하게 완료했습니다!

구체적인 작업 내용과 검증 결과는 다음과 같습니다.

🛠️ 구현 핵심 내용
날씨 설명 변수(Regressor) 추가 (

forecaster.py
): 학습에 사용되는 네이버 트렌드 시계열 데이터셋에 기온(temp)과 강수량(rain) 컬럼을 결합하고, Prophet 모델 생성 시 두 변수를 Regressor로 추가하여 학습을 고도화했습니다.
미래 날씨 결측치 예측 보완: Prophet 모델이 미래를 예측할 때 미래 날씨 데이터도 함께 제공되어야 하는 제약이 있습니다. 이를 해결하기 위해, 미래 예측 대상 일자의 날씨 정보는 '작년 동기간(365일 전)'의 실제 날씨를 복제해서 빈틈없이 채우도록 시뮬레이션 로직을 설계했습니다.
백테스트 평가 연동 (

main.py
): 예측 기능뿐만 아니라 백테스트 모델 검증(evaluate_trend_accuracy) 연산 시에도 동일하게 기상 데이터를 엮어 오차율(MAPE)과 정확도를 다시 매핑시켰습니다.
📊 검증 완료 (test_api.py 통과)
로컬 검증 스크립트 실행 결과, 기상 변수가 결합된 Prophet 예측 알고리즘(Facebook Prophet (날씨 기상 변수 결합 모델))이 오류 없이 정상 피팅되고 MAPE 오차율이 안전하게 산출되는 것을 확인했습니다.

자세한 작업 이력은
walkthrough.md
파일에 자세히 정리해 두었습니다.

실행 방법
🚀 실행 방법 (상세 가이드)
(PowerShell 사용 시 필수) 스크립트 실행 권한 허용
Windows PowerShell에서는 기본적으로 가상환경 스크립트 실행이 차단되어 있을 수 있습니다. 터미널에 아래 명령어를 복사하여 붙여넣고 엔터를 칩니다.

powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
(이 명령은 현재 열려 있는 터미널 창에 한해 가상환경 활성화 권한을 임시로 부여합니다.)

1. 가상환경 활성화
   내가 사용하는 터미널 종류에 맞게 아래 명령어를 입력합니다. (성공하면 경로 앞에 (venv)라는 표시가 붙습니다.)

PowerShell을 사용 중인 경우:
powershell
.\venv\Scripts\Activate.ps1
CMD(명령 프롬프트)를 사용 중인 경우:
cmd
.\venv\Scripts\activate.bat 2. 필요한 라이브러리(패키지) 설치
가상환경이 활성화된 상태 (venv)에서 아래 명령어를 입력하여 Prophet 모델 및 FastAPI 등 필요한 패키지들을 모두 설치합니다.

powershell
pip install -r Backend/requirements.txt
⚠️ 참고 (Prophet 설치 에러 대처법):
만약 설치 중 에러가 발생한다면 pip install --upgrade pip로 pip를 업데이트한 후 pip install prophet을 개별적으로 실행해 보세요.

3단계: 백엔드 API 서버 구동
라이브러리 설치가 끝나면 백엔드 폴더로 이동해 서버를 기동합니다. (가상환경 활성화 상태 유지)

백엔드 폴더로 이동:
powershell
cd Backend
FastAPI 서버 구동:
powershell
python main.py
터미널에 다음과 같은 문구가 뜨면 백엔드가 http://127.0.0.1:8000 주소로 완벽히 켜진 것입니다.
text
INFO: Started server process [XXXX]
INFO: Waiting for application startup.
INFO: Application startup complete.
INFO: Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
IMPORTANT

이 터미널 창은 백엔드 서버가 켜져 있는 창이므로 그대로 켜두셔야 합니다. 다른 명령어를 치려면 새 터미널 창을 하나 더 열어야 합니다.

4단계: 프론트엔드 대시보드 실행 (3가지 방법 중 택 1)
백엔드 서버가 켜진 상태에서 프론트엔드를 실행하는 방법입니다. 편한 방식을 선택해 보세요.

[방법 A] VS Code의 Live Server 사용 (가장 추천 👍)
VS Code 좌측 파일 탐색기에서 Frontend 폴더 아래의 index.html 파일을 마우스 우클릭합니다.
**[Open with Live Server]**를 클릭합니다. (VS Code 화면 우측 하단의 [Go Live] 버튼을 클릭해도 됩니다.)
브라우저가 자동으로 열리며 http://127.0.0.1:5500/index.html 주소로 대시보드가 실행됩니다.
[방법 B] 파이썬 간이 웹 서버 띄우기
VS Code에서 **새 터미널(New Terminal)**을 하나 더 엽니다.
프론트엔드 폴더로 이동합니다:
powershell
cd Frontend
파이썬 기본 웹 서버를 구동합니다:
powershell
python -m http.server 5500
크롬 등 인터넷 브라우저 주소창에 http://127.0.0.1:5500 을 입력하여 접속합니다.
