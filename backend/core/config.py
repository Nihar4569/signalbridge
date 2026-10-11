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

# We try these models in order. If one is rate-limited (429) or unavailable we
# fall through to the next, so a single exhausted quota never breaks the app.
# Override with a comma-separated list in GEMINI_MODELS.
GEMINI_MODELS = [
    m.strip()
    for m in os.getenv(
        "GEMINI_MODELS",
        "gemini-flash-lite-latest,gemini-3.5-flash-lite,gemini-3.1-flash-lite,"
        "gemini-3.8-flash,gemini-flash-latest",
    ).split(",")
    if m.strip()
]
# Kept for anything that wants a single name; the chain above is what's used.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", GEMINI_MODELS[0])

# How long to skip a model after it reports quota exhaustion (seconds).
GEMINI_COOLDOWN_SECONDS = int(os.getenv("GEMINI_COOLDOWN_SECONDS", "900"))

# --- google cloud ---
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
FIRESTORE_EMULATOR_HOST = os.getenv("FIRESTORE_EMULATOR_HOST", "")

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

# --- email (post-approval notifications) ---
# "simulated" = don't really send, just build + log the email (default, no setup).
# "smtp"      = actually send via the SMTP_* settings below.
EMAIL_MODE = os.getenv("EMAIL_MODE", "simulated")
EMAIL_FROM = os.getenv("EMAIL_FROM", "ops@signalbridge.demo")
OPS_EMAIL = os.getenv("OPS_EMAIL", "warehouse-ops@signalbridge.demo")
DEFAULT_SUPPLIER_EMAIL = os.getenv("DEFAULT_SUPPLIER_EMAIL", "orders@supplier.demo")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")



# Governance approval tiers, in integer minor units (paise).
# A plan's recovery cost is compared against these, cheapest tier first.
GOVERNANCE_TIERS = [
    ("local_planner", 5_000_000),      # up to  ₹50,000
    ("regional_manager", 50_000_000),  # up to  ₹5,00,000
    ("executive", None),               # anything above
]
