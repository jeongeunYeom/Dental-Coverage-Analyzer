# Dental Coverage Analyzer

보험 보장분석 PDF에서 확인 가능한 치아 관련 정보만 로컬에서 추출하는 Windows 애플리케이션입니다.
현재 1단계 기반 구현에는 데이터 모델, 한국식 금액 파서, Text Layer 품질 분석기와 합성 fixture가 포함됩니다.

```bash
python -m pip install -e '.[dev]'
pytest
```

PDF Parsing Foundation은 원본 텍스트와 word/block 좌표, Text Layer 품질,
페이지 유형, 보험사·상품명 후보와 치아 관련 후보 페이지를 구조화합니다.

```bash
python -m dental_coverage_analyzer analyze sample.pdf --json analysis_debug.json
```

OCR 필요 여부는 판정하지만 현재 OCR adapter는 `NOT_CONFIGURED`를 안전하게
반환합니다. 원본 PDF와 debug JSON은 외부로 전송되지 않습니다.

개발 원칙과 후속 단계는 [`docs/architecture.md`](docs/architecture.md)를 참고하세요.
