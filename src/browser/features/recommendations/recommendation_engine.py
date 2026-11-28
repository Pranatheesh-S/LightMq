"""Deterministic ranking of local history and bookmark candidates."""

from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
import math
import re
from urllib.parse import unquote_plus, urlsplit, urlunsplit


STOP_WORDS = frozenset({
    "a", "about", "all", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "get", "go", "home", "http", "https", "in", "into", "is", "it", "login", "logout",
    "my", "new", "of", "on", "or", "page", "sign", "the", "to", "up", "user", "web",
    "www", "com", "org", "net", "html", "index",
})
SENSITIVE_QUERY_KEYS = re.compile(
    r"(?:token|auth|password|passwd|secret|session|cookie|credential|api[_-]?key|access[_-]?key|"
    r"signature|sig|code|state|assertion|jwt|payment|card|cvv|reset)", re.I,
)
SENSITIVE_PATH = re.compile(
    r"(?:^|/)(?:login|log-in|logout|sign-in|signin|signout|auth|oauth|callback|password|reset|"
    r"verify|verification|checkout|payment|billing|account/recovery)(?:/|$)", re.I,
)
TOKEN_VALUE = re.compile(r"(?:eyJ[a-zA-Z0-9_-]{12,}\.|[A-Fa-f0-9]{40,}|[A-Za-z0-9_-]{48,})")


def safe_recommendation_url(raw_url: str) -> str | None:
    """Accept only public HTTP(S) pages that do not look like credentials or flows."""
    try:
        parts = urlsplit(str(raw_url).strip())
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            return None
        host = parts.hostname.rstrip(".").lower()
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local", ".internal", ".test", ".invalid")):
            return None
        try:
            address = ipaddress.ip_address(host)
            if not address.is_global:
                return None
        except ValueError:
            if "." not in host:
                return None
        if SENSITIVE_PATH.search(parts.path):
            return None
        for piece in (parts.path, parts.query, parts.fragment):
            if TOKEN_VALUE.search(piece):
                return None
        for item in parts.query.split("&") if parts.query else ():
            key = unquote_plus(item.partition("=")[0])
            if SENSITIVE_QUERY_KEYS.search(key):
                return None
        port = parts.port
        rendered_host = f"[{host}]" if ":" in host else host
        default_port = 80 if parts.scheme.lower() == "http" else 443
        netloc = rendered_host + (f":{port}" if port and port != default_port else "")
        return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", parts.query, ""))
    except (TypeError, ValueError, UnicodeError):
        return None


def recommendation_key(raw_url: str) -> str | None:
    """Return a query/fragment-free key safe to persist for user feedback."""
    clean = safe_recommendation_url(raw_url)
    if not clean:
        return None
    parts = urlsplit(clean)
    host = (parts.hostname or "").lower()
    try:
        port = parts.port
    except ValueError:
        return None
    netloc = f"[{host}]" if ":" in host else host
    default_port = 80 if parts.scheme == "http" else 443
    if port and port != default_port:
        netloc += f":{port}"
    return urlunsplit((parts.scheme, netloc, parts.path or "/", "", ""))


def _tokens(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]{3,}", text.casefold())
        if token not in STOP_WORDS and not token.isdigit()
    }


def _timestamp(raw: object) -> datetime | None:
    try:
        value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


