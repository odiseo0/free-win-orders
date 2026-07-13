import json
import time
from hashlib import sha256
from pathlib import Path
from typing import Any


CACHE_BASE_DIR = Path("cache")
FILE_CACHE_TTL_SECONDS = 900


def _cache_path(namespace: str, key: str) -> Path:
    safe_namespace = namespace.strip() or "default"
    digest = sha256(key.encode("utf-8")).hexdigest()
    filename = f"{digest}.json"
    return CACHE_BASE_DIR / safe_namespace / filename


def load_cache_entry(namespace: str, key: str) -> Any | None:
    path = _cache_path(namespace, key)

    if not path.is_file():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    expires_at = data.get("expires_at")
    payload = data.get("payload")

    if not isinstance(expires_at, (int, float)):
        return None

    if expires_at <= time.time():
        return None

    return payload


def save_cache_entry(namespace: str, key: str, payload: Any) -> None:
    path = _cache_path(namespace, key)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "expires_at": time.time() + FILE_CACHE_TTL_SECONDS,
            "payload": payload,
        }
        path.write_text(json.dumps(record), encoding="utf-8")
    except Exception:
        return

