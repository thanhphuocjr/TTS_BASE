"""Per-request CSV logger with daily rotation + N-day retention.

One row per request, even on error. Thread-safe.
"""
import csv
import datetime as _dt
import logging
import os
import threading
from typing import Optional

from config.settings import LOG_RETENTION_DAYS, LOGS_DIR, TIMEZONE_OFFSET_HOURS

logger = logging.getLogger(__name__)

VN_TZ = _dt.timezone(_dt.timedelta(hours=TIMEZONE_OFFSET_HOURS))

CSV_FIELDS = [
    "timestamp", "request_id", "model", "voice", "response_format",
    "input_length", "input_text", "normalized_text",
    "status_code", "ttfb_ms", "output_bytes", "error",
]

_csv_lock = threading.Lock()
_csv_current_date: Optional[str] = None
_csv_writer = None
_csv_file = None


def _csv_path_for(date_str: str) -> str:
    return os.path.join(LOGS_DIR, f"requests-{date_str}.csv")


def _prune_old_logs(max_days: int = LOG_RETENTION_DAYS) -> None:
    """Delete requests-*.csv / errors-*.log older than max_days."""
    cutoff = _dt.datetime.now(VN_TZ) - _dt.timedelta(days=max_days)
    try:
        for fname in os.listdir(LOGS_DIR):
            path = os.path.join(LOGS_DIR, fname)
            try:
                mtime = _dt.datetime.fromtimestamp(os.path.getmtime(path), tz=VN_TZ)
                if mtime < cutoff:
                    os.unlink(path)
            except OSError:
                pass
    except OSError:
        pass


def _get_writer():
    """Caller must hold _csv_lock."""
    global _csv_writer, _csv_file, _csv_current_date
    today = _dt.datetime.now(VN_TZ).strftime("%Y-%m-%d")
    if today == _csv_current_date and _csv_writer is not None:
        return _csv_writer
    if _csv_file is not None:
        try:
            _csv_file.close()
        except Exception:
            pass
    path = _csv_path_for(today)
    is_new = not os.path.isfile(path)
    _csv_file = open(path, "a", newline="", encoding="utf-8")
    _csv_writer = csv.DictWriter(_csv_file, fieldnames=CSV_FIELDS, extrasaction="ignore")
    if is_new:
        _csv_writer.writeheader()
        _csv_file.flush()
    _csv_current_date = today
    _prune_old_logs()
    return _csv_writer


def init() -> None:
    """Create the log dir + install a UTC+7 timestamp converter on logging."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    logging.Formatter.converter = lambda *args: _dt.datetime.now(VN_TZ).timetuple()


def log_request(row: dict) -> None:
    try:
        with _csv_lock:
            w = _get_writer()
            w.writerow(row)
            _csv_file.flush()
    except Exception as exc:
        logger.warning("CSV log write failed: %s", exc)


def log_error_text(msg: str) -> None:
    """Append a free-form error/traceback line to today's errors-*.log."""
    try:
        date = _dt.datetime.now(VN_TZ).strftime("%Y-%m-%d")
        path = os.path.join(LOGS_DIR, f"errors-{date}.log")
        stamp = _dt.datetime.now(VN_TZ).isoformat(timespec="milliseconds")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{stamp} {msg}\n")
    except Exception as exc:
        logger.warning("Error log write failed: %s", exc)


def now_iso() -> str:
    return _dt.datetime.now(VN_TZ).isoformat(timespec="milliseconds")