class RecommendationEngine:
    """Build explainable, deduplicated recommendations from bounded local rows."""

    WEIGHTS = {"frequency": 0.30, "recency": 0.30, "bookmark": 0.20, "context": 0.15, "feedback": 0.05}
    MAX_RESULTS = 24

    def recommend(
        self,
        history: list[dict],
        bookmarks: list[dict],
        feedback: list[dict],
        *,
        context_url: str = "",
        context_title: str = "",
        show_continue: bool = True,
        show_related: bool = True,
        now: datetime | None = None,
        limit: int = 8,
    ) -> dict[str, list[dict]]:
        """Return categorized cards using only the supplied local candidate data."""
        current_time = now or datetime.now(timezone.utc)
        now_utc = (
            current_time.replace(tzinfo=timezone.utc)
            if current_time.tzinfo is None
            else current_time.astimezone(timezone.utc)
        )
        feedback_by_key = {str(row.get("url_key", "")): row for row in feedback if row.get("url_key")}
        current_clean = safe_recommendation_url(context_url)
        current_key = recommendation_key(context_url) if current_clean else None
        related_tokens = _tokens(f"{context_title} {urlsplit(current_clean or '').hostname or ''}")

        candidates: dict[str, dict] = {}
        for row in history[:1000]:
            url = safe_recommendation_url(str(row.get("url", "")))
            key = recommendation_key(url or "")
            if not url or not key or key == current_key:
                continue
            try:
                count = max(0, min(1_000_000, int(row.get("visit_count", 0) or 0)))
            except (TypeError, ValueError, OverflowError):
                count = 0
            visited = _timestamp(row.get("last_visit_at", row.get("timestamp", "")))
            title = str(row.get("title", "")).strip()[:200] or (urlsplit(url).hostname or url)
            candidate = candidates.get(key)
            if candidate is None:
                candidate = {"url": url, "key": key, "title": title, "host": urlsplit(url).hostname or "",
                             "count": count, "visited": visited, "bookmark": False, "folder": "",
                             "favicon": str(row.get("favicon", ""))}
                candidates[key] = candidate
            else:
                candidate["count"] = max(candidate["count"], count)
                if visited and (candidate["visited"] is None or visited > candidate["visited"]):
                    candidate["visited"] = visited; candidate["url"] = url; candidate["title"] = title
        for row in bookmarks[:2000]:
            url = safe_recommendation_url(str(row.get("url", "")))
            key = recommendation_key(url or "")
            if not url or not key or key == current_key:
                continue
            candidate = candidates.get(key)
            title = str(row.get("title", "")).strip()[:200] or (urlsplit(url).hostname or url)
            if candidate is None:
                candidate = {"url": url, "key": key, "title": title, "host": urlsplit(url).hostname or "",
                             "count": 0, "visited": None, "bookmark": True,
                             "folder": str(row.get("folder", ""))[:100],
                             "favicon": str(row.get("favicon", ""))}
                candidates[key] = candidate
            else:
                candidate["bookmark"] = True
                candidate["folder"] = str(row.get("folder", ""))[:100]
                if not candidate.get("favicon"):
                    candidate["favicon"] = str(row.get("favicon", ""))
                if not candidate["title"] or candidate["count"] == 0:
                    candidate["title"] = title

        for key, row in feedback_by_key.items():
            if not bool(row.get("is_pinned")) or bool(row.get("is_hidden")) or key == current_key:
                continue
            candidate = candidates.get(key)
            if candidate is None:
                safe_url = safe_recommendation_url(key)
                if not safe_url:
                    continue
                candidate = {"url": safe_url, "key": key, "title": str(row.get("title", "")).strip()[:200] or str(row.get("domain", "")),
                             "host": str(row.get("domain", "")), "count": 0, "visited": None,
                             "bookmark": False, "folder": "", "favicon": ""}
                candidates[key] = candidate
            candidate["pinned"] = True

        visible = [item for item in candidates.values() if not bool(feedback_by_key.get(item["key"], {}).get("is_hidden"))]
        max_count = max((item["count"] for item in visible), default=0)
        denominator = math.log1p(max_count) if max_count > 0 else 1.0
        for item in visible:
            frequency = min(1.0, math.log1p(item["count"]) / denominator) if item["count"] else 0.0
            days = max(0.0, (now_utc - item["visited"]).total_seconds() / 86400) if item["visited"] else None
            recency = math.exp(-days / 14.0) if days is not None else 0.0
            context = self._context_score(item, related_tokens) if related_tokens else 0.0
            feedback_score = 1.0 if item.get("pinned") else 0.0
            bookmark_score = 1.0 if item["bookmark"] else 0.0
            score = (self.WEIGHTS["frequency"] * frequency + self.WEIGHTS["recency"] * recency
                     + self.WEIGHTS["bookmark"] * bookmark_score + self.WEIGHTS["context"] * context
                     + self.WEIGHTS["feedback"] * feedback_score)
            reasons = []
            if item.get("pinned"):
                reasons.append("Pinned by you")
            if item["count"] >= 3 and frequency >= 0.35:
                reasons.append("Frequently visited")
            if recency >= 0.35:
                reasons.append("Visited recently")
            if bookmark_score:
                reasons.append("Saved in bookmarks")
            if context >= 0.25:
                reasons.append("Related to current page")
            item.update({"score": round(score, 8), "frequency_score": frequency, "recency_score": recency,
                         "bookmark_score": bookmark_score, "context_score": context,
                         "feedback_score": feedback_score, "reasons": reasons or ["From your local browsing history"]})

        ordered = sorted(visible, key=lambda item: (-int(bool(item.get("pinned"))), -item["score"], -item["count"],
                                                     -(item["visited"].timestamp() if item["visited"] else 0), item["key"]))
        related = [item for item in ordered if item["context_score"] >= 0.25][:min(6, max(0, limit))] if show_related and related_tokens else []
        # Keep categories disjoint so the page never repeats a card. Pinned items
        # stay in the main section even when they also match the active context.
        related = [item for item in related if not item.get("pinned")]
        related_keys = {item["key"] for item in related}
        primary_pool = [item for item in ordered if item["key"] not in related_keys]
        primary = self._diverse(primary_pool[:max(0, limit)], max(0, limit))
        primary_keys = {item["key"] for item in primary}
        continue_items = []
        if show_continue:
            recent = sorted((candidate for candidate in visible if candidate["visited"]),
                            key=lambda c: (-(c["visited"].timestamp() if c["visited"] else 0), c["key"]))
            continue_items = [item for item in recent if item["key"] not in primary_keys | related_keys]
            continue_items = self._diverse(continue_items, min(8, max(0, limit)))
        # Collapse near-duplicate cards from a domain while retaining pinned items.
        related = self._diverse(related, min(6, max(0, limit)))
        return {"recommended": [self._serialize(item) for item in primary],
                "related": [self._serialize(item) for item in related],
                "continue": [self._serialize(item) for item in continue_items]}

    @staticmethod
    def _context_score(item: dict, context_tokens: set[str]) -> float:
        candidate_tokens = _tokens(f"{item['title']} {item['host']} {item.get('folder', '')}")
        if not candidate_tokens:
            return 0.0
        overlap = len(context_tokens & candidate_tokens)
        return overlap / len(context_tokens | candidate_tokens) if overlap else 0.0

    @staticmethod
    def _diverse(items: list[dict], limit: int) -> list[dict]:
        selected, domains = [], set()
        overflow = []
        for item in items:
            domain = (item.get("host", "") or "").lower()
            if item.get("pinned") or not domain or domain not in domains:
                selected.append(item); domains.add(domain)
            else:
                overflow.append(item)
        selected.extend(overflow)
        return selected[:limit]

    @staticmethod
    def _serialize(item: dict) -> dict:
        favicon = str(item.get("favicon", ""))
        if not favicon.startswith("data:image/") or len(favicon) > 16384:
            favicon = ""
        return {"url": item["url"], "key": item["key"], "title": item["title"], "domain": item["host"],
                "score": item["score"], "reasons": item["reasons"], "pinned": bool(item.get("pinned")),
                "bookmark": bool(item["bookmark"]), "favicon": favicon}
