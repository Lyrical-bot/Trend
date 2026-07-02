# 📋 CHANGELOG — 프로젝트 업데이트 이력

> 이 문서는 초창기 `AGENT_INSTRUCTIONS.md` 작성 이후 진행된 모든 주요 변경 사항을 기록합니다.
> 프로젝트의 **현재 상태**를 파악하려면 이 문서를 기준으로 삼으세요.

---

## 🚀 v3.12.1 — 안정성 핫픽스 및 프론트엔드 UX 개선 (2026-07-02)

### 주요 개선 사항
1. **스케줄러 콜드스타트 지연 버그 수정**
   - 기존에는 DB에 영상(Video)이 하나라도 있으면 스케줄러 가동을 3시간 미루는 구조였으나, 스파이크 필터(`TrendingKeyword`) 테이블이 비어있는 경우(예: 신규 파이프라인 마이그레이션 직후)에도 작동을 미루어 화면이 비어있는 현상 발견.
   - `scheduler.py`의 시작 조건을 `video_exists and trend_exists`로 변경하여, 트렌드 테이블이 비어있다면 즉시 1회 수집 파이프라인이 가동되도록 수정.
2. **DB 무결성 에러 (UNIQUE constraint) 원천 차단**
   - 하나의 배치 내에서 동일한 키워드가 중복으로 추출될 경우, `db.commit()` 이전에 중복을 인지하지 못해 `sqlite3.IntegrityError`가 발생하며 수집이 중단되는 치명적 버그 해결.
   - `runner.py`와 `backfill_from_db.py`의 루프 내부에 `db.flush()`를 삽입하여, 삽입 즉시 메모리 상태를 반영하여 중복 에러를 방지하도록 무결성 보장.
3. **프론트엔드 트렌드 점수 툴팁 UX 개선**
   - 기존의 원시 데이터(평균 구독자 수 등)를 단순 나열하던 방식에서, **항목별 획득 점수와 비즈니스적 의미(폭발력, 블루오션, 바이럴, 대중성)**를 직관적으로 설명하는 툴팁으로 전면 교체.
   - 대형 채널 1개로 인한 평균 구독자 하향 평준화 현상 등 사용자의 오해를 방지하고 점수의 신뢰도를 높임.

---

## 🚀 v3.12.0 — GPT-Native 아키텍처 및 Azure OpenAI 연동 완료 (2026-07-02)

### 주요 개선 사항
1. **형태소 분석기(Kiwi) 완전 대체 및 GPT-Native 추출 파이프라인 도입**
   - 기존 N-gram 단위 추출로 인해 발생하던 "크루키", "방탄소년단 버터" 등의 오탐 문제를 해결하기 위해, OpenAI의 Structured Outputs 기능을 이용한 `gpt_extractor.py`를 신설했습니다.
   - 키워드가 단일 일반명사인지, 구체적 조합형/고유명사인지 판단하는 `is_compound` 논리를 GPT가 스스로 판별하도록 강제하여, 일반 식재료명("버터", "우유")이 트렌드로 둔갑하는 현상을 원천 차단했습니다.
2. **아키텍처 3단계 분리 (Publish Gate 도입)**
   - "추출", "승격", "노출" 세 단계를 엄격히 분리했습니다.
   - `is_compound = False` 인 일반 단어는 추출 즉시 `NOISE` 상태로 처리되고, `True`인 구체적 명칭은 `PENDING`으로 대기하다가, **스파이크 필터(단기 폭발적 언급량 급증 감지기)**를 만족했을 때만 비로소 `TREND`로 승격됩니다.
3. **과거 데이터 소급(Backfill) 자동 연동**
   - 시스템 최초 가동 시(과거 데이터 14일 치 부재 시) `fetch_historical_youtube_videos()` 모듈을 호출하여, 스파이크 필터가 당일 즉시 작동할 수 있도록 초기 표본 데이터 세팅을 자동화했습니다.
4. **회귀 테스트 및 Azure OpenAI 자동 지원**
   - 3대 리스크(엔터 노이즈, 일반 명사 오탐, 표기 파편화)를 자동 검증하는 `test_gpt_extractor.py` 회귀 테스트를 신설했습니다.
   - 환경 변수(.env)에 `AZURE_OPENAI_API_KEY`가 존재할 경우, 자동으로 Azure OpenAI 클라이언트(`gpt-4o-mini` Deployment)를 사용하도록 유연성을 확보했습니다.

## 🚀 v3.11.0 — 정량적 스파이크(Spike) 필터 및 GPT 파이프라인 연동 구현 (2026-07-02)

