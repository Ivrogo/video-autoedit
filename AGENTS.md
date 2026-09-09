# AGENTS.md

Work this repo **cloud-agent first** on GitHub (Cursor Cloud Agents). Do not assume a local Mac checkout.

This repo is code only: raw video is uploaded to Google Drive, GitHub Actions edits it on ephemeral Ubuntu runners, and results go back to Drive. Media never passes through GitHub.

## Defaults

| | |
|---|---|
| Default branch | `main` |
| Processing | GitHub Actions workflow **Procesar videos de Drive** (`.github/workflows/process.yml`), `ubuntu-latest` |
| Merge / deploy | **Never merge a PR, never dispatch the Drive workflow, and never run `drive-run` against live Drive** without explicit human OK |

Open a PR to `main`. Leave it unmerged.

## Purpose

Python pipeline (`python -m autoedit`) that:

1. Cuts silences (~0.5 s+)
2. Transcribes with faster-whisper (Spanish)
3. Writes `.srt` and burned-in captions
4. Masters audio (highpass, EQ, loudnorm ~-14 LUFS)
5. Light color grade (or optional LUT)

All tunables live in [`config.yaml`](config.yaml).

## GitHub Actions + Drive

```
upload raw → Drive AutoEdit/01_Raw
                |
     Actions cron */30 or workflow_dispatch
                |
edited + .srt + transcript → AutoEdit/03_Editados
archived raw               → AutoEdit/04_Procesados
failure: raw + error.log   → AutoEdit/05_Errores
```

`02_Procesando` is an internal claim folder so concurrent runs do not collide (`concurrency.group: drive-processing`). Folders are created on first run.

CI tests: `.github/workflows/tests.yml` runs `pytest` on push to `main` and on every PR. That workflow does **not** touch Drive.

## Layout

```
autoedit/            pipeline, silence, captions, audio, color
autoedit/drive/      Drive client + one-shot runner (CI)
config.yaml          pipeline + Drive settings
.github/workflows/   process.yml (Drive), tests.yml (pytest)
scripts/             OAuth helper; Windows-only test-clip generator
tests/               unit tests (no live Drive, no real media)
```

## Commands (Linux / Cloud Agent)

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt pytest
pytest -v
```

Optional local file (not Drive): `python -m autoedit process path/to/video.mp4`

`scripts/make_test_clip.ps1` is Windows PowerShell; skip it here. Do not use Mac-only tools.

## Secrets / env

Names only. Never commit values, `credentials.json`, or `token.json` (gitignored).

GitHub Actions secrets (injected as env in `process.yml`):

- `GDRIVE_CLIENT_ID`
- `GDRIVE_CLIENT_SECRET`
- `GDRIVE_REFRESH_TOKEN`

Local optional: `token.json` from `scripts/get_refresh_token.py`. Cloud Agents should not mint OAuth tokens or change GitHub secrets unless a human asks.

## Agent notes

- Prefer small, reviewable PRs. Do not push to `main`.
- Do not change GitHub secrets, the OAuth client, or Drive folder names unless a human asks.
- Match surrounding files (Spanish docstrings are the norm; README is Spanish).
- Runners are CPU-only; Whisper `small` in `config.yaml` is the CI default. Disk on Actions is tight (~8 GB raw max).
