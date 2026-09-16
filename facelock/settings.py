import json

from . import config

DEFAULTS = {
    "idle_lock_enabled": False,
    "idle_lock_minutes": 5,
    "walkaway_lock_enabled": False,
    "walkaway_lock_minutes": 3,
    "voice_enabled": True,
}

_PATH = config.DATA_DIR / "settings.json"


def load() -> dict:
    data = {}
    if _PATH.exists():
        try:
            data = json.loads(_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in data.items() if k in DEFAULTS})
    return merged


def save(current: dict):
    _PATH.write_text(json.dumps(current, indent=2))
