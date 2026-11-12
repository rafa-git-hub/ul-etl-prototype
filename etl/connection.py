import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg

ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_PATH)


def get_connection() -> psycopg.Connection:
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "deals_bigdata"),
        user=os.getenv("POSTGRES_USER", "ul"),
        password=os.getenv("POSTGRES_PASSWORD", "ul_secret"),
    )