### 주요 개선 사항
1. **정량적 스파이크 1차 필터 도입 (비용/효율 최적화)**
   - 💡 **스파이크 필터란?** "어쩌다 한 번 언급된 단어"를 걸러내고, "최근 3일 내 언급량이 과거 대비 2배 이상 폭발적으로 급증했는지"를 수학적으로 감지하여 **진짜 유행의 전조만 통과시키는 수문장(Gatekeeper)** 역할입니다.
   - GPT에게 모든 키워드를 넘길 때 발생하던 비용 및 노이즈 문제를 해결하기 위해, 정량적 언급량 급증(Spike)을 판별하는 1차 게이트키퍼를 `signal_engine.py`에 도입했습니다.
   - 단일 `GROUP BY` 배치 쿼리를 통해 최근 3일간 절대량 하한선(5건)을 만족하면서 과거 14일 대비 200% 이상 급상승한 키워드만 선별하여 GPT 호출 예산을 방어합니다.
   - 과거 14일 언급량이 0인 신규 키워드(콜드 스타트)의 경우에도 절대량 조건을 만족하면 1차 필터를 통과하도록 예외 로직을 구현했습니다.
2. **`TrendingKeyword` 생애주기 관리 및 블랙리스트 방지**
   - 1차 필터를 통과한 키워드들의 상태(`PENDING`, `TREND`, `NOISE`, `EXPIRED`)를 관리하는 신규 테이블(`TrendingKeyword`)을 추가했습니다.
   - GPT로부터 `NOISE` 판정을 받았던 키워드라도, 다시 스파이크 조건을 만족하면 블랙리스트화되지 않고 재평가를 받도록 구현하여 '유행 전조'를 놓치지 않도록 방어했습니다.
3. **주기적 재평가 (TTL) 로직 구축**
   - 기존 `TREND` 상태인 단어라도, 최근 3일간의 언급량이 하한선 밑으로 떨어지면 스케줄러가 자동으로 `EXPIRED` 상태로 만료시키도록 `update_expired_trends` 로직을 추가했습니다.
4. **GPT 문맥(Context) 프롬프트 고도화**
   - GPT가 "이 키워드가 최근 특정 맥락으로 몰려 나타나는 트렌드인지"를 정확하게 파악할 수 있도록, 키워드가 포함된 최근 5개 영상의 **제목과 업로드 일시(`published_at`)**를 함께 컨텍스트로 전달합니다.

## 🚀 v3.10.1 — 트렌드 시계열 통계(KeywordStat) 오염 완전 복구 및 무결성 확보 (2026-07-01)

### 주요 개선 사항
1. **KeywordStat 버킷 기준일 휴리스틱 버그 수정 및 데이터 완벽 복구**
   - 백필(과거 수집) 영상과 정규 파이프라인 수집 영상 간의 시간대 버킷(`hour`)이 상이하게 적용(발행일 vs 수집일)되는 구조에서, 단순 시간 차이(`days >= 1`)로 버킷을 추론하던 불안정한 휴리스틱을 전면 제거했습니다.
   - 각 비디오가 수집될 때 최초로 생성된 `VideoStat`의 `hour` 값을 "진실의 기준(Ground Truth)" 버킷으로 역추적하여 매핑하도록 `scripts/rebuild_keyword_stats.py`를 작성했습니다.
   - 기존의 심각하게 오염되었던(백필 파이프라인의 MVP 한계로 인한 채널 수 과대 계상, 매칭 오류로 인한 특정 키워드 증발 현상 등) `KeywordStat` 테이블 데이터를 안전하게 전체 삭제한 후, 원본(`Video`, `Keyword`)을 토대로 691개의 무결한 시계열 버킷 데이터로 100% 복구 완료했습니다.
2. **데이터 파괴/재생성 작업 안전망(Safety Net) 구축**
   - 향후 DB 데이터를 대규모로 재생성/수정할 때 발생할 수 있는 엔지니어링 에러를 막기 위해, 스크립트 실행 구조를 전면 개편했습니다.
   - `--dry-run` 모드(기본값)를 통해 메모리 상에서 먼저 데이터를 구성하고, 스크립트와 무관하게 직접 DB를 쿼리하여 얻어낸 '의심 케이스 4종'의 정답셋(Ground Truth)과 코드가 스스로 자동 대조(Assert)하도록 방어 로직을 구성했습니다.
   - 검증 테스트를 100% 통과한 경우에만 `--commit` 플래그를 통해 실제 DB `DELETE` 및 `INSERT`를 수행하도록 안전 밸브를 장착하여 운영 안정성을 극대화했습니다.

