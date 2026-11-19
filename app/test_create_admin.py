import os
import unittest
from unittest.mock import patch

import create_admin


class AdminCursor:
    def __init__(self):
        self.rows = []
        self.queries = []

    def execute(self, query, parameters=None):
        normalized = " ".join(query.lower().split())
        self.queries.append((normalized, parameters))
        if normalized.startswith("select get_lock"):
            self.rows = [(1,)]
        elif normalized.startswith("select user_id from auth_user"):
            self.rows = []
        elif normalized.startswith("select release_lock"):
            self.rows = [(1,)]
        elif normalized.startswith("insert into auth_user"):
            self.insert_parameters = parameters
        else:
            raise AssertionError("Unexpected SQL: " + normalized)

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def close(self):
        pass


class AdminConnection:
    def __init__(self):
        self.test_cursor = AdminCursor()
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.test_cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class CreateAdminTests(unittest.TestCase):
    def test_admin_creation_uses_separate_trusted_database_account(self):
        connection = AdminConnection()
        with (
            patch.dict(os.environ, {
                "DB_HOST": "localhost",
                "DB_PORT": "3306",
                "DB_USER": "sdf_app",
                "DB_NAME": "symptom_doctor_finder",
                "ADMIN_DB_USER": "sdf_admin_creator",
                "ADMIN_DB_PASSWORD": "trusted-test-password"
            }, clear=True),
            patch.object(create_admin.mysql.connector, "connect", return_value=connection) as connect,
            patch.object(create_admin, "prompt_input", return_value="admin@example.test"),
            patch.object(create_admin, "getpass", side_effect=["a-secure-password", "a-secure-password"])
        ):
            create_admin.main()

        connect.assert_called_once_with(
            host="localhost",
            port=3306,
            user="sdf_admin_creator",
            password="trusted-test-password",
            database="symptom_doctor_finder"
        )
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)
        query, parameters = next(
            item for item in connection.test_cursor.queries
            if item[0].startswith("insert into auth_user")
        )
        self.assertIn("'admin'", query)
        self.assertEqual(parameters[0], "admin@example.test")
        self.assertTrue(connection.test_cursor.queries[-1][0].startswith("select release_lock"))

    def test_admin_creation_requires_trusted_database_settings(self):
        with (
            patch.dict(os.environ, {"DB_NAME": "symptom_doctor_finder"}, clear=True),
            patch.object(create_admin.mysql.connector, "connect") as connect
        ):
            with self.assertRaises(SystemExit) as raised:
                create_admin.main()

        self.assertIn("ADMIN_DB_USER", str(raised.exception))
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
