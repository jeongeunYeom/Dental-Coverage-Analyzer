# Clean Windows release 수동 검증

Windows 10/11 64-bit clean VM에서 아래 순서로 검증한다.

1. Python이 설치되지 않았는지 확인한다.
2. 시스템 Tesseract와 `PATH` 등록이 없는지 확인한다.
3. 기존 Dental Coverage Analyzer 설치가 없는지 확인한다.
4. `DentalCoverageAnalyzer-Setup-<version>.exe`를 실행한다.
5. 시작 메뉴 바로가기로 앱을 실행한다.
6. 일반 text PDF를 분석한다.
7. OCR이 필요한 synthetic PDF를 분석해 로컬 문서 인식이 동작하는지 확인한다.
8. `.dca` 프로젝트를 저장한다.
9. 프로젝트를 다시 열어 수정값을 확인한다.
10. 회사/담당자/로고 브랜드 설정을 저장한다.
11. 상담 코멘트를 작성하고 브랜드 설정 이후에도 유지되는지 확인한다.
12. 미리보기와 PDF 보고서를 저장한다.
13. 앱을 정상 종료한다.
14. 재실행하여 설정과 최근 프로젝트를 확인한다.
15. Windows 설정에서 프로그램을 uninstall한다.
16. 사용자가 저장한 `.dca`와 `%LOCALAPPDATA%/DentalCoverageAnalyzer`가 삭제되지 않았는지 확인한다.

Portable ZIP도 공백 및 한글이 포함된 별도 경로에 풀고
`DentalCoverageAnalyzer.exe --health-check`가 `APP_OK`, `OCR_OK`로 종료되는지 확인한다.