---
## 🚀 v3.10.0 — 복합 Trend Score(MVP) 체계 도입 및 데이터 품질 개편 (2026-07-01)

### 주요 개선 사항
1. **단순 TF-IDF 랭킹 폐기 및 100점 만점 Trend Score 도입**
   - 조회수 총합 등에 의존하던 기존 랭킹 방식을 버리고, **"채널당 평균 조회수"**와 **"독립 채널 수(다양성)"**를 분리하여 평가하는 수학적 스코어링 모델을 `sns_sensing/api/main.py`에 이식했습니다.
   - 구성 지표(Max 100점): 평균 조회수(40점) + 평균 구독자 파워(20점) + 조회수/구독자 비율(25점) + 업로드 밀집도(15점)
2. **단일 채널 밈 원천 차단 (Gate Multiplier)**
   - "여러 채널이 동시에 이야기하기 시작하는 것"이 유행의 전조라는 핵심 비즈니스 로직을 반영하여, 채널 다양성을 단순 가산점이 아닌 **승수(Multiplier, 0.35~1.0)**로 도입했습니다.
   - 단 한 개의 채널에서만 발화된 키워드는 기본 점수 만점을 받아도 최대 35점으로 강등되어 프론트엔드 노출(40점 컷오프)에서 완벽히 배제됩니다.
3. **범용 단어 필터 로직 고립 및 유지**
   - TF-IDF의 IDF(희귀도) 로직은 "어디서나 쓰이는 흔한 명사(예: 리뷰, 브이로그 등)"를 자동으로 필터링하는 사전 게이트키퍼(`_is_generic_word`) 역할로만 재배치했습니다.
4. **프론트엔드 트렌드 UI 개편**
   - 백엔드에서 전달된 100점 만점 스코어를 기반으로, 트렌드 칩의 색상을 3단계(90점 이상, 70점 이상, 그 이하)로 직관적으로 구분했습니다.
   - 키워드 칩에 마우스 호버(Hover) 시, 해당 트렌드를 결정지은 세부 근거(독립 채널 수, 업로드 수, 평균 조회수, 평균 구독자)를 툴팁으로 투명하게 제공합니다.
5. **[Hotfix] GPT 과잉 정규화(Over-canonicalization) 방지 및 눈덩이 편향 로직 수정**
   - "카라멜 치즈 토스트"처럼 핵심 재료 수식어가 포함된 고유 메뉴가 상위 개념("치즈토스트")으로 잘려나가는 문제를 해결하기 위해, GPT 프롬프트에 구체적인 O/X 예시 및 "핵심 재료 보존" 절대 규칙을 추가했습니다.
   - 특정 카테고리(예: 치즈)가 `recent_canonicals`를 점유하여 다른 키워드들을 강제로 편입시키는 눈덩이(Snowball) 효과를 방지하기 위해, `runner.py`에서 대표 키워드 참조 시 상위 카테고리별로 분산하여 무작위 혼합(Shuffle) 후 제한된 개수(최대 50개)만 전달하도록 로직을 개선했습니다.
6. **[Documentation] 전체 프로젝트 청사진(README.md) 구축**
   - 파이프라인 고도화로 파일 개수가 방대해짐에 따라, 프로젝트 전체 구조를 한눈에 파악할 수 있는 완전한 ASCII Tree 형태의 `README.md`를 신규 작성했습니다.
   - `Backend`, `sns_sensing`, `Frontend` 등 각 폴더와 핵심 파일의 1줄 역할 설명뿐만 아니라, 어느 파일이 어느 파일과 연동되는지 보여주는 **상호작용(Data Flow) 맵**을 명시하여 유지보수성을 극대화했습니다.

---

## 🚀 v3.9.0 — 자가 진화형 유튜브 동적 시드(Seed) 풀 아키텍처 도입 (2026-07-01)

### 주요 개선 사항
1. **스케줄러 기반 동적 카테고리 시드 확장**
   - 고정된 시드 키워드(15개)를 폐기하고, 네이버 쇼핑 인사이트 5개 세부 카테고리(유가공품, 다이어트식품, 빵/베이커리, 스낵/과자, 젤리/사탕/초콜릿)의 Top 500 검색어를 6시간마다 긁어오는 로직을 `scheduler.py`에 추가
   - 수집된 키워드들의 순위에 따라 가중치(Weight)를 차등 부여하여 `cached_youtube_seeds.json` 파일에 저장하도록 구현
   - 네이버 API 호출 제한(Rate Limit, 429 에러) 방지를 위한 호출 간격 지연(0.5초) 및 2초 대기 후 재시도(Exponential Backoff 성격) 로직 추가
