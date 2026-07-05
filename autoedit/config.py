"""Carga de configuración: defaults + config.yaml opcional."""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

DEFAULTS: dict = {
    "silence": {
        "noise_db": -35,
        "min_silence": 0.5,
        "padding": 0.15,
        "merge_gap": 0.2,
        "min_segment": 0.3,
    },
    "whisper": {
        "model": "small",
        "language": "es",
        "device": "auto",
    },
    "subtitles": {
        "enabled": True,
        "font": "Arial",
        "font_size": 54,
        "max_chars": 42,
        "max_lines": 2,
        "margin_v": 60,
        "outline": 2,
        "pause_break": 0.6,
    },
    "audio": {
        "highpass_hz": 80,
        "presence_freq": 4000,
        "presence_gain_db": 3,
        "loudnorm_i": -14,
        "loudnorm_tp": -1.5,
        "loudnorm_lra": 11,
    },
    "color": {
        "enabled": True,
        "contrast": 1.05,
        "saturation": 1.1,
        "brightness": 0.0,
        "lut": None,
    },
    "encode": {
        "preset": "veryfast",
        "crf": 20,
        "audio_bitrate": "192k",
    },
    "drive": {
        "root_folder": "AutoEdit",
        "min_file_age_minutes": 2,
        "stale_processing_hours": 6,
        "time_budget_minutes": 260,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | Path | None = None) -> dict:
    """Devuelve la config fusionando DEFAULTS con el yaml indicado (o ./config.yaml si existe)."""
    if path is None:
        candidate = Path("config.yaml")
        path = candidate if candidate.exists() else None
    if path is None:
        return copy.deepcopy(DEFAULTS)
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return _deep_merge(DEFAULTS, data)
