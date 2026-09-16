from dental_coverage_analyzer.core.pdf.page_renderer import render_page_png


class Rect:
    width = 1000
    height = 1000


class Pixmap:
    width = 100
    height = 200

    def tobytes(self, kind):
        assert kind == "png"
        return b"png"


class Page:
    rect = Rect()

    def __init__(self):
        self.dpi = None

    def get_pixmap(self, *, dpi, alpha):
        assert alpha is False
        self.dpi = dpi
        return Pixmap()


def test_renderer_caps_large_page_memory_by_reducing_dpi():
    page = Page()
    rendered = render_page_png(page, dpi=300, max_pixels=1_000_000)
    assert page.dpi < 300
    assert rendered.png_bytes == b"png"
    assert rendered.width == 100 and rendered.height == 200
