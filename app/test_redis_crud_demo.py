import time
import unittest
from unittest.mock import patch
import uuid

from redis.exceptions import ConnectionError as RedisConnectionError

import redis_crud_demo


class ExpiringRedis:
    def __init__(self):
        self.values = {}
        self.expires_at = {}

    def _expire(self, key):
        expiry = self.expires_at.get(key)
        if expiry is not None and expiry <= time.monotonic():
            self.values.pop(key, None)
            self.expires_at.pop(key, None)

    def get(self, key):
        self._expire(key)
        return self.values.get(key)

    def set(self, key, value, ex=None, nx=False, xx=False):
        self._expire(key)
        exists = key in self.values
        if (nx and exists) or (xx and not exists):
            return None
        self.values[key] = value
        if ex is not None:
            self.expires_at[key] = time.monotonic() + ex
        else:
            self.expires_at.pop(key, None)
        return True

    def delete(self, key):
        self._expire(key)
        existed = key in self.values
        self.values.pop(key, None)
        self.expires_at.pop(key, None)
        return int(existed)


class RedisCrudDemoTests(unittest.TestCase):
    def setUp(self):
        self.redis = ExpiringRedis()
        self.client_patch = patch.object(
            redis_crud_demo,
            "get_redis_client",
            return_value=self.redis
        )
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)
        self.record_id = str(uuid.uuid4())

    def test_create_read_update_and_delete_use_only_demo_namespace(self):
        initial = {"label": "sample", "enabled": False}
        updated = {"label": "sample", "enabled": True}
        unrelated_key = "doctor_finder:symptom_search:unrelated"
        self.redis.set(unrelated_key, '{"keep":true}', ex=300)

        self.assertTrue(
            redis_crud_demo.create_demo_record(self.record_id, initial, ttl=30)
        )
        demo_key = next(
            key for key in self.redis.values
            if key.startswith("doctor_finder:demo:crud:")
        )
        self.assertEqual(self.redis.expires_at[demo_key] - time.monotonic(), 30)
        self.assertEqual(redis_crud_demo.read_demo_record(self.record_id), initial)
        self.assertFalse(
            redis_crud_demo.create_demo_record(self.record_id, updated, ttl=30)
        )

        self.assertTrue(
            redis_crud_demo.update_demo_record(self.record_id, updated, ttl=45)
        )
        self.assertEqual(redis_crud_demo.read_demo_record(self.record_id), updated)
        self.assertGreater(self.redis.expires_at[demo_key] - time.monotonic(), 44)

        self.assertTrue(redis_crud_demo.delete_demo_record(self.record_id))
        self.assertIsNone(redis_crud_demo.read_demo_record(self.record_id))
        self.assertFalse(redis_crud_demo.delete_demo_record(self.record_id))
        self.assertEqual(self.redis.get(unrelated_key), '{"keep":true}')

    def test_read_update_and_delete_of_missing_record_are_safe(self):
        self.assertIsNone(redis_crud_demo.read_demo_record(self.record_id))
        self.assertFalse(
            redis_crud_demo.update_demo_record(self.record_id, {"enabled": True})
        )
        self.assertFalse(redis_crud_demo.delete_demo_record(self.record_id))

    def test_expired_demo_record_is_read_as_missing(self):
        self.assertTrue(
            redis_crud_demo.create_demo_record(
                self.record_id,
                {"temporary": True},
                ttl=1
            )
        )
        time.sleep(1.05)

        self.assertIsNone(redis_crud_demo.read_demo_record(self.record_id))
        self.assertFalse(
            redis_crud_demo.update_demo_record(self.record_id, {"temporary": False})
        )

    def test_invalid_key_and_ttl_are_rejected(self):
        with self.assertRaises(ValueError):
            redis_crud_demo.read_demo_record("not-a-uuid")
        with self.assertRaises(ValueError):
            redis_crud_demo.create_demo_record(self.record_id, {}, ttl=0)

    def test_redis_unavailability_is_reported_to_the_demo_caller(self):
        unavailable = type(
            "UnavailableRedis",
            (),
            {
                "set": lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    RedisConnectionError("Redis unavailable")
                )
            }
        )()
        with patch.object(
            redis_crud_demo,
            "get_redis_client",
            return_value=unavailable
        ):
            with self.assertRaises(RedisConnectionError):
                redis_crud_demo.create_demo_record(self.record_id, {"safe": True})


if __name__ == "__main__":
    unittest.main()
