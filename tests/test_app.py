from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_app_loads_with_no_files_and_no_errors():
    at = AppTest.from_file(APP).run(timeout=60)
    assert not at.exception
    assert at.title[0].value == "Invoice Intake"
