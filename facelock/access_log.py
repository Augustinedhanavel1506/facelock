import json
import time
from datetime import datetime

from . import config

_PATH = config.DATA_DIR / "access_log.jsonl"


def log_event(event: str, name: str = None, method: str = None):
    """event: 'granted' | 'denied'. method: 'face' | 'pin'."""
    entry = {
        "ts": time.time(),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event": event,
        "name": name,
        "method": method,
    }
    with open(_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def read_recent(limit: int = 100):
    if not _PATH.exists():
        return []
    lines = [l for l in _PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    entries = [json.loads(l) for l in lines[-limit:]]
    entries.reverse()
    return entries
