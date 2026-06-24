# 🤖 AI Agent & Developer Instructions

이 문서는 이 프로젝트를 처음 접하는 AI 에이전트와 새로운 개발자를 위한 가이드라인입니다. 코드를 수정하거나 기능을 추가하기 전에 반드시 읽어주세요.

## 1. 프로젝트 개요
이 프로젝트는 **네이버 데이터랩 트렌드 API**를 활용하여 특정 키워드의 과거 검색량 추이를 가져오고, 이를 바탕으로 **시계열 예측(Time-Series Forecasting)** 을 수행하여 미래 트렌드를 제공하는 FastAPI 기반의 백엔드 서비스입니다.

## 2. 기술 스택 (Tech Stack)
* **Backend**: Python 3, FastAPI, Uvicorn (서버 구동)
* **API 호출**: `httpx` (네이버 API 비동기 호출)
* **데이터 분석 및 예측**: `pandas`, `numpy`, `statsmodels` (Holt-Winters 지수평활법), `scikit-learn` (다항 회귀 Fallback 모델)
* **환경 변수 관리**: `python-dotenv` (`.env` 파일)

## 3. 핵심 파일 구조 및 역할
* `main.py`: FastAPI 앱 설정, 라우팅 (`/api/predict`), CORS 설정, 정적(Static) 파일 서빙
* `naver_api.py`: 네이버 통합 검색어 트렌드 API 비동기 통신 로직. `.env`에서 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`를 읽어옵니다.
* `forecaster.py`: 시계열 예측 모델 로직 (`forecast_trend` 함수). 데이터 개수에 따라 Holt-Winters 모델 또는 다항 회귀 모델을 유동적으로 선택합니다.
* `static/`: 프론트엔드 HTML, CSS, JS 파일이 저장되는 곳입니다. `main.py`에 의해 서빙됩니다.

## 4. 로컬 환경 설정 (Setup Instructions)
1. **가상 환경 생성**: `python -m venv venv`
2. **패키지 설치**: `pip install -r requirements.txt` (또는 `.\venv\Scripts\python.exe -m pip install -r requirements.txt`)
3. **환경 변수 파일 생성**: 최상위 폴더에 `.env` 파일을 만들고 아래 내용을 작성하세요.
   ```env
   NAVER_CLIENT_ID=발급받은_아이디
   NAVER_CLIENT_SECRET=발급받은_시크릿
   NAVER_AD_LICENSE=발급받은_검색광고_액세스라이선스
   NAVER_AD_SECRET=발급받은_검색광고_비밀키
   NAVER_AD_CUSTOMER_ID=커스터머_ID_숫자
   ```
4. **서버 실행**: `uvicorn main:app --reload` (기본 포트: 8000)

## 5. ⚠️ AI 에이전트 및 개발자 주의사항 (Critical Caveats)
1. **보안 (Security)**: `.env` 파일과 `venv/` 폴더, `__pycache__/`는 절대 깃허브에 커밋하지 마세요. (이미 `.gitignore`에 설정되어 있습니다.)
2. **예측 모델 한계 (Forecasting Limits)**: 
   * `statsmodels`의 Holt-Winters 모델을 사용하려면 **최소 14개 이상의 데이터 포인트**가 필요합니다.
   * 데이터가 너무 적으면 `forecaster.py` 내부에서 자동으로 1차/2차 다항 회귀(Polynomial Regression)로 폴백(Fallback)되도록 설계되어 있습니다. 이 로직을 임의로 제거하지 마세요.
3. **비동기 처리 (Async)**: 네이버 API 호출 시 `httpx.AsyncClient`를 사용하여 비동기로 통신하고 있습니다. 블로킹 코드(예: `requests`)를 추가할 경우 성능이 저하될 수 있으니 주의하세요.
4. **윈도우 실행 정책 (Windows Policy)**: 윈도우 환경에서 `venv` 활성화 시 보안 오류가 발생할 수 있습니다. 에이전트가 테스트 스크립트를 실행할 때는 가상 환경을 직접 활성화하는 대신 `.\venv\Scripts\python.exe` 처럼 절대/상대 경로로 파이썬을 직접 호출하는 방식이 가장 안전합니다.
5. **프론트엔드 연동**: `main.py`는 루트 경로(`/`)에서 `static/index.html`을 반환하도록 마운트되어 있습니다. 프론트엔드 작업 시 `static/` 폴더 내부에 작업하세요.
