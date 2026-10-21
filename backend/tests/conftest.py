
import os
from pathlib import Path
from urllib.parse import urlparse

from alembic import command
from alembic.config import Config
from dotenv import load_dotenv


# Load the backend environment variables.
BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

TEST_DATABASE_URL = os.getenv("DATABASE_URL_TEST")

if not TEST_DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL_TEST is missing from backend/.env. "
        "Refusing to run tests against an unspecified database."
    )

parsed_url = urlparse(TEST_DATABASE_URL)

# Safety guard: never allow pytest to use the development database.
if parsed_url.path.lstrip("/") != "trustvault_test":
    raise RuntimeError(
        "Unsafe test database configuration. "
        "DATABASE_URL_TEST must point to trustvault_test."
    )

if parsed_url.scheme not in {
    "postgresql",
    "postgresql+psycopg",
}:
    raise RuntimeError(
        "The test database must use PostgreSQL with psycopg."
    )

# Make the existing application and Alembic configuration use the test DB.
# This happens before test modules import app.database.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# Apply existing migrations to the test database only.
alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
command.upgrade(alembic_config, "head")
