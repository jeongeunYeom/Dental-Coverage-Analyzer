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

    def parse(self, document: PDFDocumentData) -> ParsingResult:
        aggregate = self.aggregate_parser.parse(document)
        contracts = self.contract_parser.parse(document)
        riders = self.rider_parser.parse(document, contracts.items)
        issues = [*aggregate.issues, *contracts.issues, *riders.issues]
        for page in document.pages:
            if page.ocr_required:
                issues.append(ValidationIssue(
                    "OCR_REQUIRED", ValidationSeverity.WARNING,
                    "Text Layer 품질이 낮아 로컬 OCR 또는 원본 확인이 필요합니다",
                    [page.page_number], "PDFPageData", str(page.page_number),
                    [page.text_quality],
                ))
        return ParsingResult(
            contracts=contracts.items,
            aggregate_coverages=aggregate.items,
            dental_riders=riders.items,
            validation_issues=issues,
        )

    def dental_contract_count(self, contracts: list[InsuranceContract]) -> int:
        return sum(self.product_detector.detect(item.product_name).is_candidate for item in contracts)

