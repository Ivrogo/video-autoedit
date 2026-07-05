"""Controles de calidad entre etapas del pipeline."""

from __future__ import annotations

from pathlib import Path

from . import probe as probe_mod


class QCError(RuntimeError):
    pass


def check_output(path: str | Path, expected_duration: float | None = None, tolerance: float = 1.0) -> dict:
    """Verifica que un artefacto existe, decodifica y (opcional) dura lo esperado.

    Devuelve la info de ffprobe para reutilizarla.
    """
    path = Path(path)
    if not path.exists():
        raise QCError(f"QC: el archivo no se generó: {path}")
    if path.stat().st_size == 0:
        raise QCError(f"QC: el archivo está vacío: {path}")
    try:
        info = probe_mod.probe(path)
    except Exception as exc:
        raise QCError(f"QC: ffprobe no puede leer {path}: {exc}") from exc
    if expected_duration is not None:
        actual = probe_mod.duration(info)
        if abs(actual - expected_duration) > tolerance:
            raise QCError(
                f"QC: duración inesperada en {path.name}: "
                f"esperada {expected_duration:.1f}s, real {actual:.1f}s (tolerancia {tolerance}s)"
            )
    return info
