# Facebook Page Lead Scraper

Finds Facebook business pages by **keyword + location**, pulls their public contact
details (email, phone, website, address) with [Apify](https://apify.com), and appends
new leads to a **Google Sheet**. Re-running skips pages that are already in the sheet.

## How it works

1. For every keyword × location pair it runs a Google search like
   `site:facebook.com dentist Miami, FL` (Apify actor `apify/google-search-scraper`).
2. It keeps only Facebook *page* URLs (it drops groups, events and posts) and removes duplicates.
3. It scrapes each page's About/contact info (Apify actor `apify/facebook-pages-scraper`).
4. Pages with an email or phone number are appended to your sheet. The columns are:
   `facebook_url, name, category, email, phone, website, address, likes, followers, search_query, scraped_at`.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill it in
```

### Keys you need

| Variable | Where to get it |
|---|---|
| `APIFY_TOKEN` | Apify Console → Settings → API & Integrations |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google Cloud Console → enable the **Google Sheets API** and the **Google Drive API** → create a Service Account → Keys → Add key (JSON). Set this to the file path, or paste the raw JSON. |
| `GOOGLE_SHEET_ID` | Create a sheet, then **share it (Editor) with the service account's email** (`...@...iam.gserviceaccount.com`). The ID is the part of the URL between `/d/` and `/edit`. |

Keep `.env` and the JSON key file out of git. `.gitignore` already excludes them.

## Usage

```bash
# Dentists and med spas in two cities, US Google results
python -m fb_leads -k "dentist" -k "med spa" -l "Miami, FL" -l "Tampa, FL" --country us

# Go deeper (3 Google result pages per query) and also save a CSV copy
python -m fb_leads -k "roofing contractor" -l "Austin, TX" --pages-per-query 3 --csv leads.csv

# Try it without Google Sheets
python -m fb_leads -k "gym" -l "Denver" --no-sheet --csv leads.csv
```

Options: `--max-pages` caps how many Facebook pages are scraped per run (default 100),
which keeps Apify costs under control. `--include-no-contact` keeps pages that have no email or phone.

## Cost and compliance notes

- Both actors bill your Apify account per result or per compute unit. Start with a small
  `--max-pages` to see what one run costs.
- The tool collects only information that businesses publish on their pages. Your outreach
  still has to follow CAN-SPAM, GDPR, TCPA and similar laws, as well as Facebook's terms.

## Development

```bash
pip install -r requirements-dev.txt
pytest
```

The tests use a fake Apify client, so they need no keys or network access.
