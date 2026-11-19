import argparse
import time

from cache import (
    delete_cache_entry,
    get_cache_stats,
    normalize_symptom_query
)
from db import get_db_connection
from search_service import (
    get_doctor_groups,
    get_symptom_match,
    query_doctor_groups,
    query_symptom_match
)


class TimedCursor:
    def __init__(self, cursor):
        self.cursor = cursor
        self.query_count = 0
        self.mysql_seconds = 0.0
        self._query_started = None

    def execute(self, query, parameters=None):
        self.query_count += 1
        self._query_started = time.perf_counter()
        if parameters is None:
            return self.cursor.execute(query)
        return self.cursor.execute(query, parameters)

    def fetchall(self):
        rows = self.cursor.fetchall()
        if self._query_started is not None:
            self.mysql_seconds += time.perf_counter() - self._query_started
            self._query_started = None
        return rows

    def close(self):
        self.cursor.close()


def load_search(cursor, query, cached):
    if cached:
        match = get_symptom_match(cursor, query)
    else:
        match = query_symptom_match(cursor, query)

    if match["status"] != "matched":
        raise RuntimeError(
            "The query did not match a stored symptom. Choose a query with a clear semantic match."
        )

    if cached:
        groups = get_doctor_groups(cursor, match["search_id"])
    else:
        groups = query_doctor_groups(cursor, match["search_id"])
    return match, groups


def main():
    parser = argparse.ArgumentParser(
        description="Measure the existing symptom search with and without Redis."
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="Chest tightness and shortness of breath while walking"
    )
    args = parser.parse_args()

    connection = get_db_connection()
    if not connection:
        raise RuntimeError("Could not connect to MySQL; check the local DB configuration.")

    query = args.query.strip()
    normalized_query = normalize_symptom_query(query)
    baseline_cursor = TimedCursor(connection.cursor(dictionary=True))
    try:
        started = time.perf_counter()
        match, _ = load_search(baseline_cursor, query, cached=False)
        mysql_only_seconds = baseline_cursor.mysql_seconds
        baseline_seconds = time.perf_counter() - started
    finally:
        baseline_cursor.close()

    # Remove only this query's entries so the demo measures a cold miss without
    # flushing other application or Redis data.
    delete_cache_entry("symptom_search", {"query": normalized_query})
    delete_cache_entry("doctor_search", {"search_id": match["search_id"]})

    before_cold = get_cache_stats()
    if not before_cold["redis_connected"]:
        connection.close()
        raise RuntimeError("Redis is unavailable; the cache performance run was not measured.")

    cold_cursor = TimedCursor(connection.cursor(dictionary=True))
    try:
        started = time.perf_counter()
        load_search(cold_cursor, query, cached=True)
        cold_seconds = time.perf_counter() - started
        cold_queries = cold_cursor.query_count
        cold_mysql_seconds = cold_cursor.mysql_seconds
    finally:
        cold_cursor.close()
    after_cold = get_cache_stats()

    before_warm = get_cache_stats()
    warm_cursor = TimedCursor(connection.cursor(dictionary=True))
    try:
        started = time.perf_counter()
        load_search(warm_cursor, query, cached=True)
        warm_seconds = time.perf_counter() - started
        warm_queries = warm_cursor.query_count
    finally:
        warm_cursor.close()
        connection.close()
    after_warm = get_cache_stats()

    cold_misses = after_cold["misses"] - before_cold["misses"]
    warm_hits = after_warm["hits"] - before_warm["hits"]
    if cold_misses < 2:
        raise RuntimeError(
            "Cold-cache measurement did not produce both expected cache misses."
        )
    if warm_hits < 2 or warm_queries != 0:
        raise RuntimeError(
            "Warm-cache measurement did not hit both cached search stages."
        )

    print("Query: {0}".format(query))
    print(
        "Redis connectivity during measurements: {0}".format(
            "connected" if after_warm["redis_connected"] else "unavailable"
        )
    )
    print(
        "Uncached MySQL + semantic search: {0:.3f} ms "
        "({1} MySQL queries; MySQL execute/fetch: {2:.3f} ms)".format(
            baseline_seconds * 1000,
            baseline_cursor.query_count,
            mysql_only_seconds * 1000
        )
    )
    print(
        "Redis-backed cold miss: {0:.3f} ms "
        "({1} MySQL queries; MySQL execute/fetch: {2:.3f} ms; "
        "cache misses: {3})".format(
            cold_seconds * 1000,
            cold_queries,
            cold_mysql_seconds * 1000,
            cold_misses
        )
    )
    print(
        "Redis-backed warm hit: {0:.3f} ms "
        "({1} MySQL queries; cache hits: {2})".format(
            warm_seconds * 1000,
            warm_queries,
            warm_hits
        )
    )
    print(
        "Repeated MySQL queries avoided: {0}".format(
            baseline_cursor.query_count - warm_queries
        )
    )


if __name__ == "__main__":
    main()
