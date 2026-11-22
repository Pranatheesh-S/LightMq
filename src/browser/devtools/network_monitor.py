"""Request-side network monitor using Qt's supported profile interceptor API."""

from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal, Qt, QTimer
from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QPushButton, QVBoxLayout, QWidget)


@dataclass(frozen=True)
class RequestRecord:
    method: str
    resource_type: str
    url: str
    first_party: str


class RequestHub(QObject):
    """One interceptor per profile; forward metadata with a queued Qt signal."""

    request_seen = Signal(object)
    _hubs: dict[int, "RequestHub"] = {}

    @classmethod
    def for_profile(cls, profile) -> "RequestHub":
        key = id(profile)
        hub = cls._hubs.get(key)
        if hub is None:
            hub = cls(profile)
            cls._hubs[key] = hub
        return hub

    def __init__(self, profile):
        super().__init__(profile)
        self.interceptor = _RequestInterceptor(self)
        profile.setUrlRequestInterceptor(self.interceptor)


class _RequestInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, hub: RequestHub):
        super().__init__(hub)
        self.hub = hub

    def interceptRequest(self, info) -> None:
        """Capture safe request metadata only; never inspect headers or bodies."""
        try:
            url = info.requestUrl().toString()
            if len(url) > 4096: url = url[:4096]
            first = info.firstPartyUrl().toString()[:2048]
            method = bytes(info.requestMethod()).decode("ascii", errors="replace")[:16]
            resource = getattr(info.resourceType(), "name", "unknown")
            self.hub.request_seen.emit(RequestRecord(method, str(resource), url, first))
        except RuntimeError:
            return


class NetworkMonitor(QWidget):
    """Bounded/filterable list of real outgoing request metadata."""

    LIMIT = 1000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hub = None
        self.records = deque(maxlen=self.LIMIT)
        self.monitoring = True
        self._render_timer = QTimer(self); self._render_timer.setSingleShot(True); self._render_timer.setInterval(150); self._render_timer.timeout.connect(self._render)
        layout = QVBoxLayout(self); controls = QHBoxLayout()
        self.toggle = QPushButton("Stop monitoring"); self.clear_button = QPushButton("Clear")
        self.filter_text = QLineEdit(); self.filter_text.setPlaceholderText("Filter URL or method")
        self.filter_type = QComboBox(); self.filter_type.addItems(["All types", "Resource", "MainFrame", "Stylesheet", "Script", "Image", "Font", "Xhr", "Fetch"])
        controls.addWidget(self.toggle); controls.addWidget(self.filter_type); controls.addWidget(self.filter_text, 1); controls.addWidget(self.clear_button)
        layout.addLayout(controls); self.count_label = QLabel("0 requests"); layout.addWidget(self.count_label)
        self.output = QListWidget(); layout.addWidget(self.output, 1)
        self.toggle.clicked.connect(self._toggle); self.clear_button.clicked.connect(self.clear)
        self.filter_text.textChanged.connect(self._render); self.filter_type.currentTextChanged.connect(self._render)

    def set_profile(self, profile) -> None:
        hub = RequestHub.for_profile(profile)
        if self.hub is not hub:
            if self.hub is not None:
                try: self.hub.request_seen.disconnect(self.add_record)
                except (RuntimeError, TypeError): pass
            self.hub = hub; hub.request_seen.connect(self.add_record, Qt.ConnectionType.QueuedConnection)

    def add_record(self, record: RequestRecord) -> None:
        if not self.monitoring: return
        self.records.append(record); self._render_timer.start()

    def _toggle(self) -> None:
        self.monitoring = not self.monitoring
        self.toggle.setText("Stop monitoring" if self.monitoring else "Start monitoring")

    def clear(self) -> None:
        self.records.clear(); self._render_timer.stop(); self._render()

    def _render(self, *_args) -> None:
        text = self.filter_text.text().casefold(); kind = self.filter_type.currentText().casefold()
        rows = [r for r in self.records if (text in r.url.casefold() or text in r.method.casefold()) and (kind == "all types" or kind == r.resource_type.casefold())]
        self.count_label.setText(f"{len(rows)} shown / {len(self.records)} captured — response status and timing unavailable through this API")
        self.output.clear()
        for record in rows:
            self.output.addItem(f"{record.method:<7} {record.resource_type:<12} {record.url}  (first party: {record.first_party})")
