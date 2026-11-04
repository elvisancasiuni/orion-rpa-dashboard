#orion_dashboard_tracker.py
import json
import threading
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DASHBOARD_DATA_FILE = ROOT / "dashboard_data.json"
_LOCK = threading.Lock()

def _load():
    if not DASHBOARD_DATA_FILE.exists():
        return {"events": []}
    try:
        data = json.loads(DASHBOARD_DATA_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {"events": data}
        if isinstance(data, dict) and isinstance(data.get("events"), list):
            return data
        raise ValueError("Formato JSON inesperado: se esperaba {events: []}.")
    except Exception as exc:
        raise RuntimeError(
            f"No se pudo leer {DASHBOARD_DATA_FILE.name}; se conserva el archivo original."
        ) from exc

def registrar_envio(tipo, asunto="", detalle="", referencia="", cantidad=1):
    """
    Registrar después de la tecla de envío. Cada registro conserva fecha/hora local con zona horaria para permitir
    tendencias históricas. Tipos usados por ORION:
      - correo_individual: correo individual
      - correo_masiva: correo masivo
      - masiva: evento masivo (flujo existente)
      - whatsapp: mensaje WhatsApp
    El parámetro asunto se publica en la columna
    "ASUNTO | ALARMAS | CONTACTO" del dashboard.
    """
    tipo = str(tipo).strip().lower()
    tipos_validos = {"correo_individual", "correo_masiva", "masiva", "whatsapp"}
    if tipo not in tipos_validos:
        raise ValueError(f"Tipo de envío no válido: {tipo}")

    ahora = datetime.now().astimezone().isoformat(timespec="seconds")
    evento = {
        "id": f"{ahora}-{tipo}-{referencia}",
        "tipo": str(tipo),
        "fecha_hora": ahora,
        "cantidad": int(cantidad),
        "asunto": str(asunto),
        "detalle": str(detalle),
        "referencia": str(referencia),
    }
    with _LOCK:
        data = _load()
        data.setdefault("events", []).append(evento)
        data["events"] = data["events"][-10000:]
        tmp = DASHBOARD_DATA_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(DASHBOARD_DATA_FILE)
    try:
        from github_dashboard_sync import sync_async
        sync_async()
    except Exception as exc:
        print("Dashboard GitHub: no se pudo iniciar sincronización:", exc)
    return evento
