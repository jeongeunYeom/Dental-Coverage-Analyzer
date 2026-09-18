from dental_coverage_analyzer.models import PDFDocumentData


class LotteAdapter:
    def apply_hints(self, document: PDFDocumentData) -> None:
        for page in document.pages:
            if page.text_quality in {"TEXT_GARBLED", "IMAGE_ONLY"}:
                page.parser_hints["lotte_ocr_required"] = True

