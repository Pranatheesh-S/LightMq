"""Register the trusted local scheme used by LightMq's built-in start pages."""

from PySide6.QtWebEngineCore import QWebEngineUrlScheme

_QRC_REGISTERED = False


def register_webchannel_resource_access() -> None:
    """Allow Qt's ``qrc:`` WebChannel script on the built-in start page.

    Qt 6 no longer lets custom origins load QRC resources by default. Register
    the QRC scheme with the narrow access flags documented by Qt so the trusted
    LightMq page can load its bundled WebChannel client without enabling network
    requests in the page's Content Security Policy.
    """
    global _QRC_REGISTERED
    if _QRC_REGISTERED:
        return
    scheme = QWebEngineUrlScheme(b"qrc")
    scheme.setFlags(
        QWebEngineUrlScheme.Flag.SecureScheme
        | QWebEngineUrlScheme.Flag.LocalAccessAllowed
        | QWebEngineUrlScheme.Flag.CorsEnabled
        | QWebEngineUrlScheme.Flag.ViewSourceAllowed
    )
    QWebEngineUrlScheme.registerScheme(scheme)
    _QRC_REGISTERED = True
