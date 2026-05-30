"""GroundsWell API config."""
import os
from pathlib import Path

from dotenv import load_dotenv

for parent in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
    env_path = parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        break

ES_URL = os.getenv("ES_URL", "http://localhost:9201")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
MODEL = os.getenv("GROUNDSWELL_MODEL", "claude-sonnet-4-6")
INDEX_PREFIX = "groundswell-"
