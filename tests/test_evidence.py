from dental_coverage_analyzer.models import AggregateCoverage, Confidence, DentalRider, InsuranceContract, SourceReference
from dental_coverage_analyzer.ui.evidence import aggregate_evidence, contract_evidence, rider_evidence


def test_evidence_helpers_preserve_pages_and_source_text():
    source = SourceReference(6, raw_text="치아보철 치료비 200만 50만 150만 부족")
    aggregate = AggregateCoverage("치아보철 치료비", source_pages=[6], representative_source=source, confidence=Confidence.HIGH)
    evidence = aggregate_evidence(aggregate)
    assert evidence.pages == (6,)
    assert evidence.entries == ((6, source.raw_text),)
    assert evidence.confidence == "높음"

    contract = InsuranceContract(sources=[SourceReference(10, raw_text="보험회사 가상손해보험")])
    assert contract_evidence(contract).entries[0][0] == 10
    rider = DentalRider("컴퍼짓레진", source=SourceReference(17), raw_text="컴퍼짓레진 9만원")
    assert rider_evidence(rider).entries == ((17, "컴퍼짓레진 9만원"),)
