import sys

import openpyxl
from PySide6.QtWidgets import QApplication

from browser.features.spreadsheets.spreadsheet_viewer import SpreadsheetViewer
from browser.ui.main_window import MainWindow

app = QApplication.instance() or QApplication(sys.argv)


def test_excel_document_is_a_shared_browser_tab(tmp_path):
    path = tmp_path / "data.xlsx"
    book = openpyxl.Workbook()
    book.active["A1"] = "kept"
    book.save(path)
    window = MainWindow(initial_url="about:blank", is_private=True)
    before = window.tab_manager.count()
    viewer = SpreadsheetViewer(path)
    window.tab_manager.create_document_tab(viewer, viewer.url(), viewer.title(), activate=True)
    assert window.tab_manager.count() == before + 1
    assert window.tab_manager.current_view() is viewer
    assert window.stacked_widget.currentWidget() is viewer
    assert window.tab_bar._tab_bar.tabText(window.tab_manager.current_index()).startswith("data.xlsx")
    assert window.action_back.isEnabled() is False
    assert window.tab_manager.group_manager.group_for_tab(window.tab_manager.tab_id_for(viewer)) is None
