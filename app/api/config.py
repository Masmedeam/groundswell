"""GroundsWell API config."""
import os
from pathlib import Path

from dotenv import load_dotenv

# load the repo-root .env (two levels up: app/api/ -> repo root)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

ES_URL = os.getenv("ES_URL", "http://localhost:9201")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
MODEL = os.getenv("GROUNDSWELL_MODEL", "claude-sonnet-4-6")
INDEX_PREFIX = "groundswell-"
