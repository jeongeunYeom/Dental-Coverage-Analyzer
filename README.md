# Dental Coverage Analyzer

보험 보장분석 PDF에서 확인 가능한 치아 관련 정보만 로컬에서 추출하는 Windows 애플리케이션입니다.
현재 구현은 PDF Text Layer와 좌표를 추출하고 필요한 페이지만 로컬 OCR한 뒤,
보험계약·전체 치아보장·상품별 담보와 검토 항목을 생성합니다.

```bash
python -m pip install -e '.[dev]'
pytest
```

PDF Parsing Foundation은 원본 텍스트와 word/block 좌표, Text Layer 품질,
페이지 유형, 보험사·상품명 후보와 치아 관련 후보 페이지를 구조화합니다.

```bash
python -m dental_coverage_analyzer analyze sample.pdf --json analysis_debug.json
```

## Local OCR

기본 backend는 별도 Python AI framework가 아닌 Tesseract CLI입니다. 실행 파일은
다음 순서로 찾으며 runtime 다운로드를 수행하지 않습니다.

1. 패키지 또는 PyInstaller bundle의 `resources/tesseract/`
2. `TesseractOCREngine(executable=...)`으로 지정한 경로
3. 시스템 `PATH`

한국어와 영어 OCR에는 `kor`, `eng` traineddata가 필요합니다. 실행 파일이나 언어
데이터가 없으면 `NOT_CONFIGURED`, 실행 오류는 `FAILED`로 기록되고 분석은 중단되지
않습니다. 원본 Text Layer, OCR text, 최종 effective text와 provenance는 각각
보존됩니다. Text Layer가 정상인 페이지는 OCR하지 않습니다.

구조화된 페이지는 Generic Parsing Engine을 거쳐 보험계약, 전체 치아보장 집계,
상품별 치아담보와 확인 필요 항목으로 변환됩니다. Parser는 명시적인 label,
table header 및 bbox 관계가 있는 값만 확정하고, 반복 집계금액을 합산하지 않습니다.

현재 MERITZ, SAMSUNG, LOTTE provider를 PDF 내부 신호로 score 기반 탐지합니다.
Adapter는 페이지 유형·연속 상품 상세·OCR 필요 hint만 보완하며 Generic Parser를
대체하거나 누락된 보험정보를 생성하지 않습니다. JSON에는 provider 판정, 페이지별
OCR 상태와 provenance, row reconstruction 요약 및 parser support summary가 포함됩니다.

아직 구현하지 않은 기능은 GUI, 실제 Windows용 Tesseract resource bundle,
PDF 원본 확인 화면, 최종 상담 보고서와 EXE 패키징입니다.

개발 원칙과 후속 단계는 [`docs/architecture.md`](docs/architecture.md)를 참고하세요.
