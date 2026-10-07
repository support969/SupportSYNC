"""Pure helpers: Facebook URL filtering and turning raw scraper output into lead rows."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

LEAD_COLUMNS = [
    "facebook_url",
    "name",
    "category",
    "email",
    "phone",
    "website",
    "address",
    "likes",
    "followers",
    "search_query",
    "scraped_at",
]

# First path segments that are never a business page.
_NON_PAGE_SEGMENTS = {
    "groups", "events", "watch", "marketplace", "gaming", "login", "help",
    "policies", "privacy", "legal", "business", "ads", "hashtag", "photo",
    "photo.php", "story.php", "permalink.php", "sharer", "sharer.php",
    "share", "dialog", "plugins", "reel", "reels", "stories", "search",
    "public", "directory", "places", "pages", "settings", "messages",
    "notifications", "friends", "l.php", "home.php", "careers",
}
# Sub-paths that point at content on a page; we keep only the page root.
_CONTENT_SEGMENTS = {
    "posts", "photos", "videos", "about", "reviews", "events", "community",
    "services", "menu", "shop", "mentions", "followers", "likes", "photos_by",
    "about_contact_and_basic_info", "about_details", "reels", "live_videos",
}
_FB_HOSTS = {"facebook.com", "www.facebook.com", "m.facebook.com", "web.facebook.com", "business.facebook.com"}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def normalize_page_url(url: str) -> str | None:
    """Return the canonical https://www.facebook.com/<page> URL, or None if it isn't a page."""
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if host not in _FB_HOSTS and not host.endswith(".facebook.com"):
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if not parts:
        return None
    first = parts[0].lower()
    if first in _NON_PAGE_SEGMENTS:
        return None
    if first == "profile.php":
        page_id = dict(q.split("=", 1) for q in parsed.query.split("&") if "=" in q).get("id")
        return f"https://www.facebook.com/profile.php?id={page_id}" if page_id else None
    if first == "people" and len(parts) >= 3:
        # /people/<Name>/<id>/ is a valid page URL form.
        return f"https://www.facebook.com/people/{parts[1]}/{parts[2]}"
    if first == "pg" and len(parts) >= 2:
        parts = parts[1:]
    slug = parts[0]
    if "." in slug and slug.lower().endswith(".php"):
        return None
    return f"https://www.facebook.com/{slug}"


def page_key(url: str) -> str:
    """Case-insensitive key used for de-duplication."""
    return (normalize_page_url(url) or url).lower().rstrip("/")


def _first(item: dict, *keys: str):
    for key in keys:
        value = item.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(_as_text(v) for v in value if v not in (None, ""))
    if isinstance(value, dict):
        return ", ".join(str(v) for v in value.values() if v not in (None, ""))
    return str(value).strip()


def _find_email(item: dict) -> str:
    direct = _first(item, "email", "emails", "contactEmail")
    if direct:
        text = _as_text(direct)
        match = EMAIL_RE.search(text)
        return match.group(0) if match else text
    # Fall back to scanning the free-text fields the scraper returned.
    blob = " ".join(_as_text(item.get(k)) for k in ("info", "intro", "about", "description", "contactInfo"))
    match = EMAIL_RE.search(blob)
    return match.group(0) if match else ""


def to_lead(item: dict, search_query: str = "") -> dict:
    """Map one Facebook Pages Scraper result to a row keyed by LEAD_COLUMNS."""
    url = _first(item, "facebookUrl", "pageUrl", "url", "inputUrl") or ""
    return {
        "facebook_url": normalize_page_url(url) or url,
        "name": _as_text(_first(item, "title", "name", "pageName")),
        "category": _as_text(_first(item, "categories", "category")),
        "email": _find_email(item),
        "phone": _as_text(_first(item, "phone", "phoneNumber", "phones")),
        "website": _as_text(_first(item, "website", "websites")),
        "address": _as_text(_first(item, "address", "location")),
        "likes": _as_text(_first(item, "likes")),
        "followers": _as_text(_first(item, "followers")),
        "search_query": search_query,
        "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }


def has_contact(lead: dict) -> bool:
    return bool(lead.get("email") or lead.get("phone"))
