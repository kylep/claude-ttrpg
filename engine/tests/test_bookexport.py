from weasyprint import HTML


def test_weasyprint_renders_pdf_bytes():
    pdf = HTML(string="<h1>hello</h1>").write_pdf()
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")