2. **가중치 및 템플릿 기반 수집기 고도화**
   - `seed_collector.py`에서 기존 단순 무작위 추출 방식을 버리고, `random.choices(weights=...)`를 활용한 랭킹 가중치 기반 추출 방식으로 개선
   - 트렌드 최상위 키워드가 더 자주 추출되도록 보장하면서도 낮은 순위 키워드도 간간이 섞이도록 설계
   - 시드 단어 뒤에 무작위 템플릿 접미사(" 리뷰", " 먹방", " 레시피", " 신상", " 비교", " 편의점")를 결합하여 유튜브 검색 쿼리를 생성 (예: "크룽지 신상", "버터 리뷰")
   - 이를 통해 동일 키워드에 갇히지 않고 더 광범위하고 다양한 유튜브 영상(새로운 롱테일 영상)을 발굴하도록 진화

---

## 🚀 v3.8.1 — 백필 수집 밀도 강화 및 초기 산출 방어 로직 (2026-07-01)

### 주요 개선 사항
1. **백필(Backfill) 표본 밀도 대폭 상향**
   - `seed_collector.py`의 과거 데이터 소급 수집(`fetch_historical_youtube_videos`) 시 하루 최대 수집량(`max_results_per_day`)을 5개에서 30개로 상향
   - 과거 14일 치 수집량이 총 420개로 증가하여 과거 비교군 데이터의 통계적 유의성을 확보
2. **성장률(Growth) 산출 게이팅 기간 하향 복구**
   - `Backend/main.py`의 `db_days_active` 기반 게이팅 기준을 14일에서 7일로 변경
   - 초기 데이터 밀도 부족으로 인한 과도한 왜곡(999%)은 막으면서도, 런칭 후 7일 차부터 즉각적으로 유의미한 성장률 수치를 제공하도록 개선
3. **"초기 산출(참고용)" UI 안전장치 배지 추가**
   - 백필 데이터가 섞여있는 7일~13일 구간(`db_days_active >= 7 and < 14`)에서는 백엔드가 `is_low_res_growth = True` 플래그를 발급
   - 프론트엔드(`app.js`)는 이 구간의 성장률 옆에 "⚠️초기 산출(참고용)" 배지를 노출하여, 표본 수가 제한적일 수 있음을 사용자가 인지하도록 시각적 방어망 구축
4. **단위 테스트(Unit Test) 갱신**
   - `test_youtube_growth.py`에 6일, 7일, 14일 등 세분화된 경계값 유닛 테스트를 신설하여 성장률 null 처리 및 `is_low_res_growth` 분기 처리 완벽 검증

---

## 🚀 v3.8 — 트렌드 키워드 자동 정제 파이프라인 및 지표 고도화 (MVP) (2026-07-01)

### 주요 개선 사항
1. **N-gram 추출 및 로컬 통계 엔진(PMI) 탑재**
   - `keyword_extractor.py`를 신설하여 유튜브 제목/본문에서 1~3 gram 명사구를 모두 추출
   - 단어 간 Co-occurrence(공동출현) 빈도와 PMI(점별 상호정보량)를 자체 연산
   - TF-IDF 알고리즘을 변형 적용하여 가장 강력한 트렌드 신호를 뿜어내는 '절대 순위' 도출 기능 마련
2. **이원화 컷오프(Cut-off) 필터 적용**
   - 하루 수만 개의 키워드를 GPT에 전송하는 비용 낭비를 막기 위해 `candidate_selector.py` 도입
   - 현재 가장 핫한 **절대 순위 Top 120개**와 최근 3일간 급성장한 **증가율 상위 Top 30개**만을 선별하여 정예 후보 150여 개로 압축
3. **로컬 1차 매칭 및 GPT 통합 추출/매핑 고도화**
   - `keyword_filter.py`의 시스템 프롬프트 개편: 단순 필터링을 넘어 `{brand, item, category, action, canonical_name}`의 5가지 필드 분리 추출
   - 프롬프트에 '최근 확정된 Canonical Name(대표 명칭)' 목록 100개를 함께 전달하여 단 1회의 호출로 정보 추출과 동의어 통합 매칭을 동시에 수행
   - GPT가 식별한 새로운 브랜드는 `BrandDictionary` 로컬 DB에 자동 축적되어 차기 수행 시 API 호출 없이 로컬에서 즉시 컷아웃(매칭)되도록 선순환 구조 완성
