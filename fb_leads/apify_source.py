"""Apify calls: find Facebook pages via Google search, then scrape their details."""

from __future__ import annotations

import logging
import os

from apify_client import ApifyClient

from .leads import normalize_page_url, page_key

log = logging.getLogger(__name__)

SEARCH_ACTOR = os.getenv("APIFY_SEARCH_ACTOR", "apify/google-search-scraper")
PAGES_ACTOR = os.getenv("APIFY_PAGES_ACTOR", "apify/facebook-pages-scraper")


def build_queries(keywords: list[str], locations: list[str]) -> list[str]:
    locations = locations or [""]
    return [f'site:facebook.com {kw} {loc}'.strip() for kw in keywords for loc in locations]


def _dataset_items(client: ApifyClient, run) -> list[dict]:
    if run is None:
        raise RuntimeError("Apify run did not return (timed out or failed to start)")
    status = getattr(run, "status", None) or run.get("status")
    status = getattr(status, "value", status)
    dataset_id = getattr(run, "default_dataset_id", None) or run.get("defaultDatasetId")
    if status != "SUCCEEDED":
        log.warning("Apify run finished with status %s; using partial results", status)
    return list(client.dataset(dataset_id).iterate_items())


def find_page_urls(
    client: ApifyClient,
    queries: list[str],
    pages_per_query: int = 1,
    country_code: str | None = None,
) -> dict[str, str]:
    """Return {page_url: query_that_found_it} for every Facebook page in the results."""
    run_input = {
        "queries": "\n".join(queries),
        "maxPagesPerQuery": pages_per_query,
        "saveHtml": False,
        "saveHtmlToKeyValueStore": False,
    }
    if country_code:
        run_input["countryCode"] = country_code.lower()
    log.info("Searching Google for %d queries via %s", len(queries), SEARCH_ACTOR)
    items = _dataset_items(client, client.actor(SEARCH_ACTOR).call(run_input=run_input))

    found: dict[str, str] = {}
    seen: set[str] = set()
    for item in items:
        query = (item.get("searchQuery") or {}).get("term", "")
        for result in item.get("organicResults") or []:
            url = normalize_page_url(result.get("url", ""))
            if url and page_key(url) not in seen:
                seen.add(page_key(url))
                found[url] = query.replace("site:facebook.com", "").strip()
    log.info("Found %d unique Facebook pages", len(found))
    return found


def scrape_pages(client: ApifyClient, urls: list[str]) -> list[dict]:
    if not urls:
        return []
    log.info("Scraping %d Facebook pages via %s", len(urls), PAGES_ACTOR)
    run_input = {"startUrls": [{"url": u} for u in urls]}
    return _dataset_items(client, client.actor(PAGES_ACTOR).call(run_input=run_input))
