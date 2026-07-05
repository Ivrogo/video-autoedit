"""Orquestador del pipeline: probe → corte de silencios → transcripción → subtítulos → render final."""

from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from . import audio as audio_mod
from . import captions as captions_mod
from . import color as color_mod
from . import probe as probe_mod
from . import qc
from . import silence as silence_mod
from . import transcribe as transcribe_mod
from .ffutil import run_ffmpeg

log = logging.getLogger("autoedit")


@dataclass
class PipelineResult:
    final_video: Path
    srt: Path
    transcript_txt: Path
    transcript_json: Path
    original_duration: float
    final_duration: float


def process_video(input_path: str | Path, cfg: dict, output_root: str | Path = "output") -> PipelineResult:
    """Procesa un video de principio a fin. Los artefactos quedan en output/<nombre>/."""
    input_path = Path(input_path).resolve()
    workdir = Path(output_root).resolve() / input_path.stem
    workdir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # 1. Probe y validación
    log.info("[1/6] Analizando %s", input_path.name)
    info = probe_mod.validate_input(input_path)
    total = probe_mod.duration(info)
    log.info("Duración original: %.1f s", total)

    # 2. Corte de silencios (encode 1)
    log.info("[2/6] Detectando silencios...")
    scfg = cfg["silence"]
    silences = silence_mod.detect_silences(input_path, scfg["noise_db"], scfg["min_silence"])
    segments = silence_mod.speech_segments(
        silences, total,
        padding=scfg["padding"], merge_gap=scfg["merge_gap"], min_segment=scfg["min_segment"],
    )
    if not segments:
        raise RuntimeError("No se detectó voz en el video (¿umbral de silencio demasiado alto?)")
    expected = silence_mod.kept_duration(segments)
    log.info(
        "%d silencios -> %d segmentos con voz, %.1f s conservados (%.0f%%)",
        len(silences), len(segments), expected, 100 * expected / total,
    )
    cut_path = silence_mod.cut_silences(input_path, "01_cortado.mp4", segments, workdir, cfg["encode"])
    qc.check_output(cut_path, expected_duration=expected, tolerance=1.5)

    # 3. Transcripción (sobre el video ya cortado, para que los subtítulos cuadren)
    log.info("[3/6] Transcribiendo con Whisper (%s)...", cfg["whisper"]["model"])
    words = transcribe_mod.transcribe(
        cut_path,
        model_name=cfg["whisper"]["model"],
        language=cfg["whisper"]["language"],
        device=cfg["whisper"]["device"],
    )
    transcript_json, transcript_txt = transcribe_mod.save_transcript(words, workdir)

    # 4. Subtítulos
    log.info("[4/6] Generando subtítulos...")
    sub_cfg = cfg["subtitles"]
    cues = captions_mod.build_cues(
        words,
        max_chars=sub_cfg["max_chars"], max_lines=sub_cfg["max_lines"],
        pause_break=sub_cfg["pause_break"],
    )
    srt_path = captions_mod.write_srt(cues, workdir / "captions.srt")
    ass_path = captions_mod.write_ass(cues, workdir / "captions.ass", sub_cfg)
    log.info("%d subtítulos", len(cues))

    # 5. Medición de loudness (pasada solo-audio)
    log.info("[5/6] Midiendo loudness...")
    measured = audio_mod.measure_loudnorm(cut_path, cfg["audio"])

    # 6. Render final (encode 2): color + subtítulos quemados + cadena de audio completa
    log.info("[6/6] Render final...")
    vf = color_mod.video_filters(cfg["color"])
    lut = cfg["color"].get("lut")
    if cfg["color"].get("enabled") and lut:
        shutil.copyfile(lut, workdir / "lut.cube")
    if sub_cfg.get("enabled", True) and cues:
        vf.append("subtitles=captions.ass")
    af = audio_mod.full_chain(cfg["audio"], measured)
    enc = cfg["encode"]
    final_path = workdir / "final.mp4"
    args = ["-i", cut_path.name]
    if vf:
        args += ["-vf", ",".join(vf)]
    args += [
        "-af", af,
        "-c:v", "libx264", "-preset", str(enc["preset"]), "-crf", str(enc["crf"]),
        "-c:a", "aac", "-b:a", str(enc["audio_bitrate"]),
        "-movflags", "+faststart",
        final_path.name,
    ]
    run_ffmpeg(args, cwd=workdir)
    final_info = qc.check_output(final_path, expected_duration=expected, tolerance=1.5)
    final_duration = probe_mod.duration(final_info)

    # Liberar disco: el intermedio ya no hace falta (importante en runners de CI)
    cut_path.unlink(missing_ok=True)
    (workdir / "cut_filter.txt").unlink(missing_ok=True)

    log.info(
        "Listo en %.0f s: %s (%.1f s, original %.1f s)",
        time.time() - t0, final_path, final_duration, total,
    )
    return PipelineResult(
        final_video=final_path,
        srt=srt_path,
        transcript_txt=transcript_txt,
        transcript_json=transcript_json,
        original_duration=total,
        final_duration=final_duration,
    )
