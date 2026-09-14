from __future__ import annotations

from dataclasses import dataclass, field

from dental_coverage_analyzer.core.dental import DentalProductDetector
from dental_coverage_analyzer.models import (
    AggregateCoverage,
    DentalRider,
    InsuranceContract,
    PDFDocumentData,
    ValidationIssue,
    ValidationSeverity,
)

from .aggregate_parser import AggregateCoverageParser
from .contract_parser import InsuranceContractParser
from .rider_parser import DentalRiderParser
from .adapters import LotteAdapter, MeritzAdapter, SamsungAdapter
from .provider_detector import ProviderType


@dataclass(slots=True)
class ParsingResult:
    contracts: list[InsuranceContract] = field(default_factory=list)
    aggregate_coverages: list[AggregateCoverage] = field(default_factory=list)
    dental_riders: list[DentalRider] = field(default_factory=list)
    validation_issues: list[ValidationIssue] = field(default_factory=list)


class GenericParser:
    """Provider 비종속 parser들을 안전한 순서로 조합한다."""

    def __init__(self) -> None:
        self.aggregate_parser = AggregateCoverageParser()
        self.contract_parser = InsuranceContractParser()
        self.rider_parser = DentalRiderParser()
        self.product_detector = DentalProductDetector()

    def parse(self, document: PDFDocumentData, provider: ProviderType = ProviderType.GENERIC) -> ParsingResult:
        adapter = {
            ProviderType.MERITZ: MeritzAdapter(),
            ProviderType.SAMSUNG: SamsungAdapter(),
            ProviderType.LOTTE: LotteAdapter(),
        }.get(provider)
        if adapter:
            adapter.apply_hints(document)
        aggregate = self.aggregate_parser.parse(document)
        contracts = self.contract_parser.parse(document)
        riders = self.rider_parser.parse(document, contracts.items)
        issues = [*aggregate.issues, *contracts.issues, *riders.issues]
        for page in document.pages:
            if page.ocr_required and page.ocr_status != "SUCCESS":
                code = {
                    "NOT_CONFIGURED": "OCR_NOT_AVAILABLE",
                    "FAILED": "OCR_FAILED",
                }.get(page.ocr_status, "OCR_REQUIRED")
                issues.append(ValidationIssue(
                    code, ValidationSeverity.WARNING,
                    "Text Layer 품질이 낮아 로컬 OCR 또는 원본 확인이 필요합니다",
                    [page.page_number], "PDFPageData", str(page.page_number),
                    [page.text_quality, page.ocr_reason or ""],
                ))
            if page.page_type.value == "UNKNOWN" and page.dental_candidate_score > 0:
                issues.append(ValidationIssue(
                    "PAGE_TYPE_UNCERTAIN", ValidationSeverity.WARNING,
                    "치아 관련 신호가 있으나 페이지 유형을 확정하지 못했습니다",
                    [page.page_number], "PDFPageData", str(page.page_number),
                ))
        return ParsingResult(
            contracts=contracts.items,
            aggregate_coverages=aggregate.items,
            dental_riders=riders.items,
            validation_issues=issues,
        )

    def dental_contract_count(self, contracts: list[InsuranceContract]) -> int:
        return sum(self.product_detector.detect(item.product_name).is_candidate for item in contracts)
