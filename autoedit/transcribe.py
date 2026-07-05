"""Transcripción con faster-whisper (timestamps por palabra)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

log = logging.getLogger("autoedit")


@dataclass
class Word:
    start: float
    end: float
    text: str


def _run(path: str, model_name: str, language: str, device: str, compute_type: str) -> list[Word]:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    segments, info = model.transcribe(
        path,
        language=language,
        word_timestamps=True,
        vad_filter=True,
    )
    words: list[Word] = []
    # segments es un generador: los errores de ejecución (p. ej. CUDA sin
    # librerías) saltan aquí, no al crear el modelo. Materializar dentro del try.
    for segment in segments:
        for w in segment.words or []:
            text = w.word.strip()
            if text:
                words.append(Word(start=w.start, end=w.end, text=text))
    log.info("Transcripción: %d palabras (idioma detectado: %s)", len(words), info.language)
    return words


def transcribe(path: str | Path, model_name: str, language: str, device: str = "auto") -> list[Word]:
    """Transcribe el archivo y devuelve la lista plana de palabras con tiempos.

    Con device=auto intenta CUDA y, si falla en cualquier punto (falta de
    librerías incluida), reintenta en CPU int8.
    """
    attempts = [("cuda", "float16"), ("cpu", "int8")] if device == "auto" else [
        (device, "float16" if device == "cuda" else "int8")
    ]
    last_exc: Exception | None = None
    for dev, ctype in attempts:
        try:
            log.info("Whisper %s en %s (%s)", model_name, dev, ctype)
            return _run(str(path), model_name, language, dev, ctype)
        except Exception as exc:  # noqa: BLE001 - CTranslate2 lanza tipos variados
            last_exc = exc
            if (dev, ctype) != attempts[-1]:
                log.info("Fallo con %s (%s); reintentando en CPU", dev, exc)
    raise RuntimeError(f"La transcripción falló en todos los dispositivos: {last_exc}") from last_exc


def save_transcript(words: list[Word], workdir: Path) -> tuple[Path, Path]:
    """Guarda transcript.json (palabras con tiempos) y transcript.txt (texto plano)."""
    json_path = workdir / "transcript.json"
    txt_path = workdir / "transcript.txt"
    json_path.write_text(
        json.dumps([asdict(w) for w in words], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    txt_path.write_text(" ".join(w.text for w in words), encoding="utf-8")
    return json_path, txt_path
