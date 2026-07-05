"""Cliente de Google Drive: auth por refresh token (CI) o flujo local, y operaciones básicas.

Credenciales, en orden de prioridad:
1. Variables de entorno GDRIVE_CLIENT_ID / GDRIVE_CLIENT_SECRET / GDRIVE_REFRESH_TOKEN (GitHub Actions).
2. token.json local (generado por scripts/get_refresh_token.py).
"""

from __future__ import annotations

import io
import json
import logging
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

log = logging.getLogger("autoedit")

SCOPES = ["https://www.googleapis.com/auth/drive"]
TOKEN_URI = "https://oauth2.googleapis.com/token"
FOLDER_MIME = "application/vnd.google-apps.folder"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"}

SUBFOLDERS = ["01_Raw", "02_Procesando", "03_Editados", "04_Procesados", "05_Errores"]


def get_service():
    """Construye el cliente de la API de Drive con las credenciales disponibles."""
    client_id = os.environ.get("GDRIVE_CLIENT_ID")
    client_secret = os.environ.get("GDRIVE_CLIENT_SECRET")
    refresh_token = os.environ.get("GDRIVE_REFRESH_TOKEN")

    if client_id and client_secret and refresh_token:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=TOKEN_URI,
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )
    elif Path("token.json").exists():
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    else:
        raise RuntimeError(
            "Sin credenciales de Drive: define GDRIVE_CLIENT_ID/GDRIVE_CLIENT_SECRET/"
            "GDRIVE_REFRESH_TOKEN o genera token.json con scripts/get_refresh_token.py"
        )
    creds.refresh(Request())
    return build("drive", "v3", credentials=creds, cache_discovery=False)


class DriveFolders:
    """Localiza (o crea) el árbol AutoEdit/{01_Raw,...} y guarda los IDs."""

    def __init__(self, service, root_name: str):
        self.service = service
        self.root_id = self._ensure_folder(root_name, parent=None)
        self.ids: dict[str, str] = {
            name: self._ensure_folder(name, parent=self.root_id) for name in SUBFOLDERS
        }

    def _ensure_folder(self, name: str, parent: str | None) -> str:
        safe = name.replace("'", "\\'")
        query = f"name = '{safe}' and mimeType = '{FOLDER_MIME}' and trashed = false"
        if parent:
            query += f" and '{parent}' in parents"
        else:
            query += " and 'root' in parents"
        res = self.service.files().list(q=query, fields="files(id)", pageSize=1).execute()
        files = res.get("files", [])
        if files:
            return files[0]["id"]
        meta = {"name": name, "mimeType": FOLDER_MIME}
        if parent:
            meta["parents"] = [parent]
        created = self.service.files().create(body=meta, fields="id").execute()
        log.info("Creada carpeta de Drive: %s", name)
        return created["id"]


def list_videos(service, folder_id: str) -> list[dict]:
    """Videos de una carpeta con id, nombre, tamaño, fechas y appProperties."""
    files: list[dict] = []
    page_token = None
    while True:
        res = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="nextPageToken, files(id, name, size, modifiedTime, createdTime, appProperties)",
            pageSize=100,
            pageToken=page_token,
        ).execute()
        for f in res.get("files", []):
            if Path(f["name"]).suffix.lower() in VIDEO_EXTENSIONS:
                files.append(f)
        page_token = res.get("nextPageToken")
        if not page_token:
            break
    return files


def move_file(service, file_id: str, from_folder: str, to_folder: str, app_properties: dict | None = None) -> None:
    body = {"appProperties": app_properties} if app_properties else None
    service.files().update(
        fileId=file_id,
        addParents=to_folder,
        removeParents=from_folder,
        body=body,
        fields="id",
    ).execute()


def download_file(service, file_id: str, dest: Path) -> Path:
    request = service.files().get_media(fileId=file_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with io.FileIO(str(dest), "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=32 * 1024 * 1024)
        done = False
        while not done:
            status, done = downloader.next_chunk(num_retries=5)
            if status:
                log.info("Descarga %s: %d%%", dest.name, int(status.progress() * 100))
    return dest


def upload_file(service, path: Path, folder_id: str, name: str | None = None) -> str:
    media = MediaFileUpload(str(path), resumable=True, chunksize=32 * 1024 * 1024)
    meta = {"name": name or path.name, "parents": [folder_id]}
    request = service.files().create(body=meta, media_body=media, fields="id")
    response = None
    while response is None:
        status, response = request.next_chunk(num_retries=5)
        if status:
            log.info("Subida %s: %d%%", meta["name"], int(status.progress() * 100))
    return response["id"]


def upload_text(service, text: str, name: str, folder_id: str) -> str:
    """Sube un archivo de texto pequeño (logs de error) sin archivo temporal."""
    from googleapiclient.http import MediaInMemoryUpload

    media = MediaInMemoryUpload(text.encode("utf-8"), mimetype="text/plain")
    meta = {"name": name, "parents": [folder_id]}
    created = service.files().create(body=meta, media_body=media, fields="id").execute()
    return created["id"]
