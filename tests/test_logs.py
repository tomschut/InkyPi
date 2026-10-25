"""Log file fallback for log downloads without a systemd journal (Docker / HAOS add-on)."""
from datetime import datetime, timedelta
import logging
import sys
from pathlib import Path

from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from utils import log_file
from blueprints import settings


def write_log(path, lines):
    path.write_text("".join(f"{line}\n" for line in lines))


def stamp(dt):
    return dt.strftime(log_file.TIMESTAMP_FORMAT)


def test_read_logs_since_filters_by_time_and_keeps_tracebacks(tmp_path):
    now = datetime.now()
    log = tmp_path / "inkypi.log"
    write_log(Path(f"{log}.1"), [f"{stamp(now - timedelta(hours=30))} - INFO - old - too old"])
    write_log(log, [
        f"{stamp(now - timedelta(hours=25))} - ERROR - old - also too old",
        "Traceback (most recent call last):",
        f"{stamp(now - timedelta(hours=1))} - ERROR - plugin - recent failure",
        "Traceback (most recent call last):",
        '  File "screenshot.py", line 1',
    ])
    lines = log_file.read_logs_since(now - timedelta(hours=24), str(log))
    assert [line.rstrip("\n") for line in lines] == [
        f"{stamp(now - timedelta(hours=1))} - ERROR - plugin - recent failure",
        "Traceback (most recent call last):",
        '  File "screenshot.py", line 1',
    ]


def test_setup_file_logging_writes_parseable_lines(tmp_path, monkeypatch):
    log = tmp_path / "logs" / "inkypi.log"
    monkeypatch.setattr(logging.getLogger(), "level", logging.INFO)  # as set by config/logging.conf
    handler = log_file.setup_file_logging(str(log))
    try:
        logging.getLogger("test_logs").info("hello from the add-on")
        handler.flush()
    finally:
        logging.getLogger().removeHandler(handler)
        handler.close()
    lines = log_file.read_logs_since(datetime.now() - timedelta(minutes=1), str(log))
    assert any("INFO - test_logs - hello from the add-on" in line for line in lines)


def test_download_logs_uses_log_file_without_journal(tmp_path, monkeypatch):
    log = tmp_path / "inkypi.log"
    write_log(log, [f"{stamp(datetime.now())} - INFO - inkypi - visible in download"])
    monkeypatch.setattr(settings, "JOURNAL_AVAILABLE", False)
    monkeypatch.setattr(settings, "read_logs_since", lambda since: log_file.read_logs_since(since, str(log)))
    app = Flask(__name__)
    app.register_blueprint(settings.settings_bp)
    response = app.test_client().get("/download-logs?hours=24")
    assert response.status_code == 200
    assert "visible in download" in response.get_data(as_text=True)
    assert "attachment; filename=inkypi_" in response.headers["Content-Disposition"]
