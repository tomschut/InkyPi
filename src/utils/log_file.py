"""Rotating log file, used for log downloads when the systemd journal is unavailable (e.g. Docker / HAOS add-on)."""
from datetime import datetime
from logging.handlers import RotatingFileHandler
import logging
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_FILE = os.getenv("INKYPI_LOG_FILE", os.path.join(BASE_DIR, "logs", "inkypi.log"))
MAX_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 3
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_file_logging(log_file=LOG_FILE):
    """Attach a rotating file handler to the root logger. Never fails startup."""
    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        handler = RotatingFileHandler(log_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT)
    except OSError as e:
        logging.getLogger(__name__).warning(f"File logging disabled, cannot write {log_file}: {e}")
        return None
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s", TIMESTAMP_FORMAT))
    logging.getLogger().addHandler(handler)
    return handler


def read_logs_since(since, log_file=LOG_FILE):
    """Return log lines written at or after `since`, oldest first.

    Lines without a timestamp (tracebacks, chromium output) belong to the record before them.
    """
    files = [f"{log_file}.{i}" for i in range(BACKUP_COUNT, 0, -1)] + [log_file]
    lines, include = [], False
    for path in files:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    include = datetime.strptime(line[:19], TIMESTAMP_FORMAT) >= since
                except ValueError:
                    pass
                if include:
                    lines.append(line)
    return lines
