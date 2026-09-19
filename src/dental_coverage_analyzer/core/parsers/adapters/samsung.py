from dental_coverage_analyzer.models import PDFDocumentData, PageType


class SamsungAdapter:
    def apply_hints(self, document: PDFDocumentData) -> None:
        previous_detail = False
        for page in document.pages:
            text = page.effective_text or page.text
            has_new_header = "보험회사" in text or "상품명" in text
            explicit_detail = "상품별 상세 현황" in text
            dental_content = any(word in text for word in ("치아", "치과", "발치", "충전", "스케일링"))
            if explicit_detail:
                page.page_type = PageType.PRODUCT_DETAIL
                page.parser_hints["product_section"] = "SAMSUNG_PRODUCT_DETAIL"
                previous_detail = True
            elif previous_detail and dental_content and not has_new_header:
                page.page_type = PageType.PRODUCT_DETAIL
                page.parser_hints["inherit_product_context"] = True
                page.parser_hints["product_section"] = "SAMSUNG_PRODUCT_DETAIL"
                previous_detail = True
            else:
                previous_detail = page.page_type is PageType.PRODUCT_DETAIL

