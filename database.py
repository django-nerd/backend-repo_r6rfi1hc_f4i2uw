"""
Database Helper Functions with Fallback

Primary: MongoDB via environment variables DATABASE_URL and DATABASE_NAME
Fallback: Mongita (embedded, file-based MongoDB-compatible client) when env vars
          are not provided. This enables the app to run without external DB.
"""

from datetime import datetime, timezone
import os
from typing import Union

from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file (if present)
load_dotenv()

_client = None
db = None

# Try primary MongoDB via env vars
DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME")

try:
    if DATABASE_URL and DATABASE_NAME:
        from pymongo import MongoClient  # type: ignore
        _client = MongoClient(DATABASE_URL)
        db = _client[DATABASE_NAME]
    else:
        # Fallback to Mongita (embedded MongoDB-like client)
        from mongita import MongitaClientDisk  # type: ignore
        _client = MongitaClientDisk()
        db = _client[os.getenv("FALLBACK_DATABASE_NAME", "solo_leveling_fitness")]  # local file-based DB
except Exception as e:
    # As an ultimate fallback, try Mongita in-memory so the API stays usable
    try:
        from mongita import MongitaClientMemory  # type: ignore
        _client = MongitaClientMemory()
        db = _client["solo_leveling_fitness_runtime"]
    except Exception:
        db = None


# Helper functions for common database operations

def create_document(collection_name: str, data: Union[BaseModel, dict]):
    """Insert a single document with timestamps. Returns inserted id (str)."""
    if db is None:
        raise Exception(
            "Database not available. Ensure DATABASE_URL & DATABASE_NAME are set or fallback is working."
        )

    # Convert Pydantic model to dict if needed
    if isinstance(data, BaseModel):
        data_dict = data.model_dump()
    else:
        # Copy to avoid mutating caller's data
        data_dict = dict(data)

    now = datetime.now(timezone.utc)
    data_dict.setdefault("created_at", now)
    data_dict["updated_at"] = now

    result = db[collection_name].insert_one(data_dict)
    inserted_id = getattr(result, "inserted_id", None)
    return str(inserted_id) if inserted_id is not None else None


def get_documents(collection_name: str, filter_dict: dict | None = None, limit: int | None = None):
    """Get documents from collection as a list."""
    if db is None:
        raise Exception(
            "Database not available. Ensure DATABASE_URL & DATABASE_NAME are set or fallback is working."
        )

    cursor = db[collection_name].find(filter_dict or {})
    if limit:
        cursor = cursor.limit(limit)
    return list(cursor)
