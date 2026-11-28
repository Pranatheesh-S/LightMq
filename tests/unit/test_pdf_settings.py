"""PDF handling preference validation and persistence."""

from PySide6.QtCore import QSettings
from PySide6.QtCore import QUrl

from browser.storage.settings import BrowserSettings
from browser.storage.session_model import SessionSnapshot


def test_pdf_viewer_preference_defaults_to_open_and_persists(tmp_path):
    store = QSettings(str(tmp_path / "browser.ini"), QSettings.Format.IniFormat)
    settings = BrowserSettings(store)

    assert settings.pdf_open_in_browser() is True

    settings.set("pdf/open_in_browser", False)
    store.sync()
    restored = BrowserSettings(
        QSettings(str(tmp_path / "browser.ini"), QSettings.Format.IniFormat)
    )
    assert restored.pdf_open_in_browser() is False

    restored.set("pdf/open_in_browser", True)
    assert BrowserSettings(
        QSettings(str(tmp_path / "browser.ini"), QSettings.Format.IniFormat)
    ).pdf_open_in_browser() is True


def test_invalid_pdf_preference_value_falls_back_to_open(tmp_path):
    store = QSettings(str(tmp_path / "browser.ini"), QSettings.Format.IniFormat)
    store.setValue("pdf/open_in_browser", "unexpected")
    assert BrowserSettings(store).pdf_open_in_browser() is True


def test_session_restores_only_existing_local_pdf_files(tmp_path):
    pdf = tmp_path / "résumé with spaces.pdf"
    pdf.write_bytes(b"%PDF-1.7\nlocal test document")
    url = QUrl.fromLocalFile(str(pdf)).toString()

    restored = SessionSnapshot.sanitize_url(url)
    assert restored == QUrl.fromLocalFile(str(pdf)).toString(QUrl.ComponentFormattingOption.FullyEncoded)

    pdf.unlink()
    assert SessionSnapshot.sanitize_url(url) is None


def test_session_rejects_non_pdf_local_files(tmp_path):
    document = tmp_path / "notes.pdf"
    document.write_text("not a PDF", encoding="utf-8")
    assert SessionSnapshot.sanitize_url(QUrl.fromLocalFile(str(document)).toString()) is None
