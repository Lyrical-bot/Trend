# 📋 CHANGELOG — 프로젝트 업데이트 이력

> 이 문서는 초창기 `AGENT_INSTRUCTIONS.md` 작성 이후 진행된 모든 주요 변경 사항을 기록합니다.
> 프로젝트의 **현재 상태**를 파악하려면 이 문서를 기준으로 삼으세요.

---

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
   - *(참고: 초기에 10년 치로 확장했으나 API 응답 속도 및 모델 학습 속도 저하 문제로 2년으로 내렸다가, 완전한 3번의 여름 사이클(23년 4월 말 시작)을 확보하기 위해 최종 3년 3개월로 타협)*
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
     - *`SMAPE` (대칭 평균 절대 백분율 오차)*: 검색량이 적을 때 오차율이 과도하게 뻥튀기되는 기존 MAPE의 단점을 보완한 지표입니다.
     - *`MAE` (평균 절대 오차)*: 퍼센트(%)가 아닌 "실제 검색량 수치(건수)"가 평균적으로 얼마나 차이 났는지 보여주는 직관적인 지표입니다.
     - *방향성 정확도 (`directionAccuracy`)*: 검색량이 내일 오를지 내릴지, 그 '추세의 방향'을 맞춘 확률(%)을 의미합니다.
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
