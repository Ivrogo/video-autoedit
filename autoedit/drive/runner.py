"""Modo one-shot para CI: reclama videos de 01_Raw, los procesa y reparte los resultados.

Las carpetas de Drive son la máquina de estados:
  01_Raw         -> pendientes (subidos por Ivan desde cualquier dispositivo)
  02_Procesando  -> reclamados por un run (appProperties.claimed_at marca cuándo)
  03_Editados    -> final.mp4 + .srt + transcript.txt
  04_Procesados  -> crudos ya procesados
  05_Errores     -> crudos que fallaron + error.log
"""

from __future__ import annotations

import datetime as dt
import logging
import shutil
import time
import traceback
from pathlib import Path

from ..pipeline import process_video
from . import client as drive

log = logging.getLogger("autoedit")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _parse_rfc3339(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def _requeue_stale(service, folders: drive.DriveFolders, stale_hours: float) -> None:
    """Devuelve a 01_Raw los archivos reclamados por jobs que murieron."""
    for f in drive.list_videos(service, folders.ids["02_Procesando"]):
        claimed_at = (f.get("appProperties") or {}).get("claimed_at")
        reference = _parse_rfc3339(claimed_at) if claimed_at else _parse_rfc3339(f["modifiedTime"])
        age_hours = (_now() - reference).total_seconds() / 3600
        if age_hours > stale_hours:
            log.warning("Re-encolando %s (reclamado hace %.1f h por un job muerto)", f["name"], age_hours)
            drive.move_file(
                service, f["id"],
                from_folder=folders.ids["02_Procesando"], to_folder=folders.ids["01_Raw"],
                app_properties={"claimed_at": ""},
            )


def _pending_videos(service, folders: drive.DriveFolders, min_age_minutes: float) -> list[dict]:
    """Videos de 01_Raw cuya subida parece terminada (no modificados recientemente)."""
    pending = []
    for f in drive.list_videos(service, folders.ids["01_Raw"]):
        age_min = (_now() - _parse_rfc3339(f["modifiedTime"])).total_seconds() / 60
        if age_min >= min_age_minutes:
            pending.append(f)
        else:
            log.info("Saltando %s: modificado hace %.1f min (subida posiblemente en curso)", f["name"], age_min)
    pending.sort(key=lambda f: f["createdTime"])
    return pending


def _process_one(service, folders: drive.DriveFolders, meta: dict, cfg: dict, work_root: Path) -> None:
    name = meta["name"]
    stem = Path(name).stem
    workdir = work_root / stem
    raw_path = workdir / name
    try:
        drive.download_file(service, meta["id"], raw_path)
        result = process_video(raw_path, cfg, output_root=workdir / "output")

        editados = folders.ids["03_Editados"]
        drive.upload_file(service, result.final_video, editados, name=f"{stem}_editado.mp4")
        drive.upload_file(service, result.srt, editados, name=f"{stem}.srt")
        drive.upload_file(service, result.transcript_txt, editados, name=f"{stem}_transcript.txt")

        drive.move_file(
            service, meta["id"],
            from_folder=folders.ids["02_Procesando"], to_folder=folders.ids["04_Procesados"],
        )
        log.info("OK: %s (%.1fs -> %.1fs)", name, result.original_duration, result.final_duration)
    except Exception:
        error_text = f"Video: {name}\nFecha: {_now().isoformat()}\n\n{traceback.format_exc()}"
        log.error("FALLO procesando %s:\n%s", name, error_text)
        try:
            drive.upload_text(service, error_text, f"{stem}_error.log", folders.ids["05_Errores"])
            drive.move_file(
                service, meta["id"],
                from_folder=folders.ids["02_Procesando"], to_folder=folders.ids["05_Errores"],
            )
        except Exception:
            log.error("Tampoco se pudo mover %s a 05_Errores:\n%s", name, traceback.format_exc())
        raise
    finally:
        shutil.rmtree(workdir, ignore_errors=True)  # liberar disco del runner


def run_once(cfg: dict, max_videos: int | None = None) -> list[str]:
    """Procesa los videos pendientes. Devuelve la lista de nombres que fallaron."""
    dcfg = cfg["drive"]
    service = drive.get_service()
    folders = drive.DriveFolders(service, dcfg["root_folder"])
    work_root = Path("work")

    _requeue_stale(service, folders, dcfg["stale_processing_hours"])
    pending = _pending_videos(service, folders, dcfg["min_file_age_minutes"])
    if not pending:
        log.info("No hay videos pendientes en 01_Raw")
        return []
    if max_videos:
        pending = pending[:max_videos]
    log.info("%d video(s) pendiente(s)", len(pending))

    start = time.time()
    budget_s = dcfg["time_budget_minutes"] * 60
    failures: list[str] = []
    for meta in pending:
        if time.time() - start > budget_s:
            log.info("Presupuesto de tiempo agotado; el resto queda para el siguiente run")
            break
        # Reclamar: mover a 02_Procesando con marca de tiempo
        drive.move_file(
            service, meta["id"],
            from_folder=folders.ids["01_Raw"], to_folder=folders.ids["02_Procesando"],
            app_properties={"claimed_at": _now().isoformat()},
        )
        log.info("Procesando %s ...", meta["name"])
        try:
            _process_one(service, folders, meta, cfg, work_root)
        except Exception:
            failures.append(meta["name"])  # ya registrado y movido a 05_Errores; seguimos con el resto
    return failures
