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
