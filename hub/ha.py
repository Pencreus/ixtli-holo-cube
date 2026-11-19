"""Tiny Home Assistant REST helper (read-only; never calls actuating services)."""
import os
import httpx

HA_URL = os.environ.get("HA_URL", "http://10.0.0.190:8123")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
_H = {"Authorization": f"Bearer {HA_TOKEN}"}


def state(entity_id):
    """Return {'state': str, 'attributes': dict} or None when missing/unreachable."""
    try:
        r = httpx.get(f"{HA_URL}/api/states/{entity_id}", headers={"Authorization": f"Bearer {os.environ.get('HA_TOKEN', '')}"}, timeout=6)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def value(entity_id, default=None):
    s = state(entity_id)
    if not s or s["state"] in ("unavailable", "unknown", "None"):
        return default
    return s["state"]


def number(entity_id, default=None):
    v = value(entity_id)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def forecast(entity_id, kind="daily"):
    """Read-only weather forecast (service call that only returns data)."""
    try:
        r = httpx.post(f"{HA_URL}/api/services/weather/get_forecasts?return_response",
                       headers={"Authorization": f"Bearer {os.environ.get('HA_TOKEN', '')}"},
                       json={"entity_id": entity_id, "type": kind}, timeout=10)
        if r.status_code == 200:
            return r.json()["service_response"][entity_id]["forecast"]
    except Exception:
        pass
    return []
