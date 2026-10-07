"""Find Facebook business pages by keyword + location and save their contact info as leads.

Example:
    python -m fb_leads -k "dentist" -k "med spa" -l "Miami, FL" -l "Tampa, FL"
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys

from .leads import LEAD_COLUMNS, has_contact, page_key, to_lead

log = logging.getLogger("fb_leads")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="fb_leads", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-k", "--keyword", action="append", required=True, help="Business type to search for (repeatable)")
    p.add_argument("-l", "--location", action="append", default=[], help="City/region to pair with each keyword (repeatable)")
    p.add_argument("--pages-per-query", type=int, default=1, help="Google result pages per query, ~10 results each (default 1)")
    p.add_argument("--country", help="Google country code, e.g. us, gb, ca")
    p.add_argument("--max-pages", type=int, default=100, help="Cap on Facebook pages scraped per run (default 100)")
    p.add_argument("--include-no-contact", action="store_true", help="Keep pages with no email or phone")
    p.add_argument("--csv", metavar="PATH", help="Also write the new leads to this CSV file")
    p.add_argument("--no-sheet", action="store_true", help="Skip Google Sheets (use with --csv)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)

    token = os.getenv("APIFY_TOKEN")
    if not token:
        log.error("APIFY_TOKEN is not set (see .env.example)")
        return 2
    if args.no_sheet and not args.csv:
        log.error("--no-sheet needs --csv, otherwise the leads go nowhere")
        return 2

    ws = None
    known: set[str] = set()
    if not args.no_sheet:
        sheet_id = os.getenv("GOOGLE_SHEET_ID")
        if not sheet_id:
            log.error("GOOGLE_SHEET_ID is not set (or pass --no-sheet --csv leads.csv)")
            return 2
        from .sheets import existing_keys, open_worksheet
        ws = open_worksheet(sheet_id, os.getenv("GOOGLE_SHEET_TAB", "Leads"))
        known = existing_keys(ws)
        log.info("Sheet already has %d leads; those will be skipped", len(known))

    from apify_client import ApifyClient
    from .apify_source import build_queries, find_page_urls, scrape_pages

    client = ApifyClient(token)
    found = find_page_urls(client, build_queries(args.keyword, args.location), args.pages_per_query, args.country)
    unseen = [u for u in found if page_key(u) not in known]
    new_urls = unseen[: args.max_pages]
    log.info("%d new pages to scrape (%d already in sheet)", len(new_urls), len(found) - len(unseen))

    query_by_key = {page_key(u): q for u, q in found.items()}
    leads, seen = [], set()
    for item in scrape_pages(client, new_urls):
        if item.get("error"):
            continue
        lead = to_lead(item)
        key = page_key(lead["facebook_url"])
        if key in seen or key in known:
            continue
        seen.add(key)
        lead["search_query"] = query_by_key.get(key) or query_by_key.get(page_key(item.get("inputUrl", "")), "")
        if args.include_no_contact or has_contact(lead):
            leads.append(lead)

    log.info("%d leads with contact info", len(leads))
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=LEAD_COLUMNS)
            writer.writeheader()
            writer.writerows(leads)
        log.info("Wrote %s", args.csv)
    if ws is not None:
        from .sheets import append_leads
        log.info("Appended %d rows to Google Sheets", append_leads(ws, leads))
    return 0


if __name__ == "__main__":
    sys.exit(main())
