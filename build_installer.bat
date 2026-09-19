@echo off
setlocal
cd /d "%~dp0"
if not exist "dist\DentalCoverageAnalyzer\DentalCoverageAnalyzer.exe" (
  echo 먼저 build_exe.bat을 실행하세요.
  exit /b 1
)
python scripts\generate_windows_metadata.py
if errorlevel 1 exit /b 1
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo Inno Setup 6을 찾을 수 없습니다.
  exit /b 1
)
"%ISCC%" installer\DentalCoverageAnalyzer.iss
if errorlevel 1 exit /b 1
echo 설치파일 생성 완료: dist\installer
endlocal
