import os
from pathlib import Path
import sys


APP_DIRECTORY = Path(__file__).resolve().parent / "app"
sys.path.insert(0, str(APP_DIRECTORY))

import app as application


if __name__ == "__main__":
    application.app.run(
        host="127.0.0.1",
        debug=os.getenv("FLASK_DEBUG", "").strip().lower() == "true"
    )
