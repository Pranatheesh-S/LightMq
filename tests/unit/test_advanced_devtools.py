"""Unit coverage for bounded diagnostic data and safe CSS validation."""

import sys

from PySide6.QtWidgets import QApplication

from browser.devtools.console_panel import ConsolePanel
from browser.devtools.css_inspector import CSSInspector
from browser.devtools.network_monitor import RequestRecord
from browser.devtools.performance_panel import PerformancePanel

app = QApplication.instance() or QApplication(sys.argv)


def test_console_buffer_severity_filter_search_and_clear():
    panel = ConsolePanel()
    for index in range(panel.LIMIT + 2):
        panel.add_message("WarningMessageLevel", f"warning {index}", index, "app.js")
    assert len(panel.messages) == panel.LIMIT
    assert panel.messages[-1][0] == "warning"
    panel.severity.setCurrentText("Warning")
    panel.search.setText("warning 501")
    assert panel.output.count() == 1
    panel.clear()
    assert panel.output.count() == 0


def test_css_property_validation_and_request_record_fields():
    assert CSSInspector.SAFE_PROPERTY.fullmatch("background-color")
    assert not CSSInspector.SAFE_PROPERTY.fullmatch("color;alert(1)")
    record = RequestRecord("GET", "Script", "https://example.test/app.js", "https://example.test/")
    assert record.method == "GET" and record.resource_type == "Script"


def test_performance_panel_marks_unsupported_metrics():
    panel = PerformancePanel()
    panel._show({"ready": "complete", "duration": 42.5, "resources": 2})
    assert panel.values["Navigation duration"].text() == "42.5 ms"
    assert panel.values["First contentful paint"].text() == "—"
    assert panel.values["JS heap memory"].text() == "Unsupported"
