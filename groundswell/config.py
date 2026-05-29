"""Central config: env tokens, paths, and the metro reference table."""
import os
import socket
from pathlib import Path

import urllib3.util.connection as _u3conn
import yaml
from dotenv import load_dotenv

# Force IPv4 for all urllib3/requests connections. Python requests lacks curl's
# Happy-Eyeballs, so a dead IPv6 route can hang each request for the full timeout.
_u3conn.allowed_gai_family = lambda: socket.AF_INET

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# --- credentials (loaded from .env; never hard-coded) ---
APIFY_TOKEN = os.getenv("APIFY_TOKEN")
BRIGHTDATA_TOKEN = os.getenv("BRIGHTDATA_TOKEN")
BRIGHTDATA_ZONE = os.getenv("BRIGHTDATA_ZONE", "web_unlocker1")
FRED_API_KEY = os.getenv("FRED_API_KEY")  # optional; fredgraph CSV works keyless
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")  # for the GroundsWell agent app

# --- paths ---
DATA_RAW = ROOT / "data" / "raw"
DATA_NORM = ROOT / "data" / "normalized"
DATA_RAW.mkdir(parents=True, exist_ok=True)
DATA_NORM.mkdir(parents=True, exist_ok=True)


def load_metros():
    with open(ROOT / "config" / "metros.yaml") as f:
        return yaml.safe_load(f)["metros"]


METROS = load_metros()
