# 치아보험 보장분석표 생성기

보험 보장분석 PDF에서 확인 가능한 치아 관련 정보만 **내 PC에서** 분석하고,
사용자가 결과를 수정한 뒤 새로운 A4 치아보험 보장분석표를 PDF로 저장하는 Windows 프로그램입니다.
원본 PDF와 개인정보는 외부 서버로 전송되지 않습니다.

## Windows 실행파일 받기

1. GitHub 저장소의 **Actions** 탭을 엽니다.
2. 최신 `Build Windows MVP` 실행 결과를 선택합니다.
3. Artifacts에서 **DentalCoverageAnalyzer-Windows**를 다운로드합니다.
4. ZIP 압축을 풀고 `DentalCoverageAnalyzer.exe`를 더블클릭합니다.

기본 배포는 안정성을 위한 `onedir` 방식입니다. EXE만 다른 위치로 옮기지 말고
압축을 푼 폴더 전체를 함께 보관하세요.

## 사용 방법

1. 첫 화면에 보험 보장분석 PDF를 끌어놓거나 **PDF 선택**을 누릅니다.
2. **분석 시작**을 누르고 Text Layer/OCR/담보 분석이 끝날 때까지 기다립니다.
3. `전체 요약`, `치아보험 상품`, `세부 치아담보`, `확인 필요`, `원본 정보` 탭을 확인합니다.
4. 잘못되거나 누락된 보험사, 상품명, 담보명, 금액, 상태, 카테고리, 질병/상해,
   지급단위를 표에서 직접 수정합니다. Aggregate/Rider는 추가하거나 삭제할 수 있습니다.
5. 고객명과 필요한 상담 코멘트를 입력하고 **보고서 미리보기**로 최종 내용을 확인합니다.
6. **PDF 저장**을 눌러 `치아보험 보장분석표.pdf`를 저장합니다.

## 분석 프로젝트 저장과 다시 열기

분석 결과를 수정한 뒤 **파일 → 프로젝트 저장**(`Ctrl+S`)으로 `.dca` 프로젝트를
저장할 수 있습니다. **프로젝트 열기**(`Ctrl+O`)를 사용하면 PDF를 다시 분석하지 않고
고객명, 수정한 보장·계약·담보, 상담 코멘트와 확인 필요 정보를 그대로 복원합니다.
**다른 이름으로 저장**은 `Ctrl+Shift+S`입니다.

프로젝트는 JSON 기반이지만 사용자는 내부 내용을 직접 편집할 필요가 없습니다. 원본 PDF를
복사하지 않고 경로만 보관하므로 PDF가 이동되거나 삭제되어도 저장된 분석 결과와 보고서
출력은 계속 사용할 수 있고, 원본 PDF 열기만 제한됩니다. 작업 중 변경사항은 30초 간격으로
`%LOCALAPPDATA%\DentalCoverageAnalyzer\autosave`에 로컬 자동 저장되며, 비정상 종료 후
다음 실행 때 복구 여부를 묻습니다. 최근 프로젝트에는 최대 5개의 파일 경로만 기록합니다.

원본 PDF는 변경되지 않으며 수동 수정은 `.dca` 프로젝트에 별도로 저장됩니다.
세부 치아담보는 지급단위가 다를 수 있으므로 총액으로 합산하지 않습니다.
상담 코멘트는 입력한 줄바꿈을 유지해 미리보기와 PDF 마지막 페이지에 표시되며,
입력하지 않으면 코멘트 영역을 만들지 않습니다. 확인된 치아보험 상품이 없으면
보고서의 `가입된 치아보험` 영역에는 `없음`만 표시합니다.

## OCR 제한

Text Layer가 깨졌거나 이미지뿐인 페이지만 Tesseract 로컬 OCR을 시도합니다. Tesseract는
번들 경로, 명시 경로, 시스템 `PATH` 순으로 찾고 인터넷에서 자동 다운로드하지 않습니다.
현재 Actions MVP는 Tesseract 전체 binary를 강제 번들하지 않으므로 사용할 수 없는 PC에서는
**“OCR을 사용할 수 없어 일부 페이지는 수동 확인이 필요합니다.”**라고 안내한 뒤 분석을 계속합니다.
이 경우 `확인 필요`와 `원본 정보`를 보고 결과를 직접 보정할 수 있습니다.

## 현재 지원 범위

* Generic PDF 분석
* MERITZ / SAMSUNG / LOTTE 문서 신호 및 adapter hint
* 전체 치아보장, 보험계약, 상품별 치아담보 추출
* Text Layer와 OCR provenance 및 confidence 확인
* 결과 수동 수정, Aggregate/Rider 추가·삭제
* HTML 미리보기 및 PySide6 QPdfWriter/QPainter 기반 A4 PDF 저장
* Local debug JSON 저장

