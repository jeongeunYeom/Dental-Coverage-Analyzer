from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from .core.pdf import PDFLoadError, analyze_pdf


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="치아보험 PDF 구조 분석기 (로컬 전용)")
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze", help="PDF의 페이지 구조를 분석합니다")
    analyze.add_argument("pdf", type=Path, help="분석할 PDF 경로")
    analyze.add_argument("--json", dest="json_path", type=Path, help="분석 JSON 저장 경로")
    analyze.add_argument("--password", help="암호화된 PDF 암호")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = analyze_pdf(args.pdf, password=args.password)
    except PDFLoadError as exc:
        print(f"분석 실패: {exc}")
        return 2

    print(f"총 페이지 수: {result.total_pages}")
    for status in ("TEXT_OK", "TEXT_PARTIAL", "TEXT_GARBLED", "IMAGE_ONLY"):
        print(f"{status}: {result.text_quality_summary.get(status, 0)}")
    pages = ", ".join(map(str, result.ocr_required_pages)) or "없음"
    print(f"OCR 필요 페이지: {pages}")
    print("페이지 유형: " + ", ".join(
        f"{name}={count}" for name, count in sorted(result.detected_page_types.items())
    ))
    print("치아 관련 후보 페이지: " + (
        ", ".join(map(str, result.dental_candidate_pages)) or "없음"
    ))
    print("보험사 후보: " + (", ".join(c.value for c in result.insurer_candidates) or "없음"))
    print("상품명 후보: " + (", ".join(c.value for c in result.product_candidates) or "없음"))
    print(f"발견된 보험계약 수: {len(result.contracts)}")
    print(f"치아보험 상품 수: {result.dental_product_count}")
    print(f"전체 치아보장 수: {len(result.aggregate_coverages)}")
    print(f"세부 치아담보 수: {len(result.dental_riders)}")
    print(f"확인 필요 항목 수: {len(result.validation_issues)}")
    print(f"Provider: {result.provider} ({result.provider_confidence.value})")
    if result.support_summary:
        summary = result.support_summary
        print(
            "OCR 처리: "
            f"시도 {summary.ocr_attempted_pages}, 성공 {summary.ocr_success_pages}, "
            f"실패/미설정 {summary.ocr_failed_pages}"
        )
        print(f"지원 수준: {summary.support_level.value}")
    if args.json_path:
        print(f"JSON 저장: {result.export_json(args.json_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
