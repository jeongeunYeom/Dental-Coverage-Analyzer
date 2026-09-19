@echo off
setlocal
cd /d "%~dp0"

echo [1/7] Python 환경 확인
where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.11을 찾을 수 없습니다. Python을 설치한 뒤 다시 실행하세요.
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo 가상환경 .venv를 생성합니다.
  python -m venv .venv
  if errorlevel 1 exit /b 1
)
call .venv\Scripts\activate.bat

echo [2/7] 빌드 의존성 설치
python -m pip install --upgrade pip
python -m pip install -e ".[build]"
if errorlevel 1 (
  echo 의존성 설치에 실패했습니다. 인터넷 연결과 Python 버전을 확인하세요.
  exit /b 1
)

echo [3/7] 앱 아이콘 생성
python scripts\build_icon.py
if errorlevel 1 exit /b 1

echo [4/7] 테스트 실행
python -m pytest -q
if errorlevel 1 exit /b 1

if exist "dist" rmdir /s /q "dist"
if exist "build\DentalCoverageAnalyzer" rmdir /s /q "build\DentalCoverageAnalyzer"

echo [5/7] 번들 OCR 준비
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\prepare_tesseract_windows.ps1
if errorlevel 1 exit /b 1

echo [6/7] Windows 메타데이터 생성
python scripts\generate_windows_metadata.py
if errorlevel 1 exit /b 1

echo [7/7] Windows onedir 실행파일 생성
python -m PyInstaller --noconfirm --clean DentalCoverageAnalyzer.spec
if errorlevel 1 exit /b 1

echo.
echo 빌드 완료: dist\DentalCoverageAnalyzer\DentalCoverageAnalyzer.exe
endlocal
