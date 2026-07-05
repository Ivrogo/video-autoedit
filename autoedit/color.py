"""Corrección de color: eq suave por defecto, o LUT .cube si la config lo indica."""

from __future__ import annotations


def video_filters(cfg: dict) -> list[str]:
    """Filtros de color según config. Lista vacía si está desactivado."""
    if not cfg.get("enabled", True):
        return []
    lut = cfg.get("lut")
    if lut:
        # El .cube se copia al workdir como lut.cube (ver pipeline) para evitar
        # el escapado de rutas Windows dentro del grafo de filtros.
        return ["lut3d=lut.cube"]
    return [
        f"eq=contrast={cfg['contrast']}:saturation={cfg['saturation']}:brightness={cfg['brightness']}"
    ]
