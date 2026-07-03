# scraping_ouedkniss

Scrapes job listings from [Ouedkniss](https://www.ouedkniss.com) (Algerian classifieds site) via its GraphQL API, and converts JSON output to CSV.

## Files

- `jobs.py` — scrapes all job listings under the "Offres d'emploi" category, paginating through the GraphQL API, and saves the results to `jobs.json` (or `.csv`).
- `converter` — generic JSON-to-CSV converter (supports flattening nested JSON).

## Usage

```bash
pip install requests
python jobs.py
```

Edit the config block at the top of `jobs.py` to change `MAX_PAGES` (default: scrape all pages) or `OUTPUT_FILE`.

To convert an existing JSON file to CSV:

```bash
python converter jobs.json jobs.csv --flatten
```

## Note

`jobs.json` / `jobs.csv` (scraped output) are gitignored and not tracked in this repo.

## Automation (GitHub Actions)

`.github/workflows/scrape.yml` runs the scraper on the 1st of every month (and on-demand via the Actions tab → "Scrape Ouedkniss Jobs" → Run workflow), then emails the resulting `jobs.csv`.

Requires two repository secrets (Settings → Secrets and variables → Actions):

- `MAIL_USERNAME` — the sending Gmail address
- `MAIL_PASSWORD` — a Gmail [App Password](https://myaccount.google.com/apppasswords) (requires 2FA enabled on the account; a normal password will not work)

`MAX_PAGES` in `jobs.py` is currently set to `10` for faster runs; set it to `None` for a full scrape.
