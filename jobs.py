"""
Ouedkniss Job Scraper — GraphQL API version
============================================
Scrapes ALL job listings from Ouedkniss with complete field coverage.

Usage:
    pip install requests
    python ouedkniss_scraper.py
"""

import json
import csv
import time
import uuid
import requests
from pathlib import Path

# ─── CONFIG ───────────────────────────────────────────────────────────────────
MAX_PAGES = 10           # None = scrape ALL pages (~605 pages, ~29,000 jobs)
JSON_FILE = "jobs.json"  # Raw scrape output
CSV_FILE  = "jobs.csv"   # Auto-generated from JSON_FILE after scraping
DELAY_SEC = 1.0          # Polite delay between pages
# ──────────────────────────────────────────────────────────────────────────────

GRAPHQL_URL = "https://api.ouedkniss.com/graphql"

# Full category map: id → name
CATEGORY_MAP = {
    "209": "Offres d'emploi",
    "210": "Sécurité",
    "211": "Mécanique Auto",
    "212": "Beauté & Esthétique",
    "213": "Transport & Chauffeurs",
    "214": "Artisanat",
    "215": "Bureautique & Secrétariat",
    "216": "Administration & Management",
    "217": "Éducation & Formations",
    "218": "Électronique & Technique",
    "219": "Construction & Travaux",
    "220": "Commerce & Vente",
    "221": "Commercial & Marketing",
    "222": "Graphisme & Communication",
    "223": "Comptabilité & Audit",
    "224": "Environnement",
    "225": "Agents polyvalents",
    "226": "Nettoyage & Hygiène",
    "227": "Industrie & Production",
    "228": "Informatique & Internet",
    "229": "Juridique",
    "230": "Journalisme & Presse",
    "231": "Achat & Logistique",
    "232": "Recherche & Développement",
    "233": "Couture et Confection",
    "234": "Médecine & Santé",
    "235": "Tourisme & Gastronomie",
    "236": "Carburants & Mines",
    "237": "Immobilier",
    "238": "Autre",
}

QUERY = """
query SearchQuery($q: String, $filter: SearchFilterInput, $mediaSize: MediaSize = MEDIUM) {
  search(q: $q, filter: $filter) {
    announcements {
      data {
        id
        title
        slug
        createdAt: refreshedAt
        isFromStore
        isCommentEnabled
        hasDelivery
        deliveryType
        paymentMethod
        likeCount
        description
        status
        cities {
          id
          name
          slug
          region {
            id
            name
            slug
          }
        }
        store {
          id
          name
          slug
          imageUrl
          isOfficial
          isVerified
        }
        user {
          id
        }
        defaultMedia(size: $mediaSize) {
          mediaUrl
          mimeType
        }
        medias(size: SMALL) {
          mediaUrl
          mimeType
        }
        price
        pricePreview
        priceUnit
        oldPrice
        oldPricePreview
        priceType
        exchangeType
        category {
          id
          slug
        }
      }
      paginatorInfo {
        lastPage
        hasMorePages
      }
    }
  }
}
"""


def make_headers() -> dict:
    return {
        "accept": "*/*",
        "accept-language": "fr",
        "authorization": "",
        "content-type": "application/json",
        "locale": "fr",
        "origin": "https://www.ouedkniss.com",
        "referer": "https://www.ouedkniss.com/offres_demandes_emploi/1",
        "sec-ch-ua": '"Microsoft Edge";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0",
        "x-app-version": '"3.5.20"',
        "x-referer": "https://www.ouedkniss.com/offres_demandes_emploi",
        "x-track-id": str(uuid.uuid4()),
        "x-track-timestamp": str(int(time.time())),
    }


def fetch_page(page: int, session: requests.Session) -> dict:
    payload = {
        "operationName": "SearchQuery",
        "query": QUERY,
        "variables": {
            "mediaSize": "MEDIUM",
            "q": None,
            "filter": {
                "categorySlug": "emploi_offres",
                "origin": None,
                "connected": False,
                "delivery": None,
                "regionIds": [],
                "cityIds": [],
                "priceRange": [],
                "exchange": None,
                "hasPictures": False,
                "hasPrice": False,
                "priceUnit": None,
                "fields": [],
                "page": page,
                "orderByField": {"field": "REFRESHED_AT"},
                "count": 48,
            },
        },
    }

    headers = make_headers()
    response = session.post(GRAPHQL_URL, json=payload, headers=headers, timeout=30)

    if response.status_code != 200:
        print(f"  ✗ HTTP {response.status_code}: {response.text[:400]}")
        response.raise_for_status()

    data = response.json()
    if "errors" in data:
        print(f"  ✗ GraphQL errors: {data['errors']}")
        raise ValueError(f"GraphQL error on page {page}")

    return data


