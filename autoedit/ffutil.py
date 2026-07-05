"""Utilidades para invocar ffmpeg/ffprobe vía subprocess."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger("autoedit")


class FfmpegError(RuntimeError):
    pass


def run_ffmpeg(args: list[str], cwd: str | Path | None = None) -> str:
    """Ejecuta ffmpeg con los argumentos dados. Devuelve stderr (donde ffmpeg escribe su log)."""
    cmd = ["ffmpeg", "-hide_banner", "-y", *args]
    log.debug("ffmpeg %s", " ".join(args))
    proc = subprocess.run(
        cmd, cwd=str(cwd) if cwd else None,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise FfmpegError(
            f"ffmpeg falló (código {proc.returncode}):\n{proc.stderr[-4000:]}"
        )
    return proc.stderr


def run_ffprobe(args: list[str]) -> str:
    cmd = ["ffprobe", "-v", "error", *args]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise FfmpegError(
            f"ffprobe falló (código {proc.returncode}):\n{proc.stderr[-4000:]}"
        )
    return proc.stdout