4. **Trend Score 엔진 재설계 (가중치 기반)**
   - `signal_engine.py`에 유튜브 전용 종합 점수를 도출하는 `calculate_sns_trend_score` 로직 신설
   - 어뷰징 방지를 위해 **채널 다양성(Channel Diversity)** 지표에 기하급수적 가중치(`unique_channels ** 1.5 * diversity * 10`)를 부여하여 대중적으로 확산된 진짜 트렌드에 점수를 몰아줌
5. **정규화 DB 스키마 완벽 지원**
   - `models.py`에 `BrandDictionary`, `CanonicalKeyword`, `RawKeywordMapping`, `CoOccurrence` 등 4종의 신규 테이블을 추가하여 파편화된 원시 단어들이 하나의 대표 이름(Canonical Name)으로 응집되도록 인프라 마련
   - `runner.py`를 개편하여 새로 추출 및 통합된 스키마 구조로 키워드와 통계(KeywordStat)를 정상 적재하도록 DB 저장 파이프라인 전면 개편


## 🚀 v3.7.1 — LLM 필터링 안정성 강화 및 띄어쓰기 복합명사 누락 버그 핫픽스 (2026-06-30)

### 주요 개선 사항
1. **LLM 필터 우회 취약점(Fail-Open) 수정**
   - GPT-4o-mini가 간혹 지시를 어기고 `["단어1", "단어2"]` 형태의 단순 문자열 리스트로 응답할 때, 이를 맹목적으로 유효 키워드로 추가해버리던 버그를 수정
   - 잘못된 포맷의 응답은 즉시 무시(`Fail-Closed`)하도록 예외 처리를 강화하여 "사장", "The"와 같은 의미 없는 노이즈 데이터 유입을 원천 차단
2. **띄어쓰기 포함 복합명사(Bi-gram) 누락 버그 해결**
   - LLM 필터가 띄어쓰기를 압축하여 반환할 때, 원본 단어와 단순 텍스트 비교(`in`)를 수행하여 "두바이 초콜릿" 같은 중요 복합명사가 모두 탈락하던 버그 수정
   - `classify_keywords_batch`가 `{원본 단어: 정규화된 단어}` 형태의 매핑 딕셔너리를 반환하도록 고도화하여, 복합명사가 정상 수집되고 DB에는 정제된 이름으로 기록되도록 파이프라인 완벽 복구
3. **DB 노이즈 데이터 소급 대청소 완료**
   - `clean_db_retroactive.py` 스크립트를 신규 딕셔너리 구조에 맞춰 고도화
   - 누적된 3,939개 과거 DB 키워드 전체를 재평가하여 약 3,200건 이상의 쓰레기 노이즈 키워드 및 통계 데이터를 영구 삭제 완료

## 🚀 v3.7 — LLM 기반 자동 정규화 및 줄임말 통합 병합(Auto-Normalization) (2026-06-30)

### 주요 개선 사항
1. **줄임말 및 동의어 자동 병합 (Entity Resolution)**
   - GPT-4o-mini의 프롬프트에 `standard_name` 반환 필드를 추가하여, 입력된 단어가 줄임말이거나 파편화된 단어일 경우(예: '두쫀쿠', '애사비') 대중적인 풀네임('두바이쫀득쿠키', '애플사이다비니거')으로 자동 변환하도록 기능 고도화
   - 별도의 수동 줄임말 사전 없이 AI의 맥락 이해를 통해 실시간 트렌드 용어를 정규화
2. **해시태그식 공백 전면 제거 (Spacing Normalization)**
   - 동일한 키워드임에도 "두바이 쫀득 쿠키"와 "두바이쫀득 쿠키"처럼 띄어쓰기가 달라 검색량과 언급량이 분산되는 데이터 파편화 현상을 해결
   - LLM 필터링의 최종 반환 단계에서 모든 공백을 압축(제거)하여 DB에 저장함으로써 데이터의 파괴력을 한 곳으로 완벽하게 응집

---

## 🚀 v3.6 — 신조어 및 미등록어 포집망(OOV Catcher) 도입 (2026-06-30)

