from datetime import date
import sys

import openpyxl
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from browser.features.spreadsheets.spreadsheet_viewer import SpreadsheetViewer

app = QApplication.instance() or QApplication(sys.argv)


def workbook_file(tmp_path):
    path = tmp_path / "résumé file.xlsx"
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Employees"
    sheet["A1"] = "0012"
    sheet["B1"] = 12
    sheet["C1"] = "=B1+1"
    sheet["D1"] = date(2025, 1, 2)
    sheet["A3"] = "end"
    book.create_sheet("Second")
    book.save(path)
    return path


def test_view_mode_read_only_and_formula_read_only(tmp_path):
    viewer = SpreadsheetViewer(workbook_file(tmp_path))
    model = viewer.grid.model()
    assert not model.flags(model.index(0, 1)) & Qt.ItemFlag.ItemIsEditable
    viewer.set_mode(True)
    model = viewer.grid.model()
    assert model.flags(model.index(0, 1)) & Qt.ItemFlag.ItemIsEditable
    assert not model.flags(model.index(0, 2)) & Qt.ItemFlag.ItemIsEditable
    assert model.data(model.index(0, 2)) == "=B1+1"


def test_value_types_formula_literal_and_undo_redo(tmp_path):
    viewer = SpreadsheetViewer(workbook_file(tmp_path))
    viewer.set_mode(True)
    model = viewer.grid.model()
    assert model.setData(model.index(0, 1), "42")
    assert model.sheet["B1"].value == 42
    assert viewer.dirty
    viewer.undo_stack.undo()
    assert model.sheet["B1"].value == 12
    viewer.undo_stack.redo()
    assert model.sheet["B1"].value == 42
    assert model.setData(model.index(1, 0), "=1+2")
    assert model.sheet["A2"].value == "=1+2"
    assert model.sheet["A2"].data_type == "s"


def test_sheet_switch_and_atomic_save_as(tmp_path):
    path = workbook_file(tmp_path)
    viewer = SpreadsheetViewer(path)
    viewer.set_mode(True)
    viewer.grid.model().setData(viewer.grid.model().index(0, 1), "25")
    viewer.sheets.setCurrentIndex(1)
    viewer.grid.model().setData(viewer.grid.model().index(0, 0), "Saved on second sheet")
    viewer.sheets.setCurrentIndex(0)
    target = tmp_path / "copy.xlsx"
    assert viewer._save_to(target, overwrite=False)
    loaded = openpyxl.load_workbook(target, data_only=False)
    assert loaded["Employees"]["B1"].value == 25
    assert loaded["Employees"]["C1"].value == "=B1+1"
    assert loaded["Second"]["A1"].value == "Saved on second sheet"
    assert not viewer.dirty


def test_invalid_and_unsupported_workbooks(tmp_path):
    bad = tmp_path / "bad.xlsx"
    bad.write_text("not a workbook")
    from browser.features.spreadsheets.spreadsheet_viewer import inspect_xlsx
    with pytest.raises(Exception):
        inspect_xlsx(bad)
