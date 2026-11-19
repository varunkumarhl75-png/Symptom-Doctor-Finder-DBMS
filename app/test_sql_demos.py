from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SqlDemonstrationTests(unittest.TestCase):
    def test_dml_demo_operates_only_on_a_temporary_table(self):
        script = (
            PROJECT_ROOT / "database" / "18_dml_demo.sql"
        ).read_text(encoding="utf-8").upper()

        self.assertIn("CREATE TEMPORARY TABLE DML_DEMO_SAMPLE", script)
        self.assertIn("INSERT INTO DML_DEMO_SAMPLE", script)
        self.assertIn("SELECT SAMPLE_ID", script)
        self.assertIn("UPDATE DML_DEMO_SAMPLE", script)
        self.assertIn("DELETE FROM DML_DEMO_SAMPLE", script)
        self.assertIn("DROP TEMPORARY TABLE DML_DEMO_SAMPLE", script)
        self.assertNotIn("INSERT INTO PATIENT", script)
        self.assertNotIn("UPDATE APPOINTMENT", script)
        self.assertNotIn("DELETE FROM APPOINTMENT", script)

    def test_recursive_cte_demo_is_a_select_and_has_a_bounded_recursion(self):
        script = (
            PROJECT_ROOT / "database" / "19_recursive_cte_demo.sql"
        ).read_text(encoding="utf-8").upper()

        self.assertIn("WITH RECURSIVE CALENDAR_DATES", script)
        self.assertIn("SELECT CURRENT_DATE", script)
        self.assertIn("SELECT SLOT_DATE + INTERVAL 1 DAY", script)
        self.assertIn("SLOT_DATE < CURRENT_DATE + INTERVAL 6 DAY", script)
        self.assertIn("NOT EXISTS", script)
        self.assertNotIn("INSERT INTO", script)
        self.assertNotIn("UPDATE ", script)
        self.assertNotIn("DELETE FROM", script)

    def test_only_age_function_is_declared_non_deterministic(self):
        script = (
            PROJECT_ROOT / "database" / "10_functions.sql"
        ).read_text(encoding="utf-8").upper()
        age_body = script.split("CREATE FUNCTION CALCULATE_AGE", 1)[1].split(
            "END $$", 1
        )[0]
        other_functions = (
            script.split("CREATE FUNCTION GET_EXPERIENCE_CATEGORY", 1)[1]
            .split("CREATE FUNCTION CALCULATE_AGE", 1)[0]
            + script.split("CREATE FUNCTION GET_SIMILARITY_CATEGORY", 1)[1]
        )

        self.assertIn("CURDATE()", age_body)
        self.assertIn("NOT DETERMINISTIC", age_body)
        self.assertNotIn("NOT DETERMINISTIC", other_functions)
        self.assertEqual(other_functions.count("DETERMINISTIC"), 2)


if __name__ == "__main__":
    unittest.main()
