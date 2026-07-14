import importlib


def test_pdf_modules_import_without_manual_sys_path_hacks() -> None:
    module = importlib.import_module("pdf_to_excel_ai.pdf_processor")
    assert module is not None

    gemini_module = importlib.import_module("pdf_to_excel_ai.gemini_client")
    assert gemini_module is not None
