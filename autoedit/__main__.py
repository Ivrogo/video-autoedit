"""CLI de autoedit.

Uso:
  python -m autoedit process <video> [--config config.yaml] [--output output]
  python -m autoedit drive-run [--config config.yaml] [--max-videos N]
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import load_config


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(prog="autoedit", description="Edición de video automatizada")
    sub = parser.add_subparsers(dest="command", required=True)

    p_process = sub.add_parser("process", help="Procesa un video local")
    p_process.add_argument("video", help="Ruta del video de entrada")
    p_process.add_argument("--config", default=None, help="Ruta a config.yaml")
    p_process.add_argument("--output", default="output", help="Carpeta de salida")

    p_drive = sub.add_parser("drive-run", help="Procesa los videos pendientes de Google Drive (one-shot)")
    p_drive.add_argument("--config", default=None, help="Ruta a config.yaml")
    p_drive.add_argument("--max-videos", type=int, default=None, help="Máximo de videos en este run")

    args = parser.parse_args(argv)
    cfg = load_config(args.config)

    if args.command == "process":
        from .pipeline import process_video

        result = process_video(args.video, cfg, output_root=args.output)
        print(f"\nVideo final: {result.final_video}")
        print(f"Subtítulos:  {result.srt}")
        print(f"Transcript:  {result.transcript_txt}")
        print(f"Duración: {result.original_duration:.1f}s -> {result.final_duration:.1f}s")
        return 0

    if args.command == "drive-run":
        from .drive.runner import run_once

        failures = run_once(cfg, max_videos=args.max_videos)
        return 1 if failures else 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
