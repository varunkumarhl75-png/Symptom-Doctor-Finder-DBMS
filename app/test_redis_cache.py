import os
import re
import unittest
from unittest.mock import patch

from redis.exceptions import ConnectionError as RedisConnectionError

import cache
import search_service

os.environ.setdefault("FLASK_SECRET_KEY", "unit-test-only-secret")
import app as app_module


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expirations = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        if ex is not None:
            self.expirations[key] = ex
        return True

    def delete(self, key):
        existed = key in self.values
        self.values.pop(key, None)
        self.expirations.pop(key, None)
        return int(existed)

    def incr(self, key):
        value = int(self.values.get(key, "0")) + 1
        self.values[key] = str(value)
        return value

    def ping(self):
        return True


class FakeCursor:
    def __init__(self):
        self.executed = []
        self.rows = []

    def execute(self, query, parameters=None):
        self.executed.append((query, parameters))
        if "FROM symptom_search" in query:
            self.rows = [{
                "search_id": 17,
                "symptom_text": "Chest pain and shortness of breath"
            }]
        else:
            self.rows = [{
                "specialization": "Cardiology",
                "similarity_score": 0.94,
                "doctor_id": 3,
                "doctor_name": "Dr Demo",
                "qualification": "MD Cardiology",
                "experience_years": 12,
                "clinic_name": "Demo Clinic",
                "phone": "9000000000"
            }]

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class UnavailableRedis:
    def __getattr__(self, _name):
        raise RedisConnectionError("Redis is unavailable")


