# Dental Coverage Analyzer

보험 보장분석 PDF에서 확인 가능한 치아 관련 정보만 로컬에서 추출하는 Windows 애플리케이션입니다.
현재 1단계 기반 구현에는 데이터 모델, 한국식 금액 파서, Text Layer 품질 분석기와 합성 fixture가 포함됩니다.

```bash
python -m pip install -e '.[dev]'
pytest
```

개발 원칙과 후속 단계는 [`docs/architecture.md`](docs/architecture.md)를 참고하세요.
