"""Central configuration.

Everything that can change between machines lives here and is read from the
environment (see .env.example). Import `config` and read the values — never
re-read os.environ elsewhere.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a local .env file if present. Safe to call once at import.
load_dotenv()

# Repo root = two levels up from this file (backend/core/config.py -> repo/).
ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = ROOT / "fixtures"

# --- data ---
DATA_BACKEND = os.getenv("DATA_BACKEND", "local")  # "local" | "firestore"
TENANT_ID = os.getenv("TENANT_ID", "buildx-demo")

# --- gemini / agent ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

# --- google cloud ---
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
FIRESTORE_EMULATOR_HOST = os.getenv("FIRESTORE_EMULATOR_HOST", "")

# Weather + news scan while the API process is running. 0 turns the loop off.
SIGNAL_SCAN_INTERVAL_SECONDS = int(os.getenv("SIGNAL_SCAN_INTERVAL_SECONDS", "120"))

# --- external APIs (free, no key needed) ---
HTTP_TIMEOUT = 15  # seconds, for any outbound API call
HTTP_USER_AGENT = "SignalBridge/0.1 (prototype)"

# Open-Meteo weather forecast. Filtered by latitude/longitude + chosen variables.
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# GDELT DOC 2.0 news search. Filtered by location phrase + disruption keywords.
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
NEWS_TIMESPAN = os.getenv("NEWS_TIMESPAN", "3d")   # how far back to search
NEWS_MAX_RECORDS = int(os.getenv("NEWS_MAX_RECORDS", "10"))
DISRUPTION_KEYWORDS = [
    "strike", "closure", "closed", "suspended", "congestion",
    "blocked", "shutdown", "cyclone", "storm", "flood",
]

# Weather risk thresholds (worst value in the forecast window).
WEATHER_WIND_GUST_HIGH_KMH = 60
WEATHER_WIND_GUST_MED_KMH = 40
WEATHER_PRECIP_HIGH_MM = 20
WEATHER_PRECIP_MED_MM = 10
WEATHER_STORM_CODES = {95, 96, 97, 99}  # WMO thunderstorm codes


# Governance approval tiers, in integer minor units (paise).
# A plan's recovery cost is compared against these, cheapest tier first.
GOVERNANCE_TIERS = [
    ("local_planner", 5_000_000),      # up to  ₹50,000
    ("regional_manager", 50_000_000),  # up to  ₹5,00,000
    ("executive", None),               # anything above
]
