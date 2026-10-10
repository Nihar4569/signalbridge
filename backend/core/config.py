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

# Governance approval tiers, in integer minor units (paise).
# A plan's recovery cost is compared against these, cheapest tier first.
GOVERNANCE_TIERS = [
    ("local_planner", 5_000_000),      # up to  ₹50,000
    ("regional_manager", 50_000_000),  # up to  ₹5,00,000
    ("executive", None),               # anything above
]
