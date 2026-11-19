import logging
import os

import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error


load_dotenv()
logger = logging.getLogger(__name__)


def get_db_connection():
    required_settings = ("DB_USER", "DB_NAME")
    missing_settings = [
        setting for setting in required_settings if not os.getenv(setting)
    ]
    if "DB_PASSWORD" not in os.environ:
        missing_settings.append("DB_PASSWORD")
    if missing_settings:
        logger.error(
            "Database configuration is missing required environment settings: %s",
            ", ".join(missing_settings)
        )
        return None

    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            database=os.environ["DB_NAME"]
        )
    except (Error, ValueError) as error:
        error_code = getattr(error, "errno", None)
        logger.error(
            "Database connection failed (MySQL error %s).",
            error_code if error_code is not None else "configuration"
        )
        return None
