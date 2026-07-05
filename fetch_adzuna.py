"""
Fetches job postings from the Adzuna API and saves raw JSON to disk.
Run this first. It will NOT re-hit the API if a raw file already exists
for a given (title, city, page) combo -- so you can re-run safely.
"""
import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("ADZUNA_APP_ID")
APP_KEY = os.getenv("ADZUNA_APP_KEY")
COUNTRY = "us"
BASE_URL = f"https://api.adzuna.com/v1/api/jobs/{COUNTRY}/search"

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "raw_data")
os.makedirs(RAW_DIR, exist_ok=True)

# Keep this list small for a 2-day build. Expand later.
JOB_TITLES = [
    "data analyst",
    "software engineer",
    "python developer",
    "data scientist",
    "business analyst",
]

CITIES = [
    "New York",
    "San Francisco",
    "Austin",
    "Chicago",
    "Seattle",
]

RESULTS_PER_PAGE = 50
PAGES_PER_QUERY = 2  # 2 pages x 50 = ~100 jobs per (title, city) combo


def fetch_page(title, city, page):
    params = {
        "app_id": APP_ID,
        "app_key": APP_KEY,
        "results_per_page": RESULTS_PER_PAGE,
        "what": title,
        "where": city,
        "content-type": "application/json",
    }
    url = f"{BASE_URL}/{page}"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main():
    if not APP_ID or not APP_KEY:
        raise SystemExit(
            "Missing ADZUNA_APP_ID / ADZUNA_APP_KEY. "
            "Copy .env.example to .env and fill in your keys."
        )

    for title in JOB_TITLES:
        for city in CITIES:
            for page in range(1, PAGES_PER_QUERY + 1):
                safe_title = title.replace(" ", "_")
                safe_city = city.replace(" ", "_")
                out_path = os.path.join(
                    RAW_DIR, f"{safe_title}__{safe_city}__p{page}.json"
                )

                if os.path.exists(out_path):
                    print(f"SKIP (already fetched): {out_path}")
                    continue

                try:
                    data = fetch_page(title, city, page)
                except requests.HTTPError as e:
                    print(f"ERROR fetching {title} / {city} / page {page}: {e}")
                    continue

                with open(out_path, "w") as f:
                    json.dump(data, f)

                n_results = len(data.get("results", []))
                print(f"Saved {n_results} jobs -> {out_path}")

                time.sleep(0.5)  # be polite to the API / avoid rate limits

    print("\nDone. Raw JSON files are in:", RAW_DIR)


if __name__ == "__main__":
    main()
