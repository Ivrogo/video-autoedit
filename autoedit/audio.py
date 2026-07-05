"""Masterización de audio: highpass, EQ de presencia, compresión y loudnorm en dos pasadas."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .ffutil import run_ffmpeg


def base_filters(cfg: dict) -> list[str]:
    """Cadena de filtros previa a loudnorm."""
    return [
        f"highpass=f={cfg['highpass_hz']}",
        f"equalizer=f={cfg['presence_freq']}:t=q:w=1:g={cfg['presence_gain_db']}",
        "acompressor=threshold=-18dB:ratio=3:attack=20:release=250:makeup=2",
    ]


def _loudnorm_target(cfg: dict) -> str:
    return f"I={cfg['loudnorm_i']}:TP={cfg['loudnorm_tp']}:LRA={cfg['loudnorm_lra']}"


def measure_loudnorm(path: str | Path, cfg: dict) -> dict:
    """Primera pasada (solo audio, rápida): mide loudness con la cadena base aplicada."""
    chain = ",".join(base_filters(cfg) + [f"loudnorm={_loudnorm_target(cfg)}:print_format=json"])
    stderr = run_ffmpeg([
        "-i", str(path),
        "-vn",
        "-af", chain,
        "-f", "null", "-",
    ])
    # El JSON de loudnorm es el último bloque {...} del stderr
    matches = re.findall(r"\{[^{}]+\}", stderr, flags=re.DOTALL)
    if not matches:
        raise RuntimeError("loudnorm no devolvió mediciones (¿audio vacío?)")
    return json.loads(matches[-1])


def full_chain(cfg: dict, measured: dict | None = None) -> str:
    """Cadena completa para el render final. Con `measured`, loudnorm usa modo lineal (2ª pasada)."""
    loudnorm = f"loudnorm={_loudnorm_target(cfg)}"
    if measured:
        loudnorm += (
            f":measured_I={measured['input_i']}"
            f":measured_TP={measured['input_tp']}"
            f":measured_LRA={measured['input_lra']}"
            f":measured_thresh={measured['input_thresh']}"
            f":offset={measured['target_offset']}"
            ":linear=true"
        )
    return ",".join(base_filters(cfg) + [loudnorm])
