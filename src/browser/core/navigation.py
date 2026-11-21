"""Navigation utilities for URL normalization and validation.

This module handles sanitization, scheme default injection (e.g. adding https://),
and validation of user-entered navigation targets.
"""

from PySide6.QtCore import QUrl


def normalize_url(input_text: str) -> QUrl:
    """Normalize user input string into a valid QUrl.

    Rules:
    - Empty input returns QUrl("about:blank").
    - Explicit schemes (http://, https://, file://, about:, lightmq:) are preserved.
    - Local development targets (localhost, 127.0.0.1) default to http://.
    - Standard domain names (e.g. example.com) default to https://.
    - Strips leading and trailing whitespace.

    Args:
        input_text: Raw text entered by the user.

    Returns:
        QUrl: Validated and normalized Qt URL instance.
    """
    cleaned = input_text.strip()
    if not cleaned:
        return QUrl("about:blank")

    lower = cleaned.lower()

    # Preserve explicit supported schemes
    if lower.startswith(("http://", "https://", "file://", "about:", "qrc:", "view-source:", "devtools:", "chrome:", "lightmq:")):
        return QUrl(cleaned)

    # Local development hosts default to http://
    if lower.startswith(("localhost", "127.0.0.1")):
        return QUrl(f"http://{cleaned}")

    # Standard public domain names default to secure https://
    return QUrl(f"https://{cleaned}")


def is_valid_url(url: QUrl) -> bool:
    """Check if a QUrl instance is valid and not empty.

    Args:
        url: QUrl to check.

    Returns:
        bool: True if URL is structurally valid, False otherwise.
    """
    return url.isValid() and not url.isEmpty()
