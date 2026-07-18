@echo off
title BookOasis Media Server
setlocal enabledelayedexpansion

echo ====================================================
echo  BookOasis Media Server - Windows Startup Utility
echo ====================================================
echo.

cd /d "%~dp0"

:: 단일 프로세스 실행(Windows)에서 큐 처리 워커를 함께 기동
set "BOOKOASIS_ENABLE_EMBEDDED_WORKER=true"

:: 1. 필수 물리 디렉토리 생성
echo [*] 필수 디렉토리 확인 및 생성 중...
if not exist db mkdir db
if not exist covers mkdir covers
if not exist cache mkdir cache
if not exist logs mkdir logs

:: 2. 가상환경 및 Python 필수 의존성 체크
echo [*] Python 및 필수 패키지 검사 중...
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] 오류: 시스템에 Python이 설치되어 있지 않거나 PATH가 지정되지 않았습니다.
    echo     Python 3.8 이상을 먼저 설치하고 설치 프로그램에서 'Add Python to PATH'를 선택해 주세요.
    pause
    exit /b 1
)

:: 윈도우에서 다중 백그라운드 스레드를 가볍게 돌리기 위해 waitress 설치 자동화
pip show waitress >nul 2>&1
if errorlevel 1 (
    echo [*] 윈도우용 고성능 웹 서비스엔진 'waitress' 패키지를 설치합니다...
    pip install waitress
)

:: 나머지 가상환경 패키지 일괄 복원
if exist requirements.txt (
    echo [*] requirements.txt 패키지 설치 여부 점검 중...
    pip install -r requirements.txt
)

:: 3. 미디어 서버 구동 (waitress를 사용하여 5930 포트로 실행)
echo.
echo [+] BookOasis 미디어 서버 구동 성공!
echo     웹 브라우저를 열고 http://localhost:5930 에 접속해 주세요.
echo     (이 창을 닫으면 서버가 안전하게 종료됩니다.)
echo.
echo ====================================================

:: Flask를 waitress 프로덕션용 경량 엔진으로 감싸 윈도우에서 구동
python -c "from waitress import serve; from core import app; serve(app, host='0.0.0.0', port=5930, threads=12)"

pause
