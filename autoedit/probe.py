"""Inspección de archivos con ffprobe."""

from __future__ import annotations

import json
from pathlib import Path

from .ffutil import run_ffprobe


class ProbeError(RuntimeError):
    pass


def probe(path: str | Path) -> dict:
    """Devuelve la información de ffprobe (format + streams) como dict."""
    path = Path(path)
    if not path.exists():
        raise ProbeError(f"El archivo no existe: {path}")
    out = run_ffprobe([
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(path),
    ])
    return json.loads(out)


def duration(info: dict) -> float:
    try:
        return float(info["format"]["duration"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ProbeError("No se pudo leer la duración del archivo") from exc


def has_audio(info: dict) -> bool:
    return any(s.get("codec_type") == "audio" for s in info.get("streams", []))


def has_video(info: dict) -> bool:
    return any(s.get("codec_type") == "video" for s in info.get("streams", []))


def validate_input(path: str | Path) -> dict:
    """Probe + validaciones básicas. Lanza ProbeError con mensaje claro si algo falla."""
    info = probe(path)
    if not has_video(info):
        raise ProbeError(f"El archivo no tiene pista de video: {path}")
    if not has_audio(info):
        raise ProbeError(f"El archivo no tiene pista de audio (necesaria para el pipeline): {path}")
    if duration(info) < 1.0:
        raise ProbeError(f"El archivo dura menos de 1 segundo: {path}")
    return info
