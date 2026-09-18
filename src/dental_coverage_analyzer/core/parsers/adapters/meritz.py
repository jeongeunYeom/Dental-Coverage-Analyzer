from dental_coverage_analyzer.models import PDFDocumentData, PageType


class MeritzAdapter:
    def apply_hints(self, document: PDFDocumentData) -> None:
        headings = {
            "간편보장분석": PageType.SUMMARY,
            "보장별 상세 내역": PageType.COVERAGE_DETAIL,
            "담보별 진단 현황": PageType.DIAGNOSIS_DETAIL,
            "담보별 진단현황": PageType.DIAGNOSIS_DETAIL,
        }
        for page in document.pages:
            for heading, page_type in headings.items():
                if heading in (page.effective_text or page.text):
                    page.page_type = page_type
                    page.parser_hints["provider_page_type"] = f"MERITZ:{heading}"
                    break

