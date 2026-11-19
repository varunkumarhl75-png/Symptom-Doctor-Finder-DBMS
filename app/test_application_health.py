import os
import unittest
from unittest.mock import patch

os.environ.setdefault("FLASK_SECRET_KEY", "unit-test-only-secret")
import app as app_module


class HealthCursor:
    def __init__(self, value=1, error=None):
        self.value = value
        self.error = error

    def execute(self, query):
        if query != "SELECT 1":
            raise AssertionError("Unexpected health query.")
        if self.error:
            raise self.error

    def fetchone(self):
        return (self.value,)

    def close(self):
        pass


class HealthConnection:
    def __init__(self, cursor):
        self.test_cursor = cursor
        self.closed = False

    def cursor(self):
        return self.test_cursor

    def close(self):
        self.closed = True


class ApplicationHealthTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_health_reports_mysql_and_redis_independently_when_healthy(self):
        connection = HealthConnection(HealthCursor())
        with patch.object(
            app_module,
            "get_db_connection",
            return_value=connection
        ), patch.object(app_module, "redis_health", return_value=True):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "status": "healthy",
            "mysql": "connected",
            "redis": "connected"
        })
        self.assertTrue(connection.closed)

    def test_redis_failure_does_not_report_mysql_as_unavailable(self):
        with patch.object(
            app_module,
            "get_db_connection",
            return_value=HealthConnection(HealthCursor())
        ), patch.object(app_module, "redis_health", return_value=False):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["mysql"], "connected")
        self.assertEqual(response.get_json()["redis"], "disconnected")

    def test_mysql_failure_does_not_report_redis_as_unavailable(self):
        with patch.object(
            app_module,
            "get_db_connection",
            return_value=None
        ), patch.object(app_module, "redis_health", return_value=True):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["mysql"], "disconnected")
        self.assertEqual(response.get_json()["redis"], "connected")

    def test_mysql_query_failure_does_not_expose_database_error(self):
        connection = HealthConnection(
            HealthCursor(error=app_module.Error(msg="private connection detail", errno=1045))
        )
        with patch.object(
            app_module,
            "get_db_connection",
            return_value=connection
        ), patch.object(app_module, "redis_health", return_value=True):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["mysql"], "disconnected")
        self.assertNotIn(b"private connection detail", response.data)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