고급 bbox 하이라이트 PDF Viewer, 여러 PDF 일괄 처리, 자동 업데이트 및 보험 추천 기능은 아직 제공하지 않습니다.

## Debug JSON

분석 결과 화면의 **Debug JSON 저장** 버튼을 누르면 provider, OCR 상태, 원본/effective text,
보험계약, Aggregate, Rider 및 ValidationIssue를 로컬 JSON으로 저장할 수 있습니다.
개인정보가 포함될 수 있으므로 파일을 외부에 공유할 때 주의하세요.

## 개발 실행

Python 3.11 환경에서 다음 명령을 사용합니다.

```bash
python -m pip install -e '.[build]'
python -m pytest -q
python -m dental_coverage_analyzer gui
```

CLI 분석도 유지됩니다.

```bash
python -m dental_coverage_analyzer analyze sample.pdf --json analysis_debug.json
```

Windows에서 직접 빌드하려면 `build_exe.bat`를 실행합니다. 결과는
`dist\DentalCoverageAnalyzer\DentalCoverageAnalyzer.exe`에 생성됩니다.

## 보고서 디자인 확인

최종 PDF는 HTML 인쇄가 아니라 Qt의 벡터 드로잉으로 생성합니다. 동일 카테고리의
Aggregate가 충돌하면 원본과 ValidationIssue는 유지하되, 보고서에는 confidence·완전성·
논리 일관성·출처 근거 순으로 고른 대표 카드 하나만 표시합니다. 계약이나 세부 담보가
없으면 빈 전용 페이지를 만들지 않습니다.

개인정보가 없는 가상 데이터로 디자인을 확인하려면 다음 명령을 실행합니다.

```bash
python scripts/generate_sample_report.py
```

저장소 루트에 `sample_report.pdf`가 생성됩니다.

## 브랜드 설정과 원본 근거 확인

- **설정 → 보고서/브랜드 설정**에서 회사명, 담당자, 연락처, 이메일, 로고, 대표 색상과 보고서 안내문을 설정할 수 있습니다.
- 선택한 PNG/JPG 로고는 사용자 로컬 앱 데이터의 `DentalCoverageAnalyzer/branding` 폴더로 복사되어 원본 이미지가 이동되어도 유지됩니다.
- 브랜드 설정은 고객별 `.dca` 프로젝트와 분리된 사용자 전역 설정입니다. 예전에 저장한 프로젝트도 현재 브랜드 설정으로 보고서를 출력합니다.
- 분석 결과에서 **원본 근거 보기**를 누르면 출처 페이지, 원문과 분석 신뢰도를 확인할 수 있습니다. 원본 PDF가 없어도 저장된 근거는 계속 표시됩니다.
- 진단 데이터는 **도구 → 고급 기능 → 진단 데이터 저장**에서 저장할 수 있습니다.
- 분석, 자동복구 및 브랜드 설정은 모두 이 PC에서만 처리되며 외부 서버로 전송되지 않습니다.

## Windows 설치판과 Portable 배포

지원 범위는 Windows 10/11 64-bit입니다. GitHub Actions artifact에는 두 배포물이 생성됩니다.

- **DentalCoverageAnalyzer-Windows-Installer**: Setup.exe를 실행한 뒤 시작 메뉴에서 프로그램을 실행합니다.
- **DentalCoverageAnalyzer-Windows-Portable**: ZIP을 원하는 폴더에 풀고 폴더 구조를 유지한 채 `DentalCoverageAnalyzer.exe`를 실행합니다.

두 방식 모두 Python과 Tesseract를 별도로 설치하거나 PATH를 설정할 필요가 없습니다. OCR 실행 파일,
필수 DLL, `kor`/`eng` 언어 데이터는 빌드 시 포함되며 실행 중 인터넷 다운로드는 하지 않습니다.
설치 제거는 프로그램 파일만 제거하고 `%LOCALAPPDATA%/DentalCoverageAnalyzer`의 사용자 설정과
사용자가 저장한 `.dca` 프로젝트는 삭제하지 않습니다.

배포 상태 확인은 명령 프롬프트에서 `DentalCoverageAnalyzer.exe --health-check`로 실행할 수 있습니다.
정상 배포는 `APP_OK`와 `OCR_OK`를 출력합니다. 코드 서명되지 않은 개발용 build는 SmartScreen 경고가
표시될 수 있으며, Windows 보안 기능을 끄지 말고 게시자와 다운로드 출처를 확인해야 합니다.
