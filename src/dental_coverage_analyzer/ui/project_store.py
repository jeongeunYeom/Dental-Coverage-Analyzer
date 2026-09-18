from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from dental_coverage_analyzer.core.pdf.analyzer import PDFAnalysisResult
from dental_coverage_analyzer.models import (
    AggregateCoverage, CauseType, Confidence, CustomerInfo, DentalRider,
    InsuranceContract, PDFDocumentData, PaymentUnit, SourceReference,
    ValidationIssue, ValidationSeverity,
)

from .session import AnalysisSession


SCHEMA_VERSION = 1


class ProjectError(RuntimeError):
    """사용자에게 안전한 문구로 표시할 수 있는 프로젝트 오류다."""


class FutureProjectVersionError(ProjectError):
    pass


@dataclass(slots=True)
class ProjectData:
    schema_version: int
    app_version: str
    created_at: str
    updated_at: str
    original_pdf_path: str
    customer: dict[str, Any]
    canonical_aggregates: list[dict[str, Any]]
    raw_aggregate_candidates: list[dict[str, Any]]
    contracts: list[dict[str, Any]]
    riders: list[dict[str, Any]]
    validation_issues: list[dict[str, Any]]
    comment: str
    provider: dict[str, Any]
    analysis_metadata: dict[str, Any]
    aggregate_conflict_warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class LoadedProject:
    session: AnalysisSession
    project: ProjectData
    original_pdf_missing: bool


def app_version() -> str:
    try:
        return version("dental-coverage-analyzer")
    except PackageNotFoundError:
        return "0.1.0"


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "DentalCoverageAnalyzer"
    return Path.home() / ".local" / "share" / "DentalCoverageAnalyzer"


def autosave_path() -> Path:
    return app_data_dir() / "autosave" / "recovery.dca"


def recent_projects_path() -> Path:
    return app_data_dir() / "recent_projects.json"


