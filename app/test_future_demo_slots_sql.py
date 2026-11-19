import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FutureDemoSlotScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = (
            PROJECT_ROOT / "database" / "14_seed_future_demo_slots.sql"
        ).read_text(encoding="utf-8")
        cls.schema = (
            PROJECT_ROOT / "database" / "01_schema.sql"
        ).read_text(encoding="utf-8")

    def test_script_generates_only_the_next_thirty_days(self):
        self.assertIn("CURRENT_DATE + INTERVAL 1 DAY", self.script)
        self.assertIn("CURRENT_DATE + INTERVAL 30 DAY", self.script)
        self.assertIn("WEEKDAY(future_dates.slot_date)", self.script)
        self.assertIn("BETWEEN '2026-10-05' AND '2026-10-09'", self.script)

    def test_script_is_idempotent_and_does_not_modify_appointments(self):
        self.assertIn("WHERE NOT EXISTS", self.script)
        self.assertIn(
            "UNIQUE (doctor_id, slot_date, start_time, end_time)",
            self.schema
        )
        self.assertNotIn("UPDATE APPOINTMENT", self.script.upper())
        self.assertNotIn("DELETE FROM", self.script.upper())


if __name__ == "__main__":
    unittest.main()
