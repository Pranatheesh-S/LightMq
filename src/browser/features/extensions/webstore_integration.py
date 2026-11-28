"""Safe recognition of Chrome Web Store listings; no package scraping."""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlsplit


_EXTENSION_ID = re.compile(r"^[a-p]{32}$")


@dataclass(frozen=True)
class WebStoreListing:
    """A syntactically recognized listing; the ID is not store-verified metadata."""

    url: str
    extension_id: str | None
    slug: str | None


def recognize_webstore_listing(url: str) -> WebStoreListing | None:
    """Recognize only HTTPS detail pages on the official store hostnames."""
    try:
        parts = urlsplit(url)
        if parts.scheme.casefold() != "https" or parts.username or parts.password:
            return None
        if parts.port not in (None, 443):
            return None
        host = (parts.hostname or "").casefold()
        segments = [segment for segment in parts.path.split("/") if segment]
        if host == "chromewebstore.google.com":
            if len(segments) != 3 or segments[0] != "detail":
                return None
            slug, candidate = segments[1], segments[2]
        elif host == "chrome.google.com":
            if len(segments) != 4 or segments[:2] != ["webstore", "detail"]:
                return None
            slug, candidate = segments[2], segments[3]
        else:
            return None
        extension_id = candidate if _EXTENSION_ID.fullmatch(candidate) else None
        return WebStoreListing(url=url, extension_id=extension_id, slug=slug or None)
    except (TypeError, ValueError):
        return None


def webstore_install_limitation() -> str:
    """Explain the supported publisher API and LightMq's local-package flow."""
    return (
        "LightMq recognizes this official store listing, but does not download or install "
        "packages directly from the Chrome Web Store. Google's documented Web Store API "
        "is an authenticated publisher API for managing items, not a public consumer "
        "package-download API. Choose an authorized local ZIP or unpacked folder to inspect "
        "it in LightMq. Store identity shown here is read from the URL and is not independently verified."
    )
