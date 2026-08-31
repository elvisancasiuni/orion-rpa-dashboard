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
import certifi
import truststore
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "dashboard_data.json"
HTML_FILE = ROOT / "dashboard.html"

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
        "User-Agent": "ORION-RPA-Dashboard"
    }
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
   
        #with urlopen(req, timeout=20) as response:
    ssl_context = ssl.create_default_context(
        cafile=certifi.where()
        )
    try:
        with urlopen(
            req,
            timeout=20,
            context=ssl_context
        ) as response:
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
        _LAST_SYNC = now

        data = DATA_FILE.read_bytes() if DATA_FILE.exists() else b'{"events":[]}'
        # Primero actualiza el JSON. El HTML se publica una vez para que
        # GitHub Pages lo pueda servir.
        _put_file(
            DATA_PATH,
            data,
            f"ORION: actualizar dashboard_data.json ({time.strftime('%Y-%m-%d %H:%M:%S')})"
        )

        if HTML_FILE.exists() and os.getenv("ORION_GITHUB_UPDATE_HTML", "1") == "1":
            _put_file(
                HTML_PATH,
                HTML_FILE.read_bytes(),
                "ORION: actualizar dashboard"
            )

    return True, "Dashboard sincronizado con GitHub."

def sync_async():
    if not configured():
        return
    threading.Thread(target=sync_dashboard, kwargs={"force":False}, daemon=True).start()
