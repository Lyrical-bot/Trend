@echo off
chcp 65001 > nul
echo ==========================================
echo 🚀 트렌드 예측 프로젝트 원클릭 실행 스크립트
echo ==========================================

echo [1/4] 기존 사용 중인 포트(8000, 3000) 정리 중...
powershell -Command "Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess -Force -ErrorAction SilentlyContinue"
powershell -Command "Stop-Process -Id (Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue).OwningProcess -Force -ErrorAction SilentlyContinue"

echo [2/4] 가상환경 활성화 및 필요한 라이브러리 설치 검사...
powershell -Command "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process; .\venv\Scripts\Activate.ps1; pip install -r Backend/requirements.txt"

echo [3/4] 백엔드 FastAPI 서버 실행...
start powershell -NoExit -Command "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process; .\venv\Scripts\Activate.ps1; cd Backend; python main.py"

echo [4/4] 프론트엔드 로컬 웹 서버 실행 (포트 3000)...
start powershell -NoExit -Command "python -m http.server 3000 --directory Frontend"

echo ⏳ 서버 구동 대기 중 (2초)...
timeout /t 2 /nobreak > nul

echo 🌐 브라우저를 통해 웹 사이트 접속 중...
start http://localhost:3000

echo ==========================================
echo 백엔드 서버: http://localhost:8000
echo 프론트엔드 웹: http://localhost:3000
echo ==========================================
pause
