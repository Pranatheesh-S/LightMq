"""Native .xlsx viewer with guarded cell-value editing and safe Save As."""
from __future__ import annotations

import os
import tempfile
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.cell.cell import MergedCell
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QUrl, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QApplication,
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTabBar, QTableView, QVBoxLayout, QWidget,
)


def inspect_xlsx(path: str | Path) -> tuple[openpyxl.Workbook, list[str]]:
    """Load a bounded .xlsx and report structures openpyxl may not preserve."""
    source = Path(path)
    if source.suffix.lower() != ".xlsx" or not source.is_file():
        raise ValueError("Choose an existing .xlsx workbook.")
    if source.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("This workbook exceeds LightMq's 100 MB safety limit.")
    warnings: list[str] = []
    with zipfile.ZipFile(source) as archive:
        entries = archive.infolist()
        if len(entries) > 10_000 or sum(item.file_size for item in entries) > 500 * 1024 * 1024:
            raise ValueError("This workbook has an unsafe or unusually large ZIP package.")
        names = {item.filename for item in entries}
        if any(item.file_size > 0 and item.file_size / max(item.compress_size, 1) > 500 for item in entries):
            raise ValueError("This workbook has an unsafe compression ratio.")
        unsupported = [name for name in names if name.startswith(("xl/drawings/", "xl/externalLinks/", "xl/embeddings/", "xl/activeX/"))]
        if unsupported or any("connections" in name.lower() or "vbaProject" in name for name in names):
            warnings.append("This workbook contains drawings, connections, embedded objects, or macros. It is view-only because saving may remove unsupported content.")
    workbook = openpyxl.load_workbook(source, data_only=False, read_only=False, keep_links=False)
    if workbook.security.lockStructure:
        warnings.append("Workbook structure is protected; editing is disabled.")
    return workbook, warnings


def display_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    return str(value)


class CellEdit(QUndoCommand):
    def __init__(self, model: "WorksheetModel", row: int, column: int, before: Any, after: Any) -> None:
        super().__init__(f"Edit {model.sheet.cell(row + 1, column + 1).coordinate}")
        self.model, self.row, self.column, self.before, self.after = model, row, column, before, after

    def undo(self) -> None:
        self.model._apply(self.row, self.column, self.before)

    def redo(self) -> None:
        self.model._apply(self.row, self.column, self.after)


