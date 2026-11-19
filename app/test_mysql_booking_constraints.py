import os
import threading
import unittest
import uuid

import mysql.connector


TEST_DATABASE = os.getenv("TEST_DB_NAME")
TEST_TABLE = "test_active_slot_" + uuid.uuid4().hex[:12]


@unittest.skipUnless(
    TEST_DATABASE,
    "Set TEST_DB_NAME to an isolated MySQL test database to run integration tests."
)
class MySQLBookingConstraintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if TEST_DATABASE == os.getenv("DB_NAME"):
            raise RuntimeError("TEST_DB_NAME must not be the application database.")
        if not TEST_DATABASE.startswith("test_"):
            raise RuntimeError("TEST_DB_NAME must begin with 'test_'.")

        cls.connection_options = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "3306")),
            "user": os.environ["DB_USER"],
            "password": os.environ["DB_PASSWORD"],
            "database": TEST_DATABASE
        }
        connection = mysql.connector.connect(**cls.connection_options)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                    CREATE TABLE `{}` (
                        appointment_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        slot_id BIGINT NOT NULL,
                        status VARCHAR(20) NOT NULL,
                        active_slot_id BIGINT
                            GENERATED ALWAYS AS (
                                CASE WHEN status = 'CANCELLED' THEN NULL ELSE slot_id END
                            ) STORED,
                        CONSTRAINT chk_test_appointment_status
                            CHECK (status IN ('BOOKED', 'COMPLETED', 'CANCELLED')),
                        UNIQUE KEY uq_test_active_slot (active_slot_id)
                    ) ENGINE=InnoDB
                """.format(TEST_TABLE)
            )
            connection.commit()
            cursor.close()
        finally:
            connection.close()

    @classmethod
    def tearDownClass(cls):
        if not TEST_DATABASE or not hasattr(cls, "connection_options"):
            return
        connection = mysql.connector.connect(**cls.connection_options)
        try:
            cursor = connection.cursor()
            cursor.execute("DROP TABLE `{}`".format(TEST_TABLE))
            connection.commit()
            cursor.close()
        finally:
            connection.close()

    def setUp(self):
        self.connection = mysql.connector.connect(**self.connection_options)
        self.cursor = self.connection.cursor()

    def tearDown(self):
        self.connection.rollback()
        self.cursor.close()
        self.connection.close()

    def insert_appointment(self, slot_id, status):
        self.cursor.execute(
            "INSERT INTO `{}` (slot_id, status) VALUES (%s, %s)".format(TEST_TABLE),
            (slot_id, status)
        )

    def test_cancelled_history_can_remain_while_slot_is_rebooked(self):
        self.insert_appointment(101, "CANCELLED")
        self.connection.commit()
        self.insert_appointment(101, "CANCELLED")
        self.connection.commit()
        self.insert_appointment(101, "BOOKED")
        self.connection.commit()

        self.cursor.execute(
            "SELECT status, COUNT(*) FROM `{}` WHERE slot_id = %s GROUP BY status".format(TEST_TABLE),
            (101,)
        )
        self.assertEqual(
            dict(self.cursor.fetchall()),
            {"CANCELLED": 2, "BOOKED": 1}
        )

    def test_completed_appointment_reserves_slot(self):
        self.insert_appointment(102, "COMPLETED")
        self.connection.commit()

        with self.assertRaises(mysql.connector.IntegrityError):
            self.insert_appointment(102, "BOOKED")
        self.connection.rollback()

    def test_failed_booking_transaction_rolls_back(self):
        self.insert_appointment(103, "BOOKED")
        self.connection.rollback()

        self.cursor.execute(
            "SELECT COUNT(*) FROM `{}` WHERE slot_id = %s".format(TEST_TABLE),
            (103,)
        )
        self.assertEqual(self.cursor.fetchone()[0], 0)

    def test_concurrent_active_inserts_allow_only_one_winner(self):
        barrier = threading.Barrier(2)
        outcomes = []
        outcome_lock = threading.Lock()

        def book():
            connection = mysql.connector.connect(**self.connection_options)
            cursor = connection.cursor()
            try:
                connection.start_transaction()
                barrier.wait(timeout=10)
                cursor.execute(
                    "INSERT INTO `{}` (slot_id, status) VALUES (%s, 'BOOKED')".format(TEST_TABLE),
                    (104,)
                )
                connection.commit()
                outcome = "committed"
            except mysql.connector.IntegrityError:
                connection.rollback()
                outcome = "rejected"
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()
                connection.close()
            with outcome_lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=book) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertCountEqual(outcomes, ["committed", "rejected"])
        self.cursor.execute(
            "SELECT COUNT(*) FROM `{}` WHERE slot_id = %s AND status <> 'CANCELLED'".format(TEST_TABLE),
            (104,)
        )
        self.assertEqual(self.cursor.fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
