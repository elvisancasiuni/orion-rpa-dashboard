# orion_dashboard_tracker.py
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
        return json.loads(DASHBOARD_DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"events": []}

def registrar_envio(tipo, asunto="", detalle="", referencia="", cantidad=1):
    """
    Registrar después de la tecla de envío. Cada registro conserva fecha/hora
    local con zona horaria para permitir tendencias históricas.
    """
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