### 주요 개선 사항
1. **형태소 분석기(Kiwi) 추출 허용 태그 대폭 확대**
   - 1차 키워드 추출(`keyword_discovery.py`) 시 기존의 명사(`NNG`, `NNP`)뿐만 아니라, **미등록어(`UN`), 어근(`XR`), 외국어(`SL`), 일반부사(`MAG`)** 태그까지 모두 유효한 키워드 후보로 인정하도록 로직 확장
   - 이를 통해 국어사전에 없어 버려지던 "왁뿌" 같은 신조어 및 "쫀득", "바삭" 같은 중요 수식어들을 완벽히 포착
2. **무한 콤보(N-gram Chunking) 결합 로직 도입**
   - 위에서 허용한 태그들이 연속해서 등장할 경우, 이를 하나의 덩어리(Chunk)로 묶은 뒤 길이 2~4의 모든 부분집합(Bigram, Trigram, 4-gram)을 모조리 추출 (예: `[왁뿌] + [소금빵] -> "왁뿌 소금빵"`)
3. **형태소 파괴 방지용 원시 단어(Raw Word) 추가**
   - "두바이쫀득쿠키"처럼 형태소 분석기가 과도하게 쪼개버려서 원형이 사라지는 현상을 방어하기 위해, 띄어쓰기 단위의 원시 텍스트도 1차 필터 후보군에 강제 포함
   - 추출된 다량의 후보군들은 어차피 2차 LLM(GPT-4o-mini)이 완벽하게 필터링하므로 노이즈 걱정 없이 그물망을 극대화함

---

## 🚀 v3.5 — Azure OpenAI 기반 키워드 정제 2차 필터 도입 (2026-06-30)

### 주요 개선 사항
1. **Azure OpenAI GPT-4o-mini 파이프라인 연동**
   - 유튜브에서 수집된 대량의 후보 단어들 중 '진짜 식품 트렌드'만 남기도록 판단하는 `keyword_filter.py` 모듈 생성
   - `["word": "단어", "valid": true, "confidence": 0.95]` 형태의 정교한 JSON 반환 프롬프트 도입 (지역 특산물 예외 허용 및 먹방/리뷰 조건부 허용)
2. **복합명사(Bi-gram) 추출 로직 개선**
   - 기존의 단일 명사 추출을 넘어 "망고" + "아이스크림" -> "망고 아이스크림"과 같이 2개 이상의 연속된 명사를 조합하여 추출하도록 `keyword_discovery.py` 고도화
   - `STOPWORDS` 리스트에서 "먹방", "리뷰"를 해제하여 트렌드 발화점 키워드가 1차 통과되도록 완화
3. **배치(Batch) 처리로 API 비용 최적화**
   - 10개 영상에서 수집된 수백 개의 단어를 중복 제거 후 1개의 Prompt에 담아 LLM으로 전송하여 API 호출 비용 및 속도 개선
4. **LLM 모듈 독립 폴더 분리**
   - 향후 확장을 대비하여 OpenAI 관련 파일을 `sns_sensing/pipeline/openai_keyword_filter/` 폴더로 분리
5. **과거 DB 노이즈 데이터 소급 삭제 완료**
   - 새로 바뀐 LLM 필터를 기존에 쌓인 DB 데이터에 일괄 적용(AI 대청소)하여 수백 개의 노이즈 키워드 및 관련 통계를 영구 삭제 완료

---

## 🚀 v3.4 — Trend Bot MVP 핵심 지표 및 시계열 스키마 개편 (2026-06-30)

### 주요 개선 사항
1. **시계열 DB 스키마 (`VideoStat`) 도입**
   - `models.py`에 `VideoStat` 테이블 추가: 단순 스냅샷을 넘어 매 3시간마다 영상의 조회수, 좋아요, 댓글수를 누적 기록
   - `Video` 테이블에 `subscriber_count`(구독자 수) 컬럼을 추가하여 대형/소형 채널별 노이즈 필터링 기반 마련
2. **수집 파이프라인 (Data Pipeline) 통계 일괄 수집 최적화**
   - `seed_collector.py` 및 `runner.py`에서 YouTube API 호출 시 `part='statistics'` 파라미터 연동
   - API Quota(할당량) 절약을 위해 과거 7일 내 수집된 영상을 50개 단위로 묶어(Batch) 단일 쿼타로 일괄 갱신하도록 통계 파이프라인 전면 개편
3. **분석 엔진 (Analytics Engine) Engagement 스코어링 개편**
   - `signal_engine.py`에 참여도(Engagement Velocity) 계산 공식 도입: `(ΔLikes * 1 + ΔComments * 5) / (ΔViews + α)`
   - 베이지안 스무딩 기법 도입: 전체 영상의 최근 3시간 조회수 증가량 중앙값(Median)을 `α`로 동적 할당하여 뷰가 적은 영상의 비정상적 점수 폭등 억제