def parse_jobs(data: dict, page_num: int) -> list[dict]:
    announcements = (
        data
        .get("data", {})
        .get("search", {})
        .get("announcements", {})
        .get("data", [])
    )

    jobs = []
    for a in announcements:
        # Location
        cities      = a.get("cities") or []
        city        = cities[0] if cities else {}
        region      = city.get("region") or {}

        # Store
        store = a.get("store") or {}

        # Media
        media       = a.get("defaultMedia") or {}
        all_medias  = a.get("medias") or []
        extra_imgs  = [m["mediaUrl"] for m in all_medias if m.get("mediaUrl")]

        # Category
        category     = a.get("category") or {}
        category_id  = category.get("id")
        category_slug = category.get("slug", "")
        # Extract subcategory from slug: "emploi_offres-commerce-vente" → "Commerce & Vente"
        category_name = CATEGORY_MAP.get(str(category_id), category_slug.replace("emploi_offres-", "").replace("-", " ").title())

        jobs.append({
            # ── Core ──────────────────────────────
            "id":                  a.get("id"),
            "title":               a.get("title"),
            "description":         (a.get("description") or "").strip(),
            "status":              a.get("status"),
            "created_at":          a.get("createdAt"),
            "url":                 f"https://www.ouedkniss.com/{a['slug']}" if a.get("slug") else None,
            "slug":                a.get("slug"),

            # ── Category ──────────────────────────
            "category_id":         category_id,
            "category_slug":       category_slug,
            "category_name":       category_name,

            # ── Location ──────────────────────────
            "city_id":             city.get("id"),
            "city":                city.get("name"),
            "city_slug":           city.get("slug"),
            "wilaya_id":           region.get("id"),
            "wilaya":              region.get("name"),
            "wilaya_slug":         region.get("slug"),

            # ── Price / Salary ────────────────────
            "price":               a.get("price"),
            "price_preview":       a.get("pricePreview"),
            "price_type":          a.get("priceType"),
            "price_unit":          a.get("priceUnit"),
            "old_price":           a.get("oldPrice"),
            "exchange_type":       a.get("exchangeType"),
            "payment_method":      a.get("paymentMethod"),

            # ── Engagement ───────────────────────
            "like_count":          a.get("likeCount"),
            "is_comment_enabled":  a.get("isCommentEnabled"),
            "has_delivery":        a.get("hasDelivery"),
            "delivery_type":       a.get("deliveryType"),

            # ── Store / Poster ───────────────────
            "is_from_store":       a.get("isFromStore"),
            "store_id":            store.get("id"),
            "store_name":          store.get("name"),
            "store_slug":          store.get("slug"),
            "store_image":         store.get("imageUrl"),
            "store_is_verified":   store.get("isVerified"),
            "store_is_official":   store.get("isOfficial"),
            "user_id":             (a.get("user") or {}).get("id"),

            # ── Media ────────────────────────────
            "image_url":           media.get("mediaUrl"),
            "extra_images":        ", ".join(extra_imgs) if extra_imgs else None,

            # ── Meta ─────────────────────────────
            "page":                page_num,
        })

    return jobs


def get_total_pages(data: dict) -> int:
    return (
        data
        .get("data", {})
        .get("search", {})
        .get("announcements", {})
        .get("paginatorInfo", {})
        .get("lastPage", 1)
    )


def save_json(jobs: list[dict], filename: str):
    Path(filename).write_text(
        json.dumps(jobs, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"\n✅ Saved {len(jobs)} jobs → {filename}")


def flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    """Recursively flatten a nested dictionary; lists become '; '-joined strings."""
    items = {}
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(flatten_dict(v, new_key, sep=sep))
        elif isinstance(v, list):
            items[new_key] = "; ".join(str(i) for i in v)
        else:
            items[new_key] = v
    return items


def json_to_csv(json_filename: str, csv_filename: str):
    """Load a JSON array of job objects and convert it to CSV, flattening as needed."""
    jobs = json.loads(Path(json_filename).read_text(encoding="utf-8"))
    if not jobs:
        print("No jobs to convert.")
        return

    rows = [flatten_dict(job) for job in jobs]

    # Union of all keys, in first-seen order, so no row is missing a column.
    fieldnames = list(dict.fromkeys(key for row in rows for key in row))

    with open(csv_filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"✅ Converted {len(rows)} jobs → {csv_filename}")


def main():
    print("🐍 Ouedkniss Job Scraper — Full Run\n")
    all_jobs = []
    failed_pages = []

    with requests.Session() as session:
        # Page 1 — detect total
        print("  → Fetching page 1...")
        data = fetch_page(1, session)
        total_pages = get_total_pages(data)
        pages_to_scrape = min(MAX_PAGES, total_pages) if MAX_PAGES else total_pages
        print(f"  📄 {total_pages} total pages — scraping all {pages_to_scrape}\n")

        jobs = parse_jobs(data, 1)
        print(f"  ✓ Page 1/{pages_to_scrape} — {len(jobs)} jobs  |  total: {len(jobs)}")
        all_jobs.extend(jobs)

        for page_num in range(2, pages_to_scrape + 1):
            time.sleep(DELAY_SEC)
            try:
                data = fetch_page(page_num, session)
                jobs = parse_jobs(data, page_num)
                all_jobs.extend(jobs)
                print(f"  ✓ Page {page_num}/{pages_to_scrape} — {len(jobs)} jobs  |  total: {len(all_jobs)}")
            except Exception as e:
                print(f"  ✗ Page {page_num} failed: {e} — will retry later")
                failed_pages.append(page_num)

        # Retry failed pages once
        if failed_pages:
            print(f"\n  ↻ Retrying {len(failed_pages)} failed pages...")
            for page_num in failed_pages:
                time.sleep(DELAY_SEC * 3)
                try:
                    data = fetch_page(page_num, session)
                    jobs = parse_jobs(data, page_num)
                    all_jobs.extend(jobs)
                    print(f"  ✓ Retry page {page_num} — {len(jobs)} jobs")
                except Exception as e:
                    print(f"  ✗ Retry page {page_num} failed again: {e}")

    print(f"\n📦 Total jobs collected: {len(all_jobs)}")

    save_json(all_jobs, JSON_FILE)
    json_to_csv(JSON_FILE, CSV_FILE)


if __name__ == "__main__":
    main()