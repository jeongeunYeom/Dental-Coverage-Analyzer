"""개인정보 없는 가상 데이터로 디자인 확인용 sample_report.pdf를 생성한다."""
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dental_coverage_analyzer.models import (
    AggregateCoverage, CauseType, Confidence, CustomerInfo, DentalRider,
    InsuranceContract, PaymentUnit,
)
from dental_coverage_analyzer.reports import build_report_data, export_report_pdf


def main() -> None:
    customer = CustomerInfo(name="가명고객", analysis_date=date.today())
    aggregates = [
        AggregateCoverage(
            "치아보철 치료비", category="보철치료", recommended_amount=2_000_000,
            enrolled_amount=500_000, normalized_shortage=1_500_000, status="부족",
            confidence=Confidence.HIGH, source_pages=[2],
        ),
        AggregateCoverage(
            "치아보존 치료비", category="보존치료", recommended_amount=200_000,
            enrolled_amount=370_000, normalized_surplus=170_000, status="충분",
            confidence=Confidence.HIGH, source_pages=[2],
        ),
    ]
    contracts = [InsuranceContract(
        insurer="가상손해보험", product_name="(무)가상 든든 치아보험",
        coverage_period="2025-01-01 ~ 2060-01-01", monthly_premium=17_610,
    )]
    riders = [
        DentalRider("컴퍼짓레진", category="보존치료", enrolled_amount=90_000, cause_type=CauseType.DISEASE, payment_unit=PaymentUnit.PER_TOOTH),
        DentalRider("간접치아충전", category="보존치료", enrolled_amount=190_000, cause_type=CauseType.DISEASE, payment_unit=PaymentUnit.PER_TOOTH),
        DentalRider("파노라마 사진촬영", category="검사/영상", enrolled_amount=10_000, cause_type=CauseType.UNKNOWN, payment_unit=PaymentUnit.PER_OCCURRENCE),
        DentalRider("스케일링", category="예방", enrolled_amount=10_000, cause_type=CauseType.DISEASE, payment_unit=PaymentUnit.PER_YEAR),
    ]
    output = export_report_pdf(build_report_data(customer, aggregates, contracts, riders), ROOT / "sample_report.pdf")
    print(f"생성 완료: {output}")


if __name__ == "__main__":
    main()