def _source(value: SourceReference | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {"page": value.page, "bbox": list(value.bbox) if value.bbox else None, "raw_text": value.raw_text}


def _load_source(value: dict[str, Any] | None) -> SourceReference | None:
    if not value:
        return None
    bbox = tuple(value["bbox"]) if value.get("bbox") else None
    return SourceReference(int(value["page"]), bbox, value.get("raw_text"))


def _aggregate(item: AggregateCoverage) -> dict[str, Any]:
    return {
        "raw_name": item.raw_name, "normalized_name": item.normalized_name,
        "category": item.category, "recommended_amount": item.recommended_amount,
        "enrolled_amount": item.enrolled_amount, "shortage_amount": item.shortage_amount,
        "surplus_amount": item.surplus_amount, "raw_difference": item.raw_difference,
        "normalized_shortage": item.normalized_shortage,
        "normalized_surplus": item.normalized_surplus, "reported_ratio": item.reported_ratio,
        "calculated_ratio": item.calculated_ratio, "status": item.status,
        "normalized_status": item.normalized_status, "source_pages": list(item.source_pages),
        "representative_source": _source(item.representative_source),
        "confidence": item.confidence.value, "confidence_reason": item.confidence_reason,
    }


def _load_aggregate(value: dict[str, Any]) -> AggregateCoverage:
    return AggregateCoverage(
        raw_name=str(value["raw_name"]), normalized_name=value.get("normalized_name"),
        category=value.get("category"), recommended_amount=value.get("recommended_amount"),
        enrolled_amount=value.get("enrolled_amount"), shortage_amount=value.get("shortage_amount"),
        surplus_amount=value.get("surplus_amount"), raw_difference=value.get("raw_difference"),
        normalized_shortage=value.get("normalized_shortage"),
        normalized_surplus=value.get("normalized_surplus"), reported_ratio=value.get("reported_ratio"),
        calculated_ratio=value.get("calculated_ratio"), status=value.get("status"),
        normalized_status=value.get("normalized_status", "UNKNOWN"),
        source_pages=[int(page) for page in value.get("source_pages", [])],
        representative_source=_load_source(value.get("representative_source")),
        confidence=Confidence(value.get("confidence", "LOW")),
        confidence_reason=value.get("confidence_reason", "저장된 프로젝트"),
    )


def _contract(item: InsuranceContract) -> dict[str, Any]:
    return {
        "insurer": item.insurer, "product_name": item.product_name,
        "policyholder": item.policyholder, "insured_person": item.insured_person,
        "enrollment_date": item.enrollment_date.isoformat() if item.enrollment_date else None,
        "coverage_period": item.coverage_period, "payment_period": item.payment_period,
        "payment_cycle": item.payment_cycle, "maturity": item.maturity,
        "monthly_premium": item.monthly_premium, "contract_status": item.contract_status,
        "sources": [_source(source) for source in item.sources],
        "confidence": item.confidence.value, "confidence_reason": item.confidence_reason,
    }


def _load_contract(value: dict[str, Any]) -> InsuranceContract:
    enrollment = value.get("enrollment_date")
    return InsuranceContract(
        insurer=value.get("insurer"), product_name=value.get("product_name"),
        policyholder=value.get("policyholder"), insured_person=value.get("insured_person"),
        enrollment_date=date.fromisoformat(enrollment) if enrollment else None,
        coverage_period=value.get("coverage_period"), payment_period=value.get("payment_period"),
        payment_cycle=value.get("payment_cycle"), maturity=value.get("maturity"),
        monthly_premium=value.get("monthly_premium"), contract_status=value.get("contract_status"),
        sources=[source for raw in value.get("sources", []) if (source := _load_source(raw))],
        confidence=Confidence(value.get("confidence", "LOW")),
        confidence_reason=value.get("confidence_reason", "저장된 프로젝트"),
    )


def _rider(item: DentalRider) -> dict[str, Any]:
    return {
        "raw_name": item.raw_name, "insurer": item.insurer, "product_name": item.product_name,
        "normalized_name": item.normalized_name,
        "credit_information_name": item.credit_information_name,
        "category": item.category, "subcategory": item.subcategory,
        "enrolled_amount": item.enrolled_amount, "raw_amount": item.raw_amount,
        "payment_unit": item.payment_unit.value, "payment_limit": item.payment_limit,
        "cause_type": item.cause_type.value, "source": _source(item.source),
        "confidence": item.confidence.value, "confidence_reason": item.confidence_reason,
        "raw_text": item.raw_text, "sources": [_source(source) for source in item.sources],
        "contract_identity": item.contract_identity,
    }


def _load_rider(value: dict[str, Any]) -> DentalRider:
    return DentalRider(
        raw_name=str(value["raw_name"]), insurer=value.get("insurer"),
        product_name=value.get("product_name"), normalized_name=value.get("normalized_name"),
        credit_information_name=value.get("credit_information_name"),
        category=value.get("category"), subcategory=value.get("subcategory"),
        enrolled_amount=value.get("enrolled_amount"), raw_amount=value.get("raw_amount"),
        payment_unit=PaymentUnit(value.get("payment_unit", "UNKNOWN")),
        payment_limit=value.get("payment_limit"),
        cause_type=CauseType(value.get("cause_type", "UNKNOWN")),
        source=_load_source(value.get("source")),
        confidence=Confidence(value.get("confidence", "LOW")),
        confidence_reason=value.get("confidence_reason", "저장된 프로젝트"),
        raw_text=value.get("raw_text"),
        sources=[source for raw in value.get("sources", []) if (source := _load_source(raw))],
        contract_identity=value.get("contract_identity"),
    )


def _issue(item: ValidationIssue) -> dict[str, Any]:
    return {
        "code": item.code, "severity": item.severity.value, "message": item.message,
        "page_numbers": list(item.page_numbers), "related_object_type": item.related_object_type,
        "related_object_id": item.related_object_id, "raw_values": list(item.raw_values),
    }


def _load_issue(value: dict[str, Any]) -> ValidationIssue:
    return ValidationIssue(
        str(value["code"]), ValidationSeverity(value.get("severity", "WARNING")),
        str(value.get("message", "확인 필요")),
        [int(page) for page in value.get("page_numbers", [])],
        value.get("related_object_type"), value.get("related_object_id"),
        [str(item) for item in value.get("raw_values", [])],
    )


def project_from_session(session: AnalysisSession, created_at: str | None = None) -> ProjectData:
    now = datetime.now(timezone.utc).isoformat()
    result = session.result
    document = result.document if result else None
    return ProjectData(
        SCHEMA_VERSION, app_version(), created_at or now, now, session.source_path,
        {
            "name": session.customer.name, "masked_name": session.customer.masked_name,
            "age": session.customer.age, "gender": session.customer.gender,
            "birth_date": session.customer.birth_date.isoformat() if session.customer.birth_date else None,
            "analysis_date": session.customer.analysis_date.isoformat() if session.customer.analysis_date else None,
        },
        [_aggregate(item) for item in session.aggregates],
        [_aggregate(item) for item in session.raw_aggregate_candidates],
        [_contract(item) for item in session.contracts], [_rider(item) for item in session.riders],
        [_issue(item) for item in (result.validation_issues if result else [])], session.comment,
        {
            "name": result.provider if result else "UNKNOWN",
            "confidence": (result.provider_confidence.value if result else "LOW"),
            "reason": result.provider_reason if result else "저장된 프로젝트",
        },
        {
            "file_name": document.file_name if document else Path(session.source_path).name,
            "total_pages": document.total_pages if document else 0,
            "metadata": document.metadata if document else {},
            "is_encrypted": document.is_encrypted if document else False,
        },
        list(session.aggregate_conflict_warnings),
    )


def session_from_project(project: ProjectData) -> AnalysisSession:
    customer = project.customer
    birth = customer.get("birth_date")
    analysis = customer.get("analysis_date")
    aggregates = [_load_aggregate(item) for item in project.canonical_aggregates]
    raw = [_load_aggregate(item) for item in project.raw_aggregate_candidates]
    # canonical 객체를 raw 목록에도 공유시켜 이후 수동 수정이 보고서에 그대로 반영되게 한다.
    for canonical in aggregates:
        for index, candidate in enumerate(raw):
            if (
                candidate.category == canonical.category
                and candidate.source_pages == canonical.source_pages
                and candidate.raw_name == canonical.raw_name
            ):
                raw[index] = canonical
                break
        else:
            raw.append(canonical)
    metadata = project.analysis_metadata
    document = PDFDocumentData(
        Path(project.original_pdf_path), metadata.get("file_name") or Path(project.original_pdf_path).name,
        int(metadata.get("total_pages", 0)), metadata.get("metadata", {}),
        bool(metadata.get("is_encrypted", False)), [],
    )
    issues = [_load_issue(item) for item in project.validation_issues]
    result = PDFAnalysisResult(document, {}, [], {}, [], [], [], validation_issues=issues)
    result.provider = project.provider.get("name", "UNKNOWN")
    result.provider_confidence = Confidence(project.provider.get("confidence", "LOW"))
    result.provider_reason = project.provider.get("reason", "저장된 프로젝트")
    return AnalysisSession(
        source_path=project.original_pdf_path,
        customer=CustomerInfo(
            name=customer.get("name"), masked_name=customer.get("masked_name"),
            age=customer.get("age"), gender=customer.get("gender"),
            birth_date=date.fromisoformat(birth) if birth else None,
            analysis_date=date.fromisoformat(analysis) if analysis else None,
        ),
        contracts=[_load_contract(item) for item in project.contracts], aggregates=aggregates,
        riders=[_load_rider(item) for item in project.riders], result=result,
        raw_aggregate_candidates=raw,
        aggregate_conflict_warnings=list(project.aggregate_conflict_warnings),
        comment=project.comment,
        project_created_at=project.created_at,
    )


def _parse_project(payload: dict[str, Any]) -> ProjectData:
    schema = payload.get("schema_version")
    if not isinstance(schema, int):
        raise ProjectError("프로젝트 파일을 읽을 수 없습니다.")
    if schema > SCHEMA_VERSION:
        raise FutureProjectVersionError("현재 프로그램보다 새로운 버전에서 생성된 프로젝트입니다.")
    if schema < 1:
        raise ProjectError("지원하지 않는 이전 프로젝트 형식입니다.")
    required = {
        "app_version", "created_at", "updated_at", "original_pdf_path", "customer",
        "canonical_aggregates", "contracts", "riders", "validation_issues", "comment",
        "provider", "analysis_metadata",
    }
    if not required.issubset(payload):
        raise ProjectError("프로젝트 파일을 읽을 수 없습니다.")
    payload.setdefault("raw_aggregate_candidates", payload["canonical_aggregates"])
    payload.setdefault("aggregate_conflict_warnings", [])
    return ProjectData(**{name: payload[name] for name in ProjectData.__dataclass_fields__})


def save_project(session: AnalysisSession, destination: str | Path, created_at: str | None = None, backup: bool = True) -> ProjectData:
    path = Path(destination).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    project = project_from_session(session, created_at)
    handle, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(project.to_dict(), stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        if backup and path.exists():
            shutil.copy2(path, Path(str(path) + ".bak"))
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return project


def load_project(source: str | Path) -> LoadedProject:
    path = Path(source).expanduser().resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ProjectError("프로젝트 파일을 읽을 수 없습니다.")
        project = _parse_project(payload)
        session = session_from_project(project)
    except FutureProjectVersionError:
        raise
    except ProjectError:
        raise
    except Exception as exc:
        raise ProjectError("프로젝트 파일을 읽을 수 없습니다.") from exc
    return LoadedProject(session, project, not Path(project.original_pdf_path).is_file())


def load_recent_projects() -> list[str]:
    path = recent_projects_path()
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
        return [str(item) for item in values if isinstance(item, str)][:5]
    except (OSError, ValueError, TypeError):
        return []


def remember_project(path: str | Path) -> list[str]:
    resolved = str(Path(path).expanduser().resolve())
    recent = [resolved, *(item for item in load_recent_projects() if item != resolved)][:5]
    target = recent_projects_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(recent, ensure_ascii=False, indent=2), encoding="utf-8")
    return recent


def remove_recent_project(path: str | Path) -> list[str]:
    resolved = str(Path(path).expanduser().resolve())
    recent = [item for item in load_recent_projects() if item != resolved][:5]
    target = recent_projects_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(recent, ensure_ascii=False, indent=2), encoding="utf-8")
    return recent


def delete_autosave() -> None:
    autosave_path().unlink(missing_ok=True)
