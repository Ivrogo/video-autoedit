"""Generación de subtítulos SRT y ASS a partir de palabras con timestamps."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .transcribe import Word

_SENTENCE_END = (".", "?", "!", "…")


@dataclass
class Cue:
    start: float
    end: float
    text: str  # líneas separadas por \n


def build_cues(
    words: list[Word],
    max_chars: int = 42,
    max_lines: int = 2,
    pause_break: float = 0.6,
) -> list[Cue]:
    """Agrupa palabras en subtítulos: corta por pausa larga, puntuación o longitud."""
    cues: list[Cue] = []
    current: list[Word] = []
    max_len = max_chars * max_lines

    def flush() -> None:
        if not current:
            return
        text = " ".join(w.text for w in current)
        cues.append(Cue(start=current[0].start, end=current[-1].end, text=_wrap(text, max_chars, max_lines)))
        current.clear()

    for i, word in enumerate(words):
        candidate_len = len(" ".join(w.text for w in current)) + (1 if current else 0) + len(word.text)
        if current and candidate_len > max_len:
            flush()
        current.append(word)

        next_word = words[i + 1] if i + 1 < len(words) else None
        long_pause = next_word is not None and next_word.start - word.end >= pause_break
        sentence_end = word.text.endswith(_SENTENCE_END)
        if long_pause or (sentence_end and len(" ".join(w.text for w in current)) >= max_chars // 2):
            flush()
    flush()
    return cues


def _wrap(text: str, max_chars: int, max_lines: int) -> str:
    """Parte el texto en hasta max_lines líneas de max_chars, equilibradas."""
    if len(text) <= max_chars:
        return text
    words = text.split()
    lines: list[str] = []
    current = ""
    for w in words:
        candidate = f"{current} {w}".strip()
        if len(candidate) > max_chars and current:
            lines.append(current)
            current = w
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\n".join(lines[:max_lines]) if len(lines) <= max_lines else _rebalance(words, max_lines)


def _rebalance(words: list[str], max_lines: int) -> str:
    """Reparte las palabras en exactamente max_lines líneas de longitud similar."""
    lines: list[list[str]] = [[] for _ in range(max_lines)]
    total = sum(len(w) + 1 for w in words)
    target = total / max_lines
    idx = 0
    acc = 0
    for w in words:
        if acc > target * (idx + 1) and idx < max_lines - 1:
            idx += 1
        lines[idx].append(w)
        acc += len(w) + 1
    return "\n".join(" ".join(l) for l in lines if l)


def _srt_time(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    ms = round((s - int(s)) * 1000)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{ms:03d}"


def _ass_time(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    cs = round((s - int(s)) * 100)
    return f"{int(h)}:{int(m):02d}:{int(s):02d}.{cs:02d}"


def write_srt(cues: list[Cue], path: Path) -> Path:
    blocks = []
    for i, cue in enumerate(cues, start=1):
        blocks.append(f"{i}\n{_srt_time(cue.start)} --> {_srt_time(cue.end)}\n{cue.text}\n")
    path.write_text("\n".join(blocks), encoding="utf-8")
    return path


def write_ass(cues: list[Cue], path: Path, style: dict) -> Path:
    """Escribe un .ass con el estilo de config (fuente, tamaño, borde, posición inferior)."""
    header = f"""[Script Info]
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style['font']},{style['font_size']},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,{style['outline']},0,2,30,30,{style['margin_v']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for cue in cues:
        text = cue.text.replace("\n", "\\N")
        lines.append(f"Dialogue: 0,{_ass_time(cue.start)},{_ass_time(cue.end)},Default,,0,0,0,,{text}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
