import hashlib
import json
import logging
import os
import threading

import redis
from redis.exceptions import RedisError


logger = logging.getLogger(__name__)

_CACHE_VERSION_KEY = "doctor_finder:cache_version"
_DEFAULT_TTL = 300
_redis_client = None
_client_lock = threading.Lock()
_stats_lock = threading.Lock()
_stats = {"hits": 0, "misses": 0}


def get_redis_client():
    global _redis_client
    if _redis_client is None:
        with _client_lock:
            if _redis_client is None:
                _redis_client = redis.Redis(
                    host=os.getenv("REDIS_HOST", "localhost"),
                    port=int(os.getenv("REDIS_PORT", "6379")),
                    db=int(os.getenv("REDIS_DB", "0")),
                    password=os.getenv("REDIS_PASSWORD") or None,
                    socket_connect_timeout=float(
                        os.getenv("REDIS_CONNECT_TIMEOUT", "1")
                    ),
                    socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT", "1")),
                    decode_responses=True
                )
    return _redis_client


def normalize_symptom_query(query):
    return query.strip().casefold()


def build_cache_key(namespace, parameters, version="1"):
    serialized = json.dumps(
        parameters,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False
    )
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return "doctor_finder:{0}:v{1}:{2}".format(namespace, version, digest)


def _cache_version(client):
    version = client.get(_CACHE_VERSION_KEY)
    if version is None:
        client.set(_CACHE_VERSION_KEY, "1", nx=True)
        version = client.get(_CACHE_VERSION_KEY)
    return version or "1"


def _record_result(result):
    with _stats_lock:
        _stats["hits" if result else "misses"] += 1


def reset_cache_stats():
    with _stats_lock:
        _stats.update(hits=0, misses=0)


def _log_cache_failure(operation, error):
    logger.warning("Redis cache %s failed: %s", operation, error)


def get_cached_json(namespace, parameters):
    try:
        client = get_redis_client()
        key = build_cache_key(namespace, parameters, _cache_version(client))
        value = client.get(key)
    except (RedisError, OSError, TypeError, ValueError) as error:
        _record_result(False)
        _log_cache_failure("read", error)
        return None

    if value is None:
        _record_result(False)
        return None

    try:
        result = json.loads(value)
    except (json.JSONDecodeError, TypeError) as error:
        _record_result(False)
        _log_cache_failure("deserialization", error)
        try:
            client.delete(key)
        except (RedisError, OSError, TypeError, ValueError) as delete_error:
            _log_cache_failure("delete corrupt entry", delete_error)
        return None

    _record_result(True)
    return result


def _get_cache_ttl():
    try:
        ttl = int(os.getenv("REDIS_CACHE_TTL", str(_DEFAULT_TTL)))
        if ttl <= 0:
            raise ValueError("REDIS_CACHE_TTL must be a positive integer")
        return ttl
    except ValueError as error:
        logger.warning(
            "Invalid Redis cache TTL; using %s seconds: %s",
            _DEFAULT_TTL,
            error
        )
        return _DEFAULT_TTL


def set_cached_json(namespace, parameters, value):
    try:
        client = get_redis_client()
        key = build_cache_key(namespace, parameters, _cache_version(client))
        client.set(
            key,
            json.dumps(value, separators=(",", ":"), ensure_ascii=False),
            ex=_get_cache_ttl()
        )
        return True
    except (RedisError, OSError, TypeError, ValueError) as error:
        _log_cache_failure("write", error)
        return False


def delete_cache_entry(namespace, parameters):
    try:
        client = get_redis_client()
        key = build_cache_key(namespace, parameters, _cache_version(client))
        return bool(client.delete(key))
    except (RedisError, OSError, TypeError, ValueError) as error:
        _log_cache_failure("delete entry", error)
        return False


def invalidate_caches():
    """Advance the cache namespace; old entries expire naturally by TTL."""
    try:
        client = get_redis_client()
        _cache_version(client)
        client.incr(_CACHE_VERSION_KEY)
        return True
    except (RedisError, OSError, TypeError, ValueError) as error:
        _log_cache_failure("invalidation", error)
        return False


def redis_health():
    try:
        return bool(get_redis_client().ping())
    except (RedisError, OSError, TypeError, ValueError) as error:
        _log_cache_failure("health check", error)
        return False


def get_cache_stats():
    with _stats_lock:
        hits = _stats["hits"]
        misses = _stats["misses"]

    total = hits + misses
    return {
        "hits": hits,
        "misses": misses,
        "hit_ratio": hits / total if total else 0.0,
        "redis_connected": redis_health()
    }
