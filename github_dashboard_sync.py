# github_dashboard_sync.py
"""
Sincroniza dashboard_data.json con un repositorio GitHub.

Variables de entorno requeridas:
  ORION_GITHUB_TOKEN       = fine-grained PAT con Contents: Read and write
  ORION_GITHUB_REPOSITORY  = owner/repository (ej. usuario/orion-rpa-dashboard)
Opcionales:
  ORION_GITHUB_BRANCH      = rama (por defecto main)
  ORION_GITHUB_DATA_PATH   = ruta del JSON (por defecto dashboard_data.json)
  ORION_GITHUB_HTML_PATH   = ruta del dashboard (por defecto dashboard.html)

El token NUNCA se guarda en dashboard_data.json ni en el repositorio.
"""
import base64
import json
import os
import threading
import time
import ssl
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "dashboard_data.json"
HTML_FILE = ROOT / "dashboard.html"
INDEX_FILE = ROOT / "index.html"

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
    """Realiza una petición a GitHub con reintentos ante fallos transitorios."""
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ORION-RPA-Dashboard"
    }

    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    ssl_context = ssl.create_default_context()
    max_attempts = 4
    last_error = None

    for attempt in range(1, max_attempts + 1):
        # Crear un Request nuevo en cada intento.
        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=30, context=ssl_context) as response:
                raw = response.read().decode("utf-8", errors="replace")
                return response.status, json.loads(raw) if raw else {}

        except HTTPError as exc:
            # Los errores HTTP (401, 403, 404, 409, 422, etc.) son
            # respuestas de GitHub; no se deben reintentar aquí.
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except (ValueError, TypeError):
                payload = {"message": raw or str(exc)}
            return exc.code, payload

        except (URLError, ssl.SSLError, TimeoutError, ConnectionError, OSError) as exc:
            last_error = exc
            if attempt < max_attempts:
                wait_seconds = min(2 ** (attempt - 1), 8)
                time.sleep(wait_seconds)

    return 0, {
        "message": (
            f"No se pudo conectar con GitHub después de {max_attempts} intentos. "
            f"Último error: {last_error}"
        )
    }

def _get_sha(path):
    url = f"https://api.github.com/repos/{REPOSITORY}/contents/{path}?ref={BRANCH}"
    status, payload = _request("GET", url)
    if status == 200:
        return payload.get("sha")
    if status == 404:
        return None
    raise RuntimeError(f"GitHub GET {path}: HTTP {status}: {payload.get('message','')}")

def _put_file(path, content, commit_message):
    sha = _get_sha(path)
    encoded = base64.b64encode(content).decode("ascii")
    body = {
        "message": commit_message,
        "content": encoded,
        "branch": BRANCH,
    }
    if sha:
        body["sha"] = sha
    url = f"https://api.github.com/repos/{REPOSITORY}/contents/{path}"
    status, payload = _request("PUT", url, body)
    if status not in (200, 201):
        raise RuntimeError(f"GitHub PUT {path}: HTTP {status}: {payload.get('message','')}")
    return payload

def sync_dashboard(force=False):
    global _LAST_SYNC
    if not configured():
        return False, "GitHub no configurado: define ORION_GITHUB_TOKEN y ORION_GITHUB_REPOSITORY."

    now = time.time()
    with _LOCK:
        if not force and now - _LAST_SYNC < _SYNC_INTERVAL:
            return True, "Sincronización omitida por intervalo."
        data = DATA_FILE.read_bytes() if DATA_FILE.exists() else b'{"events":[]}'
        # Primero actualiza el JSON. El HTML se publica una vez para que
        # GitHub Pages lo pueda servir.
        _put_file(
            DATA_PATH,
            data,
            f"ORION: actualizar dashboard_data.json ({time.strftime('%Y-%m-%d %H:%M:%S')})"
        )

        if os.getenv("ORION_GITHUB_UPDATE_HTML", "1") == "1":
            # GitHub Pages sirve index.html al abrir la raíz del repositorio.
            html_content = HTML_FILE.read_bytes() if HTML_FILE.exists() else None
            index_content = INDEX_FILE.read_bytes() if INDEX_FILE.exists() else html_content
            if html_content is not None and index_content is not None and html_content != index_content:
                raise RuntimeError("dashboard.html e index.html no son idénticos. Actualiza ambos antes de sincronizar.")
            if html_content is not None:
                _put_file(HTML_PATH, html_content, "ORION: actualizar dashboard.html")
            index_path = os.getenv("ORION_GITHUB_INDEX_PATH", "index.html").strip() or "index.html"
            if index_content is not None:
                _put_file(index_path, index_content, "ORION: actualizar index.html para GitHub Pages")

        # Solo registrar el intervalo cuando TODOS los archivos se actualizaron.
        _LAST_SYNC = time.time()

    return True, "Dashboard sincronizado con GitHub."

def sync_async():
    if not configured():
        return
    threading.Thread(target=sync_dashboard, kwargs={"force":False}, daemon=True).start()
