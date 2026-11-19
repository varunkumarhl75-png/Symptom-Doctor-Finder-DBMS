from builtins import input as prompt_input
from getpass import getpass
import os
import re

import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash


load_dotenv()


def main():
    required_settings = ("ADMIN_DB_USER", "ADMIN_DB_PASSWORD", "DB_NAME")
    missing_settings = [
        setting for setting in required_settings if not os.getenv(setting)
    ]
    if missing_settings:
        raise SystemExit(
            "Missing trusted admin database settings: " + ", ".join(missing_settings)
        )

    email = prompt_input("Admin email: ").strip().lower()
    if len(email) > 150 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise SystemExit("Enter a valid email address.")

    password = getpass("Admin password (12-128 characters): ")
    confirmation = getpass("Confirm admin password: ")
    if not 12 <= len(password) <= 128:
        raise SystemExit("Password must be between 12 and 128 characters.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    try:
        connection = mysql.connector.connect(
            host=os.getenv("ADMIN_DB_HOST", os.getenv("DB_HOST", "localhost")),
            port=int(os.getenv("ADMIN_DB_PORT", os.getenv("DB_PORT", "3306"))),
            user=os.environ["ADMIN_DB_USER"],
            password=os.environ["ADMIN_DB_PASSWORD"],
            database=os.environ["DB_NAME"]
        )
    except (Error, ValueError) as error:
        raise SystemExit(
            "Trusted admin database connection failed (MySQL error {}).".format(
                getattr(error, "errno", "configuration")
            )
        ) from error

    cursor = connection.cursor()
    lock_acquired = False
    try:
        cursor.execute(
            "SELECT GET_LOCK(%s, 10)",
            ("symptom_doctor_finder:initial_admin",)
        )
        lock_result = cursor.fetchone()
        if not lock_result or lock_result[0] != 1:
            raise SystemExit("Could not acquire the initial-admin creation lock.")
        lock_acquired = True

        cursor.execute(
            "SELECT user_id FROM auth_user WHERE role = 'ADMIN' LIMIT 1"
        )
        if cursor.fetchone():
            raise SystemExit("An admin account already exists; refusing to create another.")

        cursor.execute(
            """
                INSERT INTO auth_user (email, password_hash, role, patient_id)
                VALUES (%s, %s, 'ADMIN', NULL)
            """,
            (email, generate_password_hash(password))
        )
        connection.commit()
        print("Initial admin account created.")
    except Error as error:
        connection.rollback()
        raise SystemExit(
            "Admin account creation failed (MySQL error {}).".format(
                getattr(error, "errno", "unknown")
            )
        ) from error
    finally:
        if lock_acquired:
            cursor.execute(
                "SELECT RELEASE_LOCK(%s)",
                ("symptom_doctor_finder:initial_admin",)
            )
        cursor.close()
        connection.close()


if __name__ == "__main__":
    main()
