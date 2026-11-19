"""Short-lived, non-sensitive Redis CRUD example kept separate from app caches."""

import json
import os
import uuid

from cache import get_redis_client


_DEMO_KEY_PREFIX = "doctor_finder:demo:crud:"


def _record_key(record_id):
    normalized_id = str(uuid.UUID(str(record_id)))
    return _DEMO_KEY_PREFIX + normalized_id


def _ttl_seconds(ttl=None):
    value = int(ttl if ttl is not None else os.getenv("REDIS_CACHE_TTL", "300"))
    if value <= 0:
        raise ValueError("Redis demo TTL must be a positive number of seconds.")
    return value


def create_demo_record(record_id, value, ttl=None):
    """Create one demo record without overwriting an existing key."""
    return bool(get_redis_client().set(
        _record_key(record_id),
        json.dumps(value, separators=(",", ":"), ensure_ascii=False),
        ex=_ttl_seconds(ttl),
        nx=True
    ))


def read_demo_record(record_id):
    """Return a decoded record, or None when it is missing or expired."""
    value = get_redis_client().get(_record_key(record_id))
    return None if value is None else json.loads(value)


def update_demo_record(record_id, value, ttl=None):
    """Update an existing demo record and refresh its expiry."""
    return bool(get_redis_client().set(
        _record_key(record_id),
        json.dumps(value, separators=(",", ":"), ensure_ascii=False),
        ex=_ttl_seconds(ttl),
        xx=True
    ))


def delete_demo_record(record_id):
    """Delete only the single namespaced key represented by this UUID."""
    return bool(get_redis_client().delete(_record_key(record_id)))


def main():
    record_id = str(uuid.uuid4())
    initial_record = {
        "kind": "demo_search_preference",
        "label": "sample appointment reminders",
        "enabled": False
    }
    updated_record = {**initial_record, "enabled": True}

    if not create_demo_record(record_id, initial_record):
        raise RuntimeError("The generated Redis demo key already exists.")
    print("CREATE:", read_demo_record(record_id))
    print("READ:", read_demo_record(record_id))

    if not update_demo_record(record_id, updated_record):
        raise RuntimeError("The Redis demo record disappeared before UPDATE.")
    print("UPDATE:", read_demo_record(record_id))

    if not delete_demo_record(record_id):
        raise RuntimeError("The Redis demo record disappeared before DELETE.")
    print("DELETE: record removed; final read =", read_demo_record(record_id))


if __name__ == "__main__":
    main()
