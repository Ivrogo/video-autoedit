"""Tests de agrupación y formato de subtítulos."""

from autoedit.captions import _srt_time, _wrap, build_cues, write_ass, write_srt
from autoedit.transcribe import Word


def _words(text: str, start: float = 0.0, gap: float = 0.05, dur: float = 0.3) -> list[Word]:
    words = []
    t = start
    for token in text.split():
        words.append(Word(start=t, end=t + dur, text=token))
        t += dur + gap
    return words


def test_build_cues_short_text_single_cue():
    cues = build_cues(_words("hola qué tal"))
    assert len(cues) == 1
    assert cues[0].text == "hola qué tal"


def test_build_cues_breaks_on_long_pause():
    words = _words("primera frase")
    tail = _words("segunda frase", start=words[-1].end + 2.0)
    cues = build_cues(words + tail, pause_break=0.6)
    assert len(cues) == 2
    assert cues[0].text == "primera frase"
    assert cues[1].text == "segunda frase"


def test_build_cues_breaks_on_sentence_end():
    words = _words("esto es una frase completa terminada. y aquí continúa otra")
    cues = build_cues(words, max_chars=42)
    assert len(cues) == 2
    assert cues[0].text.endswith("terminada.")


def test_build_cues_respects_max_length():
    text = "palabra " * 30
    cues = build_cues(_words(text.strip()), max_chars=20, max_lines=2)
    for cue in cues:
        for line in cue.text.split("\n"):
            assert len(line) <= 20 + 8  # margen: una palabra nunca se parte


def test_wrap_two_lines():
    wrapped = _wrap("una línea bastante larga que no cabe en una sola", max_chars=30, max_lines=2)
    lines = wrapped.split("\n")
    assert len(lines) == 2


def test_srt_time_format():
    assert _srt_time(3661.5) == "01:01:01,500"
    assert _srt_time(0) == "00:00:00,000"


def test_write_srt_and_ass(tmp_path):
    cues = build_cues(_words("hola mundo"))
    srt = write_srt(cues, tmp_path / "test.srt")
    style = {"font": "Arial", "font_size": 54, "outline": 2, "margin_v": 60}
    ass = write_ass(cues, tmp_path / "test.ass", style)

    srt_content = srt.read_text(encoding="utf-8")
    assert "1\n" in srt_content and "-->" in srt_content and "hola mundo" in srt_content

    ass_content = ass.read_text(encoding="utf-8")
    assert "[V4+ Styles]" in ass_content
    assert "Arial" in ass_content
    assert "Dialogue:" in ass_content
