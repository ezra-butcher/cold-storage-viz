"""
Fetch USDA NASS Cold Storage data via Quick Stats API.
Run directly to refresh the local parquet cache:
    python fetch_data.py
"""

import os
import pathlib
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ["NASS_API_KEY"]
BASE_URL = "https://quickstats.nass.usda.gov/api/api_GET/"
CACHE_PATH = pathlib.Path("data/cold_storage.parquet")

# Existing commodities: queried by commodity_desc (confirmed working)
_COMMODITY_DESC_QUERIES = [
    "BEEF",
    "BUTTER",
    "CHEESE",
    "CHICKENS",
    "DUCKS",
    "EGGS",
    "LAMB & MUTTON",
    "PORK",
    "TURKEYS",
    "VEAL",
]

# New series: queried by exact short_desc to guarantee matches.
# Excludes aggregate totals (FRUIT TOTALS, VEGETABLE TOTALS, etc.) —
# those are derivable from the individual series already included.
_SHORT_DESC_QUERIES = [
    # Nuts
    "PECANS, COLD STORAGE, IN SHELL, CHILLED - STOCKS, MEASURED IN LB",
    "PECANS, COLD STORAGE, SHELLED, CHILLED - STOCKS, MEASURED IN LB",
    # Frozen fruit
    "APPLES, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "APRICOTS, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "BLACKBERRIES, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "BLACKBERRIES, COLD STORAGE, IQF, FROZEN - STOCKS, MEASURED IN LB",
    "BLACKBERRIES, COLD STORAGE, PAILS, FROZEN - STOCKS, MEASURED IN LB",
    "BLACKBERRIES, COLD STORAGE, BARRELS, FROZEN - STOCKS, MEASURED IN LB",
    "BLACKBERRIES, COLD STORAGE, JUICE, CONCENTRATE, FROZEN - STOCKS, MEASURED IN LB",
    "BLUEBERRIES, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "BOYSENBERRIES, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "CHERRIES, SWEET, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "CHERRIES, TART, COLD STORAGE, RTP, FROZEN - STOCKS, MEASURED IN LB",
    "CHERRIES, TART, COLD STORAGE, JUICE, FROZEN - STOCKS, MEASURED IN LB",
    "CHERRIES, TART, COLD STORAGE, JUICE, CONCENTRATE, FROZEN - STOCKS, MEASURED IN LB",
    "GRAPES, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "PEACHES, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "RASPBERRIES, BLACK, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "RASPBERRIES, RED, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "RASPBERRIES, RED, COLD STORAGE, IQF, FROZEN - STOCKS, MEASURED IN LB",
    "RASPBERRIES, RED, COLD STORAGE, PAILS, FROZEN - STOCKS, MEASURED IN LB",
    "RASPBERRIES, RED, COLD STORAGE, BARRELS, FROZEN - STOCKS, MEASURED IN LB",
    "RASPBERRIES, RED, COLD STORAGE, JUICE, CONCENTRATE, FROZEN - STOCKS, MEASURED IN LB",
    "STRAWBERRIES, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "STRAWBERRIES, COLD STORAGE, IQF, FROZEN - STOCKS, MEASURED IN LB",
    "STRAWBERRIES, COLD STORAGE, PAILS, FROZEN - STOCKS, MEASURED IN LB",
    "STRAWBERRIES, COLD STORAGE, BARRELS, FROZEN - STOCKS, MEASURED IN LB",
    "STRAWBERRIES, COLD STORAGE, JUICE, FROZEN - STOCKS, MEASURED IN LB",
    "FRUIT, OTHER, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    # Frozen juice concentrate
    "ORANGES, COLD STORAGE, JUICE, CONCENTRATE, FROZEN - STOCKS, MEASURED IN LB",
    # Frozen vegetables
    "ASPARAGUS, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "BEANS, GREEN, LIMA, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "BEANS, GREEN, REGULAR CUT, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "BEANS, GREEN, FRENCH CUT, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "BROCCOLI, SPEARS, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "BROCCOLI, CHOPPED & CUT, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "BRUSSELS SPROUTS, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "CARROTS, DICED, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "CARROTS, (EXCL DICED), COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "CAULIFLOWER, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "SWEET CORN, CUT, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "SWEET CORN, COB, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "VEGETABLES, MIXED, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "OKRA, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "ONIONS, RINGS, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "ONIONS, (EXCL RINGS), COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "PEAS, BLACKEYE, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "PEAS, GREEN, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "PEAS & CARROTS, MIXED, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "SPINACH, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "SQUASH, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "GREENS, SOUTHERN, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "VEGETABLES, OTHER, (EXCL POTATOES), COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    # Frozen potatoes
    "POTATOES, FRENCH FRIED, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
    "POTATOES, (EXCL FRENCH FRIED), COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB",
]

