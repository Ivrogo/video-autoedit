"""Detección de silencios y corte del video conservando solo los tramos con voz."""

from __future__ import annotations

import re
from pathlib import Path

from .ffutil import run_ffmpeg

_RE_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
_RE_END = re.compile(r"silence_end:\s*(-?[\d.]+)")


def parse_silencedetect(stderr: str) -> list[tuple[float, float]]:
    """Extrae pares (inicio, fin) de silencio del log de silencedetect."""
    silences: list[tuple[float, float]] = []
    start: float | None = None
    for line in stderr.splitlines():
        m = _RE_START.search(line)
        if m:
            start = max(0.0, float(m.group(1)))
            continue
        m = _RE_END.search(line)
        if m and start is not None:
            silences.append((start, float(m.group(1))))
            start = None
    # Silencio abierto al final del archivo (sin silence_end)
    if start is not None:
        silences.append((start, float("inf")))
    return silences


def detect_silences(path: str | Path, noise_db: float, min_silence: float) -> list[tuple[float, float]]:
    """Pasada rápida solo-audio con silencedetect."""
    stderr = run_ffmpeg([
        "-i", str(path),
        "-vn",
        "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}",
        "-f", "null", "-",
    ])
    return parse_silencedetect(stderr)


def speech_segments(
    silences: list[tuple[float, float]],
    total: float,
    padding: float = 0.15,
    merge_gap: float = 0.2,
    min_segment: float = 0.3,
) -> list[tuple[float, float]]:
    """Invierte los silencios a segmentos con voz, con padding, fusión y filtrado.

    Devuelve lista de (inicio, fin) en segundos, ordenada y sin solapes.
    """
    # Invertir: huecos entre silencios
    segments: list[tuple[float, float]] = []
    cursor = 0.0
    for s_start, s_end in silences:
        if s_start > cursor:
            segments.append((cursor, s_start))
        cursor = max(cursor, min(s_end, total))
    if cursor < total:
        segments.append((cursor, total))

    # Padding a cada lado, recortado a los límites del video
    padded = [(max(0.0, a - padding), min(total, b + padding)) for a, b in segments]

    # Fusionar segmentos que se solapan o quedan muy cerca
    merged: list[tuple[float, float]] = []
    for a, b in padded:
        if merged and a - merged[-1][1] <= merge_gap:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))

    # Descartar segmentos demasiado cortos (ruidos sueltos)
    return [(a, b) for a, b in merged if b - a >= min_segment]


def kept_duration(segments: list[tuple[float, float]]) -> float:
    return sum(b - a for a, b in segments)


def cut_silences(
    input_path: str | Path,
    output_name: str,
    segments: list[tuple[float, float]],
    workdir: Path,
    encode: dict,
) -> Path:
    """Re-codifica el video conservando solo los segmentos dados (un solo encode).

    El grafo de filtros se escribe a archivo (-filter_complex_script) porque con
    videos largos puede haber cientos de segmentos y la línea de comandos se queda corta.
    Todos los paths de salida son relativos a workdir (cwd del proceso ffmpeg).
    """
    expr = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in segments)
    script = (
        f"[0:v]select='{expr}',setpts=N/FRAME_RATE/TB[v];\n"
        f"[0:a]aselect='{expr}',asetpts=N/SR/TB[a]"
    )
    script_path = workdir / "cut_filter.txt"
    script_path.write_text(script, encoding="utf-8")

    output = workdir / output_name
    run_ffmpeg(
        [
            "-i", str(input_path),
            "-filter_complex_script", script_path.name,
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", str(encode["preset"]), "-crf", str(encode["crf"]),
            "-c:a", "aac", "-b:a", str(encode["audio_bitrate"]),
            output.name,
        ],
        cwd=workdir,
    )
    return output
