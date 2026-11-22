"""On-demand page navigation and resource timing diagnostics."""

from PySide6.QtWidgets import QFormLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class PerformancePanel(QWidget):
    """Show only values reported by the page Performance APIs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.page = None
        layout = QVBoxLayout(self); self.refresh_button = QPushButton("Refresh Metrics")
        self.form = QFormLayout(); layout.addLayout(self.form); layout.addWidget(self.refresh_button); layout.addStretch()
        self.refresh_button.clicked.connect(self.refresh)
        self.values = {key: QLabel("—") for key in ("Document ready state", "Navigation duration", "DOM content loaded", "Load event", "First paint", "First contentful paint", "Resources", "Transferred resource bytes", "JS heap memory")}
        for key, widget in self.values.items(): self.form.addRow(key, widget)

    def set_page(self, page) -> None:
        if self.page is not None:
            try: self.page.loadFinished.disconnect(self._on_load_finished)
            except (RuntimeError, TypeError): pass
        self.page = page; self.refresh()
        if page is not None: page.loadFinished.connect(self._on_load_finished)

    def _on_load_finished(self, _ok: bool) -> None:
        self.refresh()

    def refresh(self) -> None:
        if self.page is None: return
        script = """(()=>{const n=performance.getEntriesByType('navigation')[0],p=performance.getEntriesByType('paint'),r=performance.getEntriesByType('resource');const paint=x=>p.find(v=>v.name===x)?.startTime??null;const memory=performance.memory;return {ready:document.readyState,duration:n?.duration??null,dom:n?.domContentLoadedEventEnd??null,load:n?.loadEventEnd??null,fp:paint('first-paint'),fcp:paint('first-contentful-paint'),resources:r.length,bytes:r.reduce((a,x)=>a+(x.transferSize||0),0),memory:memory?.usedJSHeapSize??null}})()"""
        self.page.runJavaScript(script, self._show)

    def _show(self, data) -> None:
        if not isinstance(data, dict): return
        def ms(value): return "—" if not isinstance(value, (int, float)) or value <= 0 else f"{value:.1f} ms"
        self.values["Document ready state"].setText(str(data.get("ready") or "—"))
        for label, key in (("Navigation duration", "duration"), ("DOM content loaded", "dom"), ("Load event", "load"), ("First paint", "fp"), ("First contentful paint", "fcp")):
            self.values[label].setText(ms(data.get(key)))
        self.values["Resources"].setText(str(data.get("resources", "—")))
        self.values["Transferred resource bytes"].setText(str(data.get("bytes", "—")))
        memory = data.get("memory")
        self.values["JS heap memory"].setText(f"{memory / 1048576:.1f} MiB" if isinstance(memory, (int, float)) else "Unsupported")
