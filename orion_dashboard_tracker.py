# orion_dashboard_tracker.py
# Compatible con Archivo_HTML.txt
import json, re, threading
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DASHBOARD_DATA_FILE = ROOT / "dashboard_data.json"
MAX_EVENTS = 10000
_LOCK = threading.Lock()

def _normalizar_tipo(tipo):
    s = str(tipo or "").strip().lower()
    if "whatsapp" in s or "whats" in s: return "whatsapp"
    if "masiv" in s or "evento" in s: return "masiva"
    return "correo"

def _texto(v):
    return "" if v is None else str(v).strip()

def _id_seguro(v):
    s = re.sub(r"\s+", "-", _texto(v))
    s = re.sub(r"[^A-Za-z0-9_-]", "", s)
    return s[:80] or "sin-referencia"

def _load():
    if not DASHBOARD_DATA_FILE.exists(): return {"events":[]}
    try:
        data = json.loads(DASHBOARD_DATA_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list): return {"events":data}
        if isinstance(data, dict) and isinstance(data.get("events"), list):
            return {"events":data["events"]}
    except Exception as exc:
        print("Dashboard: no se pudo leer dashboard_data.json:", exc)
    return {"events":[]}

def _save(data):
    tmp = DASHBOARD_DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DASHBOARD_DATA_FILE)

def registrar_envio(tipo, asunto="", detalle="", referencia="", cantidad=1):
    """Genera exactamente: id,tipo,fecha_hora,cantidad,asunto,detalle,referencia."""
    tipo = _normalizar_tipo(tipo)
    asunto, referencia = _texto(asunto), _texto(referencia)
    detalle = _texto(detalle) or asunto
    try: cantidad = int(cantidad)
    except (TypeError, ValueError): cantidad = 1
    cantidad = max(1, cantidad)
    ahora = datetime.now().astimezone().isoformat(timespec="seconds")
    evento = {
        "id": f"{ahora}-{tipo}-{_id_seguro(referencia)}",
        "tipo": tipo, "fecha_hora": ahora, "cantidad": cantidad,
        "asunto": asunto, "detalle": detalle, "referencia": referencia
    }
    with _LOCK:
        data = _load()
        data["events"].append(evento)
        data["events"] = data["events"][-MAX_EVENTS:]
        _save(data)
    try:
        from github_dashboard_sync import sync_async
        sync_async()
    except ImportError:
        pass
    except Exception as exc:
        print("Dashboard GitHub: no se pudo iniciar sincronización:", exc)
    return evento

def registrar_correo(asunto="", detalle="Correo enviado", referencia="", cantidad=1):
    return registrar_envio("correo", asunto, detalle, referencia, cantidad)

def registrar_whatsapp(asunto="", detalle="Mensaje WhatsApp enviado", referencia="", cantidad=1):
    return registrar_envio("whatsapp", asunto, detalle, referencia, cantidad)

def registrar_evento_masivo(asunto="", detalle="Evento masivo enviado", referencia="", cantidad=1):
    return registrar_envio("masiva", asunto, detalle, referencia, cantidad)