4. **데이터 수집 기준일 왜곡 버그 수정**
   - `trend_detector.py`, `velocity_model.py`의 데이터 수집 기준일(`end_date`)을 '오늘'에서 하루가 완전히 마감된 **'어제'** 기준으로 일괄 변경하여 일일 데이터 집계 부족으로 인한 통계 왜곡 현상 방지

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

## 2026-06-29

Azure Database for PostgreSQL 연동 및 GitHub Actions CI/CD 구축
이 계획은 로컬 SQLite 데이터베이스를 클라우드 데이터베이스인 Azure Database for PostgreSQL로 고도화하고, 깃허브 저장소(GitHub Repository)에 코드가 푸시될 때 자동으로 검증 및 배포가 수행되도록 GitHub Actions CI/CD 파이프라인을 연동하기 위한 설계입니다.

User Review Required
IMPORTANT

PostgreSQL 드라이버 설치 필요 백엔드 파이썬 환경에서 PostgreSQL과 통신하기 위해 psycopg2-binary 패키지를 추가로 설치해야 합니다. 승인 시 Backend/requirements.txt에 해당 의존성을 추가하고 가상환경에 설치합니다.

WARNING

GitHub Actions 배포 대상(Target) 확정 필요 CI/CD 파이프라인 구축 시 코드를 어디에 배포(CD)할지 타겟을 결정해야 합니다. 아래 옵션 중 권장하는 **Option A(Azure Web App)**를 기본으로 계획하되, 다른 환경을 원하시면 알려주세요.

Option A (권장): Azure Web App (FastAPI 백엔드) + Azure Static Web Apps (프론트엔드)
Option B: 가상 머신(Azure VM 또는 Ubuntu Server)에 SSH 연결 및 git pull 후 재시작 배포
Proposed Changes

1. Azure PostgreSQL 데이터베이스 연동
   [MODIFY]
   db.py
   연결 구조 최적화: .env에 정의된 DATABASE_URL을 동적으로 읽어오도록 수정합니다.
   하이브리드 지원: DATABASE_URL이 PostgreSQL 주소이면 PostgreSQL용 커넥션을 생성하고, 설정이 없으면 기존 로컬 SQLite 파일 폴더를 폴백(Fallback)으로 자동 구성합니다.
   python

is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
[MODIFY]
requirements.txt
PostgreSQL 연결 드라이버인 psycopg2-binary>=2.9.0 의존성을 추가합니다.
[MODIFY]
.env
Azure PostgreSQL 연결 연결 주소 템플릿을 환경변수 파일에 삽입합니다:
env

DATABASE_URL=postgresql://[username]:[password]@[host]:5432/[dbname]?sslmode=require 2. GitHub Actions CI/CD 구축
[NEW]
ci-cd.yml
CI (지속적 통합): main 브랜치에 푸시 또는 Pull Request가 올 때마다 자동으로 파이썬 의존성 패키지를 설치하고 Linter 및 검증 스크립트(test_api.py)를 기동하여 코드 적합성을 검증합니다.
CD (지속적 배포): 코드 검증이 완료되면 Azure Web App 서비스(인증 자격 증명은 GitHub Secrets에 등록)로 빌드된 코드 패키지를 자동으로 압축 업로드하여 배포를 완료합니다.
Verification Plan
Automated Tests
환경 변수에 로컬 PostgreSQL 혹은 SQLite를 연결한 상태에서 python Backend/test_api.py를 호출해 데이터 수집 및 연산 처리가 예외 없이 완수되는지 확인합니다.
Manual Verification
Azure PostgreSQL 커넥션을 연결하고 서버를 재구동한 뒤 테이블들이 자동으로 매핑 생성(DB 마이그레이션)되는지 검사하고, 대시보드에서 분석 결과가 DB에 정상 적재/조회되는지 테스트합니다.

## 2026-06-29 추가 수정내용

기온 및 강수량 체크박스 기반 날씨 피처 조건부 Prophet 학습 구현 계획
사용자가 프론트엔드 UI에서 "평균 기온" 및 "강수량" 체크박스를 조작함에 따라, 백엔드가 날씨 변수를 조건부로 병합하여 시계열 학습을 수행하고 예측/백테스트 그래프를 유동적으로 리프레시하도록 아키텍처를 개편합니다.

