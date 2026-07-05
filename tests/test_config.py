"""Tests de carga y fusión de configuración."""

from autoedit.config import DEFAULTS, load_config


def test_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # sin config.yaml en cwd
    cfg = load_config()
    assert cfg == DEFAULTS
    assert cfg is not DEFAULTS  # copia, no referencia


def test_yaml_overrides_deep_merge(tmp_path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text("silence:\n  noise_db: -40\n", encoding="utf-8")
    cfg = load_config(yaml_file)
    assert cfg["silence"]["noise_db"] == -40
    assert cfg["silence"]["padding"] == DEFAULTS["silence"]["padding"]  # el resto se conserva
    assert cfg["whisper"] == DEFAULTS["whisper"]
