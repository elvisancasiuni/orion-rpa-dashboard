# orion_dashboard_tracker.py
# Compatible con orion_rpa_dashboard_nuevo.html

import json
import re
import threading
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DASHBOARD_DATA_FILE = ROOT / "dashboard_data.json"
MAX_EVENTS = 10000
_LOCK = threading.Lock()


def _normalizar_tipo(tipo):
    """Convierte el tipo al formato exacto que consume el dashboard HTML."""
    s = str(tipo or "").strip().lower()
    if "whatsapp" in s or "whats" in s:
        return "whatsapp"
    if "masiv" in s or "evento" in s:
        return "masiva"
    return "correo"


def _texto(valor):
    return "" if valor is None else str(valor).strip()


def _slug(valor):
    """Genera una parte segura y corta para el id del evento."""
    s = _texto(valor)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^A-Za-z0-9_-]", "", s)
    return s[:80] or "sin-referencia"


def _load():
    """Carga dashboard_data.json con la estructura {'events': [...]}."""
    if not DASHBOARD_DATA_FILE.exists():
        return {"events": []}

    try:
        data = json.loads(DASHBOARD_DATA_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            events = data.get("events", [])
            return {"events": events if isinstance(events, list) else []}
        if isinstance(data, list):
            return {"events": data}
    except Exception as exc:
        print("Dashboard: no se pudo leer dashboard_data.json:", exc)

    return {"events": []}


def _save(data):
    """Escritura atómica para evitar que el HTML lea un JSON incompleto."""
    tmp = DASHBOARD_DATA_FILE.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(DASHBOARD_DATA_FILE)


def registrar_envio(
    tipo,
    asunto="",
    detalle="",
    referencia="",
    cantidad=1,
):
    """
    Registra un envío en el formato consumido por el dashboard:

    {
      "id": "...",
      "tipo": "correo|whatsapp|masiva",
      "fecha_hora": "ISO-8601 con zona horaria",
      "cantidad": 1,
      "asunto": "...",
      "detalle": "...",
      "referencia": "..."
    }
    """
    tipo_normalizado = _normalizar_tipo(tipo)
    asunto = _texto(asunto)
    detalle = _texto(detalle) or asunto
    referencia = _texto(referencia)

    try:
        cantidad = int(cantidad)
    except (TypeError, ValueError):
        cantidad = 1

    if cantidad <= 0:
        cantidad = 1

    ahora = datetime.now().astimezone().isoformat(timespec="seconds")

    evento = {
        "id": f"{ahora}-{tipo_normalizado}-{_slug(referencia)}",
        "tipo": tipo_normalizado,
        "fecha_hora": ahora,
        "cantidad": cantidad,
        "asunto": asunto,
        "detalle": detalle,
        "referencia": referencia,
    }

    with _LOCK:
        data = _load()
        data.setdefault("events", []).append(evento)
        data["events"] = data["events"][-MAX_EVENTS:]
        _save(data)

    # Si github_dashboard_sync.py existe, sincroniza el JSON con GitHub.
    try:
        from github_dashboard_sync import sync_async
        sync_async()
    except ImportError:
        # El tracker puede utilizarse también sin sincronización a GitHub.
        pass
    except Exception as exc:
        print("Dashboard GitHub: no se pudo iniciar sincronización:", exc)

    return evento


# Alias opcionales para que el robot pueda llamar funciones más descriptivas.
def registrar_correo(asunto="", detalle="Correo enviado", referencia="", cantidad=1):
    return registrar_envio("correo", asunto, detalle, referencia, cantidad)


def registrar_whatsapp(asunto="", detalle="Mensaje WhatsApp enviado", referencia="", cantidad=1):
    return registrar_envio("whatsapp", asunto, detalle, referencia, cantidad)


def registrar_evento_masivo(asunto="", detalle="Evento masivo enviado", referencia="", cantidad=1):
    return registrar_envio("masiva", asunto, detalle, referencia, cantidad)