class WorksheetModel(QAbstractTableModel):
    """Virtualized table model for a single openpyxl worksheet."""
    dirty_changed = Signal(bool)

    def __init__(self, sheet: Any, undo_stack: QUndoStack, editable: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.sheet, self.undo_stack, self.editable = sheet, undo_stack, editable
        self.changed_cells: set[tuple[int, int]] = set()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else self.sheet.max_row

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else self.sheet.max_column

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        cell = self.sheet.cell(index.row() + 1, index.column() + 1)
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return display_value(cell.value)
        if role == Qt.ItemDataRole.BackgroundRole and (index.row(), index.column()) in self.changed_cells:
            from PySide6.QtGui import QColor
            return QColor("#fff2cc")
        if role == Qt.ItemDataRole.ToolTipRole and cell.data_type == "f":
            return f"Formula (not calculated): {cell.value}"
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Vertical:
            return str(section + 1)
        from openpyxl.utils import get_column_letter
        return get_column_letter(section + 1)

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        flags = super().flags(index)
        if not index.isValid():
            return flags
        cell = self.sheet.cell(index.row() + 1, index.column() + 1)
        merged = isinstance(cell, MergedCell)
        if self.editable and not self.sheet.protection.sheet and not merged and cell.data_type != "f":
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if role != Qt.ItemDataRole.EditRole or not index.isValid() or not (self.flags(index) & Qt.ItemFlag.ItemIsEditable):
            return False
        cell = self.sheet.cell(index.row() + 1, index.column() + 1)
        try:
            converted = self._convert(str(value), cell.value)
        except ValueError:
            return False
        if converted == cell.value and type(converted) is type(cell.value):
            return True
        self.undo_stack.push(CellEdit(self, index.row(), index.column(), cell.value, converted))
        return True

    @staticmethod
    def _convert(text: str, original: Any) -> Any:
        if text == "":
            return None
        if text.startswith("="):
            return text
        if isinstance(original, bool):
            if text.casefold() not in {"true", "false"}:
                raise ValueError("Enter true or false.")
            return text.casefold() == "true"
        if isinstance(original, datetime):
            try: return datetime.fromisoformat(text)
            except ValueError: return text
        if isinstance(original, date):
            try: return date.fromisoformat(text)
            except ValueError: return text
        if isinstance(original, int) and not isinstance(original, bool):
            try: return int(text)
            except ValueError: return text
        if isinstance(original, float):
            try: return float(text)
            except ValueError: return text
        return text

    def _apply(self, row: int, column: int, value: Any) -> None:
        cell = self.sheet.cell(row + 1, column + 1)
        if isinstance(value, str) and value.startswith("="):
            cell.value, cell.data_type = value, "s"
        else:
            cell.value = value
        self.changed_cells.add((row, column))
        self.dataChanged.emit(self.index(row, column), self.index(row, column), [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.BackgroundRole])


class SpreadsheetViewer(QWidget):
    """A browser document tab for native .xlsx viewing and limited editing."""
    titleChanged = Signal(str)
    urlChanged = Signal(QUrl)

    def __init__(self, path: str | Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.path = Path(path).resolve()
        self.url_value = QUrl.fromLocalFile(str(self.path))
        self.workbook, self.warnings = inspect_xlsx(self.path)
        self.undo_stack = QUndoStack(self)
        self.undo_stack.cleanChanged.connect(self._dirty_changed)
        self._undo_shortcuts: list[QShortcut] = []
        for sequence, callback in (("Ctrl+Z", self.undo_stack.undo), ("Ctrl+Y", self.undo_stack.redo), ("Ctrl+Shift+Z", self.undo_stack.redo)):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
            self._undo_shortcuts.append(shortcut)
        copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self)
        copy_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        copy_shortcut.activated.connect(self.copy_selection)
        self._undo_shortcuts.append(copy_shortcut)
        self.edit_mode = False
        self.dirty = False
        self._saved_clean_index = 0
        self.models: dict[str, WorksheetModel] = {}
        self._build_ui()
        self.set_mode(False)
        self._select_sheet(0)

    def url(self) -> QUrl: return self.url_value
    def title(self) -> str: return self.path.name + (" *" if self.dirty else "")
    def icon(self): return self.style().standardIcon(self.style().StandardPixmap.SP_FileIcon)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        heading = QHBoxLayout()
        self.title_label = QLabel(self.path.name)
        heading.addWidget(self.title_label); heading.addStretch()
        self.mode = QComboBox(); self.mode.addItems(["View Mode", "Edit Mode"]); self.mode.currentIndexChanged.connect(lambda value: self.set_mode(value == 1)); heading.addWidget(self.mode)
        root.addLayout(heading)
        actions = QHBoxLayout()
        for label, callback in (("Save", self.save), ("Save As", self.save_as), ("Undo", self.undo_stack.undo), ("Redo", self.undo_stack.redo)):
            button = QPushButton(label); button.clicked.connect(callback); actions.addWidget(button)
            if label == "Save": self.save_button = button
            if label == "Save As": self.save_as_button = button
        self.search = QLineEdit(); self.search.setPlaceholderText("Find in this worksheet…"); self.search.returnPressed.connect(lambda: self.find_next(1)); actions.addWidget(self.search)
        self.find_prev = QPushButton("Previous"); self.find_prev.clicked.connect(lambda: self.find_next(-1)); actions.addWidget(self.find_prev)
        self.find_next_button = QPushButton("Next"); self.find_next_button.clicked.connect(lambda: self.find_next(1)); actions.addWidget(self.find_next_button)
        root.addLayout(actions)
        cellrow = QHBoxLayout(); self.cell_ref = QLabel("A1"); self.value = QLineEdit(); self.value.setReadOnly(True); self.value.editingFinished.connect(self._commit_value); cellrow.addWidget(QLabel("Cell:")); cellrow.addWidget(self.cell_ref); cellrow.addWidget(QLabel("Value:")); cellrow.addWidget(self.value); root.addLayout(cellrow)
        self.grid = QTableView(); self.grid.setSelectionBehavior(QTableView.SelectionBehavior.SelectItems); self.grid.setEditTriggers(QTableView.EditTrigger.NoEditTriggers); self.grid.clicked.connect(self._selection_changed); root.addWidget(self.grid)
        self.sheets = QTabBar(); self.sheets.setExpanding(False)
        for name in self.workbook.sheetnames: self.sheets.addTab(name)
        self.sheets.currentChanged.connect(self._select_sheet); root.addWidget(self.sheets)
        self.status = QLabel(f"View Mode | {len(self.workbook.sheetnames)} worksheets")
        if self.warnings: self.status.setText("View Mode | " + self.warnings[0])
        elif self.formula_count(): self.status.setText("Formulas are not calculated; cached results may be stale.")
        root.addWidget(self.status)

    def formula_count(self) -> int:
        return sum(1 for sheet in self.workbook.worksheets for cell in sheet._cells.values() if cell.data_type == "f")

    def _select_sheet(self, index: int) -> None:
        if not 0 <= index < len(self.workbook.worksheets): return
        sheet = self.workbook.worksheets[index]
        model = self.models.get(sheet.title)
        if model is None:
            model = WorksheetModel(sheet, self.undo_stack, self.edit_mode, self); self.models[sheet.title] = model
        model.editable = self.edit_mode
        self.grid.setModel(model)
        self.grid.setEditTriggers(QTableView.EditTrigger.DoubleClicked | QTableView.EditTrigger.EditKeyPressed if self.edit_mode else QTableView.EditTrigger.NoEditTriggers)
        self.grid.selectionModel().currentChanged.connect(lambda *_: self._selection_changed())
        self._selection_changed()

    def set_mode(self, editing: bool) -> None:
        blocked = bool(self.warnings) or self.workbook.security.lockStructure
        self.edit_mode = editing and not blocked
        if editing and blocked:
            QMessageBox.information(self, "Edit Mode unavailable", self.warnings[0] if self.warnings else "The workbook structure is protected.")
            self.mode.setCurrentIndex(0)
        self.mode.blockSignals(True); self.mode.setCurrentIndex(1 if self.edit_mode else 0); self.mode.blockSignals(False)
        for model in self.models.values(): model.editable = self.edit_mode
        if hasattr(self, "grid"):
            self._select_sheet(self.sheets.currentIndex() if self.sheets.count() else 0)
        self.value.setReadOnly(not self.edit_mode or (self.grid.currentIndex().isValid() and not (self.grid.model().flags(self.grid.currentIndex()) & Qt.ItemFlag.ItemIsEditable)))
        sheet_protected = bool(self.workbook.worksheets[self.sheets.currentIndex()].protection.sheet)
        self.status.setText(("Edit Mode" if self.edit_mode else "View Mode") + (" | This worksheet is protected." if sheet_protected else "") + (" | Formulas are not recalculated." if self.formula_count() else ""))

    def _selection_changed(self, *_args: Any) -> None:
        index = self.grid.currentIndex()
        if not index.isValid(): return
        cell = self.grid.model().sheet.cell(index.row() + 1, index.column() + 1)
        self.cell_ref.setText(cell.coordinate); self.value.setText(display_value(cell.value))
        self.value.setReadOnly(not self.edit_mode or not (self.grid.model().flags(index) & Qt.ItemFlag.ItemIsEditable))

    def _commit_value(self) -> None:
        index = self.grid.currentIndex()
        if index.isValid() and not self.value.isReadOnly(): self.grid.model().setData(index, self.value.text())
        self._selection_changed()

    def _dirty_changed(self, clean: bool) -> None:
        self.dirty = not clean
        self.title_label.setText(self.title()); self.save_button.setEnabled(self.dirty); self.titleChanged.emit(self.title())

    def find_next(self, direction: int) -> None:
        query = self.search.text().casefold()
        if not query: return
        model = self.grid.model(); rows, columns = model.rowCount(), model.columnCount()
        start = self.grid.currentIndex().row() * max(columns, 1) + self.grid.currentIndex().column() if self.grid.currentIndex().isValid() else -1
        for offset in range(1, rows * columns + 1):
            pos = (start + direction * offset) % (rows * columns)
            row, col = divmod(pos, columns)
            if query in display_value(model.sheet.cell(row + 1, col + 1).value).casefold():
                index = model.index(row, col); self.grid.setCurrentIndex(index); self.grid.scrollTo(index); self._selection_changed(); return

    def copy_selection(self) -> None:
        """Copy the selected cell's displayed value to the system clipboard."""
        index = self.grid.currentIndex()
        if index.isValid():
            QApplication.clipboard().setText(display_value(self.grid.model().sheet.cell(index.row() + 1, index.column() + 1).value))

    def save(self) -> None:
        if not os.access(self.path, os.W_OK):
            QMessageBox.warning(self, "Workbook is read-only", "Use Save As to write an editable copy."); return
        explanation = "Saving with openpyxl can invalidate cached formula results. LightMq never recalculates formulas."
        if self.formula_count():
            explanation += "\n\nReplace the original workbook anyway? Save As is recommended."
        else:
            explanation = "Replace the original workbook with the edited copy? Save As is recommended for safety."
        if QMessageBox.question(self, "Replace original workbook?", explanation,
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self._save_to(self.path, overwrite=True)

    def save_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(self, "Save Workbook As", str(self.path.with_name(self.path.stem + " copy.xlsx")), "Excel Workbook (*.xlsx)")
        if not path: return False
        destination = Path(path).with_suffix(".xlsx")
        if self.formula_count() and QMessageBox.question(
            self, "Formula result warning",
            "LightMq does not calculate formulas. Saving with openpyxl may invalidate cached results. Continue with Save As?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return False
        if destination.exists() and QMessageBox.question(self, "Replace workbook?", f"Replace {destination.name}?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return False
        return self._save_to(destination, overwrite=True)

    def _save_to(self, destination: Path, *, overwrite: bool) -> bool:
        if self.warnings:
            QMessageBox.warning(self, "Save blocked", self.warnings[0] + " Saving is disabled to protect workbook content."); return False
        destination = destination.resolve()
        if destination.exists() and not overwrite:
            QMessageBox.warning(self, "Save blocked", "The destination already exists."); return False
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix=".lightmq-", suffix=".xlsx", dir=destination.parent, delete=False) as temp: temporary = temp.name
            self.workbook.save(temporary)
            os.replace(temporary, destination); temporary = None
            self.path = destination; self.url_value = QUrl.fromLocalFile(str(destination)); self.undo_stack.setClean(); self._saved_clean_index = self.undo_stack.index(); self.dirty = False
            self.title_label.setText(self.title()); self.save_button.setEnabled(False); self.titleChanged.emit(self.title()); self.urlChanged.emit(self.url_value)
            return True
        except (OSError, PermissionError, ValueError) as exc:
            QMessageBox.critical(self, "Save failed", f"The workbook was not saved. The original file remains unchanged.\n\n{exc}"); return False
        finally:
            if temporary:
                try: os.unlink(temporary)
                except OSError: pass

