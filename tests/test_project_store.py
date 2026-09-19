import json
from pathlib import Path

import pytest

from dental_coverage_analyzer.core.pdf.analyzer import PDFAnalysisResult
from dental_coverage_analyzer.models import (
    AggregateCoverage, Confidence, CustomerInfo, DentalRider, InsuranceContract,
    PDFDocumentData, SourceReference, ValidationIssue, ValidationSeverity,
)
from dental_coverage_analyzer.reports import build_report_data, render_report_html
from dental_coverage_analyzer.ui.project_store import (
    FutureProjectVersionError, ProjectError, SCHEMA_VERSION, autosave_path,
    load_project, load_recent_projects, remember_project, save_project,
)
from dental_coverage_analyzer.ui.session import AnalysisSession


def session_fixture(tmp_path: Path) -> AnalysisSession:
    pdf = tmp_path / "original.pdf"
    pdf.write_bytes(b"synthetic")
    aggregate = AggregateCoverage(
        "치아보철치료비", normalized_name="치아보철치료비", category="보철치료",
        recommended_amount=2_000_000, enrolled_amount=700_000,
        shortage_amount=1_300_000, normalized_shortage=1_300_000, status="부족",
        source_pages=[6], representative_source=SourceReference(6, (1, 2, 3, 4), "원문"),
        confidence=Confidence.HIGH,
    )
    contract = InsuranceContract(
        insurer="수정손해보험", product_name="수정 치아보험",
        sources=[SourceReference(10, raw_text="계약 원문")], confidence=Confidence.HIGH,
    )
    kept_rider = DentalRider(
        "사용자 추가 Rider", category="보존치료", enrolled_amount=90_000,
        sources=[SourceReference(12, raw_text="담보 원문")], confidence=Confidence.MEDIUM,
    )
    document = PDFDocumentData(pdf, pdf.name, 22, {"title": "합성 문서"}, False, [])
    issue = ValidationIssue(
        "AGGREGATE_AMOUNT_CONFLICT", ValidationSeverity.WARNING, "원본 충돌",
        [6, 19], "AggregateCoverage", "치아보철치료비", ["raw 1", "raw 2"],
    )
    result = PDFAnalysisResult(document, {}, [], {}, [], [], [], validation_issues=[issue])
    result.provider = "MERITZ"; result.provider_confidence = Confidence.HIGH
    return AnalysisSession(
        source_path=str(pdf), customer=CustomerInfo(name="가명고객"),
        contracts=[contract], aggregates=[aggregate], riders=[kept_rider], result=result,
        raw_aggregate_candidates=[aggregate], comment="임플란트 보장 내용을 다시 확인하세요.",
        is_dirty=True,
    )


def test_manual_edits_comment_contract_and_provenance_round_trip(tmp_path):
    session = session_fixture(tmp_path)
    destination = tmp_path / "가명고객_치아보험분석.dca"
    saved = save_project(session, destination)
    loaded = load_project(destination)

    assert saved.schema_version == SCHEMA_VERSION == 1
    assert saved.created_at and saved.updated_at and saved.app_version
    assert loaded.session.customer.name == "가명고객"
    assert loaded.session.aggregates[0].enrolled_amount == 700_000
    assert loaded.session.comment == "임플란트 보장 내용을 다시 확인하세요."
    assert loaded.session.contracts[0].insurer == "수정손해보험"
    assert loaded.session.contracts[0].product_name == "수정 치아보험"
    assert loaded.session.aggregates[0].representative_source.bbox == (1, 2, 3, 4)
    assert loaded.session.result.validation_issues[0].raw_values == ["raw 1", "raw 2"]
    assert loaded.session.result.provider == "MERITZ"
    assert loaded.session.is_dirty is False


def test_session_dirty_state_is_explicit_and_save_data_does_not_clear_it(tmp_path):
    session = session_fixture(tmp_path)
    session.is_dirty = False
    session.mark_dirty()
    assert session.is_dirty is True
    save_project(session, tmp_path / "dirty.dca")
    assert session.is_dirty is True  # GUI가 성공 확인 후에만 clean으로 전환한다.


def test_rider_add_delete_result_is_preserved(tmp_path):
    session = session_fixture(tmp_path)
    session.riders.append(DentalRider("삭제할 Rider"))
    session.riders = [item for item in session.riders if item.raw_name != "삭제할 Rider"]
    destination = tmp_path / "riders.dca"
    save_project(session, destination)
    loaded = load_project(destination).session
    assert [item.raw_name for item in loaded.riders] == ["사용자 추가 Rider"]


def test_missing_original_pdf_does_not_block_project_or_report(tmp_path):
    session = session_fixture(tmp_path)
    destination = tmp_path / "missing-pdf.dca"
    save_project(session, destination)
    Path(session.source_path).unlink()
    loaded = load_project(destination)
    assert loaded.original_pdf_missing is True
    assert loaded.session.original_pdf_available is False
    report = build_report_data(
        loaded.session.customer, loaded.session.aggregates,
        loaded.session.contracts, loaded.session.riders,
        loaded.session.result.validation_issues, loaded.session.comment,
    )
    assert "가명고객" in render_report_html(report)


def test_schema_version_and_corrupted_project_are_safe(tmp_path):
    session = session_fixture(tmp_path)
    destination = tmp_path / "schema.dca"
    save_project(session, destination)
    assert load_project(destination).project.schema_version == 1

    payload = json.loads(destination.read_text(encoding="utf-8"))
    payload["schema_version"] = SCHEMA_VERSION + 1
    destination.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(FutureProjectVersionError, match="새로운 버전"):
        load_project(destination)

    destination.write_text("{ broken json", encoding="utf-8")
    with pytest.raises(ProjectError, match="읽을 수 없습니다"):
        load_project(destination)


def test_atomic_overwrite_keeps_one_backup(tmp_path):
    session = session_fixture(tmp_path)
    destination = tmp_path / "atomic.dca"
    save_project(session, destination)
    original = destination.read_text(encoding="utf-8")
    session.comment = "두 번째 저장"
    save_project(session, destination)
    assert Path(str(destination) + ".bak").read_text(encoding="utf-8") == original
    assert load_project(destination).session.comment == "두 번째 저장"
    assert not list(tmp_path.glob("*.tmp"))


def test_autosave_and_recent_paths_are_local_and_recent_is_limited(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    assert autosave_path().parent == tmp_path / "LocalAppData" / "DentalCoverageAnalyzer" / "autosave"
    for index in range(7):
        remember_project(tmp_path / f"project-{index}.dca")
    recent = load_recent_projects()
    assert len(recent) == 5
    assert recent[0].endswith("project-6.dca")