1. 개요 및 설계
   기온/강수량 체크박스 상태 추가
   use_temp, use_rain 페이로드 실어 전송
   요청 모델 파싱 및 인자 전달
   use_temp/use_rain 여부에 따라 add_regressor 분기 학습
   Frontend: index.html
   Frontend: app.js
   Backend: main.py API
   Backend: forecaster.py
   Facebook Prophet AI 모델
   체크박스 상태 = True:
   기존대로 기온 및 강수량 데이터를 Prophet 학습 시 add_regressor를 통해 외부 설명 변수로 결합합니다.
   체크박스 상태 = False:
   기상 데이터를 제외하고, 오직 네이버 검색 트렌드 데이터(ds, y)만으로 순수 Prophet 시계열 모델링을 피팅합니다.
2. 변경 대상 파일 및 상세 설계
   [Frontend]
3. index.html
   (UI 컴포넌트 추가)
   변경 위치: 분석 단위 / 예측 기간 선택 섹션 하단 (
   L89
   )
   추가 내용: "평균 기온 반영", "강수량 반영"을 켜고 끌 수 있는 체크박스 그룹 (#use-temp, #use-rain) 추가.
4. app.js
   (API 연동)
   변경 위치 1: btn-submit 클릭 시의 비교 예측 파트 (
   L227-L232
   )
   변경 위치 2: 상세 키워드 모달 클릭 시의 단일 예측 및 백테스트 파트 (
   L665-L678
   )
   추가 내용: 각 API 요청 본문(JSON)에 use_temp 및 use_rain 체크 상태를 파라미터로 적재하여 백엔드로 전달.
   [Backend]
5. main.py
   (요청 스키마 및 라우터 매핑)
   변경 위치 1: Pydantic 요청 스키마 PredictRequest, PredictKeywordRequest 수정 (
   L102-L115
   )
   변경 위치 2: 각 엔드포인트 핸들러 (predict_trend, predict_single_keyword, evaluate_single_keyword) 수정
   추가 내용:
   요청 객체 내에 use_temp: bool = True, use_rain: bool = True 파라미터 선언.
   forecast_trend 및 evaluate_trend_accuracy 내부 코어 함수 호출 시 해당 플래그들을 인자로 전달.
6. forecaster.py
   (Prophet 결합 조건 분기 처리)
   변경 위치 1: \_build_model, \_fit_model, \_predict_periods, \_rolling_backtest 서브 루틴 함수들의 매개변수 선언 및 로직 개편.
   변경 위치 2: forecast_trend, evaluate_trend_accuracy 퍼블릭 인터페이스 API 수정.
   수정 내용:
   use_temp 및 use_rain 이 True이고 실제 과거 데이터프레임 내에 해당 칼럼이 있을 때만 Prophet에 Regressor로 동적 등록 (model.add_regressor).
   학습 및 미래 30일 데이터 병합 시에도 설정된 변수만 기상 결합 및 미래 NaN 날씨 값(작년 동기 복사)을 보간 처리하도록 효율화.
   리포트 요약의 modelUsed 문구를 사용 옵션에 따라 변경 (예: "Facebook Prophet (기온 변수 결합 모델)" 등).
7. 검증 계획
   자동화 통합 테스트
   Backend/test_api.py
   에서 use_temp, use_rain을 각각 켜고 껐을 때 호출 모델의 정상 컴파일 및 실행 완료 유무 테스트.
   수동 기능 동작 테스트
   브라우저에서 분석 사이트(http://localhost:3000)에 접속.
   기온 반영 체크 켜기 + 강수량 끄기 ➡️ 예측 실행 ➡️ 요약 카드의 사용 모델명에 (기온 변수 결합 모델) 확인.
   둘 다 끄기 ➡️ 예측 실행 ➡️ 요약 카드의 사용 모델명에 Facebook Prophet + IQR Smoothing 확인

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

## **\*\*** 간단 시작 방법 **\*\*\***

1. 원클릭 실행 (가장 편한 방법)
   프로젝트 폴더 내의

run.bat
파일을 마우스로 더블 클릭만 해주시면 백엔드/프론트엔드가 순차적으로 켜지고, 크롬 브라우저로 http://localhost:3000 주소가 즉시 팝업으로 기동됩니다.

🚀 백엔드 서버 즉시 기동 (FastAPI)
.\venv\Scripts\python.exe Backend\main.py

🚀 프론트엔드 서버 즉시 기동 (FastAPI)
새 터미널에서 1번 실행

1. python -m http.server 3000 --directory Frontend
   새 터미널에서 2번 실행 (크롬으로 바로 실행)
2. start chrome http://localhost:3000