PARAMS_BASE = {
    "key": API_KEY,
    "statisticcat_desc": "STOCKS",
    "format": "JSON",
}


def fetch_commodity(commodity: str) -> pd.DataFrame:
    params = {**PARAMS_BASE, "commodity_desc": commodity}
    resp = requests.get(BASE_URL, params=params, timeout=60)
    resp.raise_for_status()
    payload = resp.json()
    if "error" in payload:
        raise ValueError(f"API error for {commodity}: {payload['error']}")
    return pd.DataFrame(payload.get("data", []))


def fetch_short_desc(short_desc: str) -> pd.DataFrame:
    params = {**PARAMS_BASE, "short_desc": short_desc}
    resp = requests.get(BASE_URL, params=params, timeout=60)
    resp.raise_for_status()
    payload = resp.json()
    if "error" in payload:
        print(f"  API error for '{short_desc}': {payload['error']}")
        return pd.DataFrame()
    return pd.DataFrame(payload.get("data", []))


def fetch_all() -> pd.DataFrame:
    frames = []

    for commodity in _COMMODITY_DESC_QUERIES:
        print(f"Fetching commodity: {commodity}...")
        df = fetch_commodity(commodity)
        print(f"  → {len(df):,} rows")
        if not df.empty:
            frames.append(df)

    total = len(_SHORT_DESC_QUERIES)
    for i, short_desc in enumerate(_SHORT_DESC_QUERIES, 1):
        label = short_desc.split(" - ")[0]
        print(f"[{i}/{total}] {label}")
        df = fetch_short_desc(short_desc)
        if df.empty:
            print("  → 0 rows (skipped)")
        else:
            print(f"  → {len(df):,} rows")
            frames.append(df)

    return pd.concat(frames, ignore_index=True)


# Maps "END OF JAN" → month int 1
_MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4,
    "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8,
    "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def _parse_period(s: str):
    """'END OF JAN' → 1, 'END OF APR' → 4, etc."""
    for abbr, num in _MONTH_MAP.items():
        if abbr in s.upper():
            return num
    return None


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Keep only cold storage series (filters out grain/oilseed stocks from
    # commodity_desc queries that return mixed results)
    if "short_desc" in df.columns:
        df = df[df["short_desc"].str.contains("COLD STORAGE", na=False)]

    # Numeric value
    df["Value"] = pd.to_numeric(
        df["Value"].str.replace(",", ""), errors="coerce"
    )
    df["year"] = pd.to_numeric(df["year"], errors="coerce")

    # Parse "END OF JAN" → month number → date
    df["month_num"] = df["reference_period_desc"].apply(_parse_period)
    df["date"] = pd.to_datetime(
        {
            "year": df["year"],
            "month": df["month_num"],
            "day": 1,
        },
        errors="coerce",
    )

    # Series label: strip the " - STOCKS, MEASURED IN LB" suffix
    df["series_label"] = df["short_desc"].str.replace(
        r" - STOCKS, MEASURED IN LB$", "", regex=True
    )

    keep = [
        "date", "year", "month_num",
        "commodity_desc", "class_desc", "short_desc", "series_label",
        "util_practice_desc", "agg_level_desc", "state_name",
        "unit_desc", "Value", "CV (%)",
    ]
    existing = [c for c in keep if c in df.columns]
    df = df[existing]
    df = df.dropna(subset=["date", "Value"])
    df = df.sort_values(["commodity_desc", "series_label", "date"])
    return df.reset_index(drop=True)


def main():
    CACHE_PATH.parent.mkdir(exist_ok=True)
    raw = fetch_all()
    cleaned = clean(raw)
    cleaned.to_parquet(CACHE_PATH, index=False)
    print(f"\nSaved {len(cleaned):,} rows → {CACHE_PATH}")
    print("Commodities:", sorted(cleaned["commodity_desc"].unique().tolist()))
    print(f"Series count: {cleaned['series_label'].nunique()}")
    print("Date range:", cleaned["date"].min().date(), "→", cleaned["date"].max().date())


def load_cache() -> pd.DataFrame:
    if not CACHE_PATH.exists():
        raise FileNotFoundError(
            f"{CACHE_PATH} not found. Run `python fetch_data.py` first."
        )
    return pd.read_parquet(CACHE_PATH)


if __name__ == "__main__":
    main()
