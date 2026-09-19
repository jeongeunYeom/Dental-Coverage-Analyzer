# Windows 배포 구성

## OCR bundle provenance

Windows release는 다음 고정 입력으로 만든다.

| 구성 | 고정 버전 | 공급 위치 | 무결성 검증 |
|---|---:|---|---|
| Tesseract Windows binary | `5.3.3.20231005` | Chocolatey `tesseract` package (UB Mannheim Windows build) | Chocolatey package에 선언된 upstream SHA-256 checksum을 `--require-checksums`로 강제 |
| Tesseract source license | `5.3.3` tag | `tesseract-ocr/tesseract` | 고정 Git tag/object 검증 |
| `eng.traineddata` | `tessdata_fast` tag `4.1.0` | `tesseract-ocr/tessdata_fast` | 고정 Git tag/object 검증, staging 시 SHA-256 출력 |
| `kor.traineddata` | `tessdata_fast` tag `4.1.0` | `tesseract-ocr/tessdata_fast` | 고정 Git tag/object 검증, staging 시 SHA-256 출력 |

`scripts/prepare_tesseract_windows.ps1`는 release build에서만 네트워크를 사용한다.
애플리케이션 runtime에는 다운로드 코드가 없으며, 준비된 실행 파일·DLL·언어 데이터를
`build/vendor/tesseract`에 staging한다. Chocolatey checksum이 없거나 일치하지 않으면
`--require-checksums`가 빌드를 중단한다. staging 완료 후 주요 파일의 SHA-256을 CI log에 남긴다.
버전, 공급 URL과 checksum 정책은 binary가 아닌
`packaging/tesseract_manifest.json`에 기록한다.

최종 portable/installer 내부 구조는 다음과 같다.

```text
DentalCoverageAnalyzer/
  DentalCoverageAnalyzer.exe
  tesseract/
    tesseract.exe
    *.dll
    tessdata/
      eng.traineddata
      kor.traineddata
    licenses/
      tesseract.txt
      tessdata.txt
  THIRD_PARTY_NOTICES.txt
```

번들 실행 파일은 explicit 경로와 시스템 `PATH`보다 먼저 탐색된다. `TESSDATA_PREFIX`는
OCR subprocess 환경에만 번들 `tessdata` 경로로 설정하며 부모 프로세스 환경은 변경하지 않는다.

## Release build

`pyproject.toml`의 `project.version`이 단일 버전 원본이다.
`scripts/generate_windows_metadata.py`가 PyInstaller version resource와 Inno Setup include를
생성한다. `build_exe.bat`은 테스트, OCR staging, metadata 생성, onedir build를 수행하고
`build_installer.bat`은 준비된 onedir 전체를 Inno Setup 6으로 패키징한다.

앱 아이콘은 Git에 추적되는 XML `assets/app_icon.svg`가 원본이다.
`scripts/build_icon.py`가 release build에서 multi-size `build/generated/app_icon.ico`를 생성하며,
생성된 ICO와 중간 PNG는 Git에서 추적하지 않는다.

Inno Setup의 고정 AppId는 `{7A834503-7785-43DF-90E1-9BC6600601A8}`이다. 기본 설치 위치는
64-bit Program Files이며 시작 메뉴 바로가기를 만들고 바탕화면 바로가기는 선택 사항이다.
uninstall은 설치 폴더만 제거하며 `%LOCALAPPDATA%/DentalCoverageAnalyzer` 또는 사용자가 만든
`.dca` 프로젝트를 삭제하는 지시를 포함하지 않는다.

코드 서명은 인증서가 준비되지 않은 현재 build에서 수행하지 않는다. 추후 서명 단계는
PyInstaller와 installer build 사이에 추가하며 인증서가 없는 일반 PR build를 막지 않아야 한다.
