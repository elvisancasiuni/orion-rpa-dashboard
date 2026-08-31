# github_dashboard_sync.py
"""
Sincroniza dashboard_data.json con GitHub para Archivo_HTML.

Variables requeridas:
  ORION_GITHUB_TOKEN
  ORION_GITHUB_REPOSITORY   = owner/repository

Opcionales:
  ORION_GITHUB_BRANCH       = main
  ORION_GITHUB_DATA_PATH    = dashboard_data.json
  ORION_GITHUB_HTML_FILE    = dashboard.html (archivo HTML local)
  ORION_GITHUB_HTML_PATH    = dashboard.html (ruta HTML en GitHub)
  ORION_GITHUB_UPDATE_HTML  = 0 o 1

El HTML Archivo_HTML carga:
  dashboard_data.json?ts=...
por lo que normalmente basta sincronizar el JSON después de cada evento.
"""

import base64
import certifi
import json
import os
import ssl
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent

DATA_FILE = ROOT / os.getenv("ORION_DASHBOARD_DATA_FILE", "dashboard_data.json")
HTML_FILE = ROOT / os.getenv("ORION_GITHUB_HTML_FILE", "dashboard.html")

TOKEN = os.getenv("ORION_GITHUB_TOKEN", "").strip()
REPOSITORY = os.getenv("ORION_GITHUB_REPOSITORY", "").strip()
BRANCH = os.getenv("ORION_GITHUB_BRANCH", "main").strip() or "main"

DATA_PATH = os.getenv("ORION_GITHUB_DATA_PATH", "dashboard_data.json").strip()
HTML_PATH = os.getenv("ORION_GITHUB_HTML_PATH", "dashboard.html").strip()

_LOCK = threading.Lock()
_LAST_SYNC = 0.0
_SYNC_INTERVAL = int(os.getenv("ORION_GITHUB_SYNC_SECONDS", "15"))


def configured():
    return bool(TOKEN and REPOSITORY)


def _request(method, url, body=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ORION-RPA-Dashboard",
    }

    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url, data=data, headers=headers, method=method)

    try:
        context = ssl.create_default_context(cafile=certifi.where())
        with urlopen(req, timeout=20, context=context) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(raw) if raw else {}

    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"message": raw}
        return exc.code, payload

    except URLError as exc:
        return 0, {"message": str(exc)}


def _api_url(path):
    safe_path = quote(path.lstrip("/"), safe="/")
    return f"https://api.github.com/repos/{REPOSITORY}/contents/{safe_path}"


def _get_sha(path):
    url = f"{_api_url(path)}?ref={quote(BRANCH, safe='')}"
    status, payload = _request("GET", url)

    if status == 200:
        return payload.get("sha")
    if status == 404:
        return None

    raise RuntimeError(
        f"GitHub GET {path}: HTTP {status}: {payload.get('message', '')}"
    )


def _put_file(path, content, commit_message):
    sha = _get_sha(path)

    body = {
        "message": commit_message,
        "content": base64.b64encode(content).decode("ascii"),
        "branch": BRANCH,
    }

    if sha:
        body["sha"] = sha

    status, payload = _request("PUT", _api_url(path), body)

    if status not in (200, 201):
        raise RuntimeError(
            f"GitHub PUT {path}: HTTP {status}: {payload.get('message', '')}"
        )

    return payload


def sync_dashboard(force=False, include_html=None):
    """
    Sincroniza el JSON compatible con Archivo_HTML.

    include_html:
      None  -> usa ORION_GITHUB_UPDATE_HTML (por defecto 0)
      True  -> también publica el HTML local
      False -> solo publica dashboard_data.json
    """
    global _LAST_SYNC

    if not configured():
        return False, (
            "GitHub no configurado: define ORION_GITHUB_TOKEN "
            "y ORION_GITHUB_REPOSITORY."
        )

    if include_html is None:
        include_html = os.getenv("ORION_GITHUB_UPDATE_HTML", "0") == "1"

    now = time.time()

    with _LOCK:
        if not force and now - _LAST_SYNC < _SYNC_INTERVAL:
            return True, "Sincronización omitida por intervalo."

        _LAST_SYNC = now

        data = (
            DATA_FILE.read_bytes()
            if DATA_FILE.exists()
            else b'{"events":[]}'
        )

        _put_file(
            DATA_PATH,
            data,
            f"ORION: actualizar dashboard_data.json "
            f"({time.strftime('%Y-%m-%d %H:%M:%S')})",
        )

        if include_html:
            if not HTML_FILE.exists():
                raise FileNotFoundError(
                    f"No se encontró el HTML local: {HTML_FILE}"
                )

            _put_file(
                HTML_PATH,
                HTML_FILE.read_bytes(),
                "ORION: actualizar dashboard HTML",
            )

    return True, "Dashboard sincronizado correctamente con GitHub."


def sync_html():
    """Publica explícitamente el HTML compatible con Archivo_HTML."""
    return sync_dashboard(force=True, include_html=True)


def sync_async():
    """
    Llamado automáticamente por orion_dashboard_tracker.py.
    Por defecto solo actualiza dashboard_data.json, que Archivo_HTML
    vuelve a leer cada 15 segundos sin caché.
    """
    if not configured():
        return None

    thread = threading.Thread(
        target=sync_dashboard,
        kwargs={"force": False, "include_html": False},
        daemon=True,
        name="ORION-GitHub-Sync",
    )
    thread.start()
    return thread
