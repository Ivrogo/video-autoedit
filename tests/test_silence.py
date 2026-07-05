"""Tests de la lógica pura de detección/inversión de silencios."""

from autoedit.silence import kept_duration, parse_silencedetect, speech_segments

SAMPLE_STDERR = """
[silencedetect @ 000001] silence_start: 5.2
[silencedetect @ 000001] silence_end: 7.1 | silence_duration: 1.9
[silencedetect @ 000001] silence_start: 20.5
[silencedetect @ 000001] silence_end: 22.0 | silence_duration: 1.5
size=N/A time=00:00:30.00 bitrate=N/A speed= 500x
"""


def test_parse_silencedetect():
    assert parse_silencedetect(SAMPLE_STDERR) == [(5.2, 7.1), (20.5, 22.0)]


def test_parse_silencedetect_open_ended():
    stderr = "[silencedetect @ 0x1] silence_start: 25.0\n"
    assert parse_silencedetect(stderr) == [(25.0, float("inf"))]


def test_parse_silencedetect_negative_start_clamped():
    # silencedetect puede reportar silence_start negativo al principio del archivo
    stderr = (
        "[silencedetect @ 0x1] silence_start: -0.02\n"
        "[silencedetect @ 0x1] silence_end: 3.0 | silence_duration: 3.02\n"
    )
    assert parse_silencedetect(stderr) == [(0.0, 3.0)]


def test_speech_segments_basic():
    silences = [(5.0, 7.0), (20.0, 22.0)]
    segments = speech_segments(silences, total=30.0, padding=0.0, merge_gap=0.0, min_segment=0.0)
    assert segments == [(0.0, 5.0), (7.0, 20.0), (22.0, 30.0)]


def test_speech_segments_padding_and_clamp():
    segments = speech_segments([(5.0, 7.0)], total=10.0, padding=0.5, merge_gap=0.0, min_segment=0.0)
    assert segments == [(0.0, 5.5), (6.5, 10.0)]


def test_speech_segments_merge_close():
    # Con padding 0.5 el hueco (5,6) se reduce a (5.5, 5.5): se fusiona todo
    segments = speech_segments([(5.0, 6.0)], total=10.0, padding=0.5, merge_gap=0.2, min_segment=0.0)
    assert segments == [(0.0, 10.0)]


def test_speech_segments_silence_at_start():
    segments = speech_segments([(0.0, 3.0)], total=10.0, padding=0.0, merge_gap=0.0, min_segment=0.0)
    assert segments == [(3.0, 10.0)]


def test_speech_segments_open_ended_silence():
    segments = speech_segments([(8.0, float("inf"))], total=10.0, padding=0.0, merge_gap=0.0, min_segment=0.0)
    assert segments == [(0.0, 8.0)]


def test_speech_segments_drops_tiny():
    silences = [(0.5, 5.0), (5.1, 10.0)]  # deja un fragmento de 0.1s entre silencios
    segments = speech_segments(silences, total=10.0, padding=0.0, merge_gap=0.0, min_segment=0.3)
    assert segments == [(0.0, 0.5)]


def test_kept_duration():
    assert kept_duration([(0.0, 5.0), (7.0, 10.0)]) == 8.0
