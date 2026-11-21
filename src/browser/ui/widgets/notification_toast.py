"""Small, nonmodal popup notifications for browser events."""

from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget


class NotificationToast(QFrame):
    """Show a brief notification without taking focus from the browser."""

    def __init__(self, parent: QWidget):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(
            "QFrame { background: #252525; color: white; border: 1px solid #555; "
            "border-radius: 6px; } QLabel { padding: 10px 14px; }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        self.label.setMaximumWidth(360)
        layout.addWidget(self.label)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, message: str, timeout_ms: int = 3500) -> None:
        """Display text at the top-right of the parent window temporarily."""
        self.label.setText(message)
        self.adjustSize()
        parent = self.parentWidget()
        if parent is not None:
            position = parent.mapToGlobal(
                QPoint(max(12, parent.width() - self.width() - 18), 48)
            )
            self.move(position)
        self.show()
        self.raise_()
        self._timer.start(max(1000, timeout_ms))