class RedisCacheTests(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()
        self.redis_patch = patch.object(
            cache,
            "get_redis_client",
            return_value=self.redis
        )
        self.redis_patch.start()
        self.addCleanup(self.redis_patch.stop)
        cache.reset_cache_stats()

    def test_connection_configuration_and_health_check(self):
        self.redis_patch.stop()
        try:
            with patch.dict(os.environ, {
                "REDIS_HOST": "redis.example.test",
                "REDIS_PORT": "6381",
                "REDIS_DB": "2",
                "REDIS_PASSWORD": "",
                "REDIS_CONNECT_TIMEOUT": "2.5",
                "REDIS_SOCKET_TIMEOUT": "3"
            }), patch.object(cache.redis, "Redis") as redis_constructor:
                with patch.object(cache, "_redis_client", None):
                    client = cache.get_redis_client()
        finally:
            self.redis_patch.start()

        self.assertIs(client, redis_constructor.return_value)
        redis_constructor.assert_called_once_with(
            host="redis.example.test",
            port=6381,
            db=2,
            password=None,
            socket_connect_timeout=2.5,
            socket_timeout=3.0,
            decode_responses=True
        )
        self.assertTrue(cache.redis_health())

    def test_symptom_search_miss_then_hit_and_doctor_results_are_cached(self):
        cursor = FakeCursor()
        with patch.object(
            search_service,
            "find_best_symptom",
            return_value={"index": 0, "similarity": 0.91}
        ) as semantic_search:
            first_match = search_service.get_symptom_match(
                cursor,
                "  Chest pain and shortness of breath  "
            )
            first_groups = search_service.get_doctor_groups(
                cursor,
                first_match["search_id"]
            )
            second_match = search_service.get_symptom_match(
                cursor,
                "chest pain and shortness of breath"
            )
            second_groups = search_service.get_doctor_groups(
                cursor,
                second_match["search_id"]
            )

        self.assertEqual(first_match, second_match)
        self.assertEqual(first_groups, second_groups)
        self.assertEqual(len(cursor.executed), 2)
        semantic_search.assert_called_once()
        self.assertEqual(cache.get_cache_stats()["hits"], 2)
        self.assertEqual(cache.get_cache_stats()["misses"], 2)

    def test_different_symptoms_use_different_keys(self):
        first = cache.build_cache_key(
            "symptom_search",
            {"query": cache.normalize_symptom_query("Chest pain")}
        )
        second = cache.build_cache_key(
            "symptom_search",
            {"query": cache.normalize_symptom_query("Knee pain")}
        )

        self.assertNotEqual(first, second)
        self.assertEqual(
            cache.normalize_symptom_query("  CHEST Pain  "),
            "chest pain"
        )

    def test_json_round_trip_and_ttl(self):
        expected = {"search_id": 8, "score": 0.876, "groups": []}
        with patch.dict(os.environ, {"REDIS_CACHE_TTL": "321"}):
            self.assertTrue(
                cache.set_cached_json("symptom_search", {"query": "test"}, expected)
            )
            actual = cache.get_cached_json("symptom_search", {"query": "test"})

        self.assertEqual(actual, expected)
        cache_key = next(
            key for key in self.redis.expirations if key.startswith("doctor_finder:symptom_search:")
        )
        self.assertEqual(self.redis.expirations[cache_key], 321)

    def test_cache_invalidation_uses_a_new_namespace_version(self):
        params = {"search_id": 17}
        cache.set_cached_json("doctor_search", params, [{"doctor_id": 3}])
        first_key = next(
            key for key in self.redis.values if key.startswith("doctor_finder:doctor_search:")
        )

        self.assertTrue(cache.invalidate_caches())
        self.assertIsNone(cache.get_cached_json("doctor_search", params))
        second_key = cache.build_cache_key("doctor_search", params, version="2")

        self.assertIn(first_key, self.redis.values)
        self.assertNotEqual(first_key, second_key)

    def test_redis_outage_does_not_block_search(self):
        cursor = FakeCursor()
        with patch.object(cache, "get_redis_client", return_value=UnavailableRedis()):
            with patch.object(
                search_service,
                "find_best_symptom",
                return_value={"index": 0, "similarity": 0.91}
            ):
                match = search_service.get_symptom_match(cursor, "chest pain")
                groups = search_service.get_doctor_groups(cursor, 17)

        self.assertEqual(match["status"], "matched")
        self.assertEqual(groups[0]["specialization"], "Cardiology")
        self.assertEqual(len(cursor.executed), 2)

    def test_flask_cache_endpoints_report_health_and_stats(self):
        app_module.app.config.update(TESTING=True)
        client = app_module.app.test_client()
        with patch.object(
            app_module,
            "get_cache_stats",
            return_value={
                "hits": 3,
                "misses": 1,
                "hit_ratio": 0.75,
                "redis_connected": True
            }
        ), patch.object(app_module, "redis_health", return_value=True):
            stats = client.get("/api/cache/stats")
            health = client.get("/api/cache/health")

        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.get_json()["hit_ratio"], 0.75)
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json()["status"], "healthy")

        with patch.object(app_module, "redis_health", return_value=False):
            unhealthy = client.get("/api/cache/health")
        self.assertEqual(unhealthy.status_code, 503)
        self.assertEqual(unhealthy.get_json()["status"], "unhealthy")

    def test_search_route_remains_available_when_redis_is_down(self):
        app_module.app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=False
        )
        with patch.object(cache, "get_redis_client", return_value=UnavailableRedis()):
            with patch.object(
                app_module,
                "get_db_connection",
                return_value=type("Connection", (), {
                    "cursor": lambda _self, **_kwargs: FakeCursor(),
                    "close": lambda _self: None
                })()
            ), patch.object(
                search_service,
                "find_best_symptom",
                return_value={"index": 0, "similarity": 0.91}
            ):
                response = app_module.app.test_client().post(
                    "/search",
                    data={"symptoms": "chest pain"}
                )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Doctor Search Results", response.data)

    def test_search_route_uses_cache_with_valid_csrf_session(self):
        app_module.app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=True
        )
        self.redis.values.clear()
        self.redis.expirations.clear()
        cache.reset_cache_stats()
        sql_calls = []

        class RouteConnection:
            def cursor(self, **_kwargs):
                return FakeCursor()

            def close(self):
                pass

        original_execute = FakeCursor.execute

        def record_execute(cursor, query, parameters=None):
            sql_calls.append(query)
            return original_execute(cursor, query, parameters)

        client = app_module.app.test_client()
        with patch.object(FakeCursor, "execute", record_execute), patch.object(
            app_module,
            "get_db_connection",
            side_effect=RouteConnection
        ), patch.object(
            search_service,
            "find_best_symptom",
            return_value={"index": 0, "similarity": 0.91}
        ) as semantic_search:
            home = client.get("/")
            token_match = re.search(
                rb'name="csrf_token" value="([^"]+)"',
                home.data
            )
            self.assertIsNotNone(token_match)
            csrf_token = token_match.group(1).decode("ascii")

            first = client.post(
                "/search",
                data={"symptoms": "Chest pain", "csrf_token": csrf_token}
            )
            after_first = cache.get_cache_stats()
            second = client.post(
                "/search",
                data={"symptoms": "  CHEST PAIN  ", "csrf_token": csrf_token}
            )
            after_second = cache.get_cache_stats()
            different = client.post(
                "/search",
                data={"symptoms": "Knee pain", "csrf_token": csrf_token}
            )
            after_different = cache.get_cache_stats()

        self.assertEqual(first.status_code, 200)
        self.assertIn(b"Doctor Search Results", first.data)
        self.assertEqual(second.status_code, 200)
        self.assertIn(b"Doctor Search Results", second.data)
        self.assertEqual(different.status_code, 200)
        self.assertIn(b"Doctor Search Results", different.data)
        self.assertEqual(after_first["misses"], 2)
        self.assertEqual(after_first["hits"], 0)
        self.assertEqual(after_second["misses"], 2)
        self.assertEqual(after_second["hits"], 2)
        self.assertEqual(after_different["misses"], 3)
        self.assertEqual(after_different["hits"], 3)
        self.assertEqual(len(sql_calls), 3)
        self.assertEqual(semantic_search.call_count, 2)

    def test_search_route_rejects_missing_csrf_token(self):
        app_module.app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=True
        )
        response = app_module.app.test_client().post(
            "/search",
            data={"symptoms": "Chest pain"}
        )

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
