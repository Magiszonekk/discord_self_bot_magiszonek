import os
from datetime import datetime
from pathlib import Path
from threading import Lock

LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
LOG_FILE = LOG_DIR / os.getenv("LOG_FILE_NAME", "bot.log")
_LOG_LOCK = Lock()


def log(message: str, print_output: bool = False, level: str = "INFO") -> None:
    """
    Append a single log entry to the log file and mirror it to stdout.
    """

    # if print_output:
    #     print(message)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{timestamp} [{level.upper()}] {message}"
    if print_output:
        print(entry)
    with _LOG_LOCK:
        with LOG_FILE.open("a", encoding="utf-8") as fp:
            fp.write(entry + "\n")
