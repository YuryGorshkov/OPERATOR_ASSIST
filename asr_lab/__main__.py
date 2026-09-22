"""Opt-in command line entry point. No UI automation, capture or downloads."""

import argparse
import json
import logging
from pathlib import Path
import sys

from .corpus import corpus_summary, load_manifest
from .profiles import PROFILES


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("profiles", help="List available experiments without loading a model.")
    check = commands.add_parser("check", help="Validate paired data without loading a model.")
    check.add_argument("manifest", type=Path)
    convert = commands.add_parser("convert", help="Convert an authorized local audio file to mono PCM16/16k WAV.")
    convert.add_argument("source", type=Path)
    convert.add_argument("output", type=Path)
    convert.add_argument("--permission-confirmed", action="store_true")
    export = commands.add_parser("export-training", help="Export verified pairs; does not train a model.")
    export.add_argument("manifest", type=Path)
    export.add_argument("output", type=Path)
    evaluate = commands.add_parser("evaluate", help="Compare profiles through offline speaker-channel replay.")
    evaluate.add_argument("manifest", type=Path)
    evaluate.add_argument("--model", type=Path, required=True, help="Existing local CTranslate2 model directory.")
    evaluate.add_argument("--output", type=Path, required=True, help="New report directory; never overwritten.")
    evaluate.add_argument("--device", choices=("gpu", "cpu"), default="gpu")
    evaluate.add_argument("--profiles", nargs="+", choices=tuple(PROFILES), default=("baseline", "context_off", "raw_context"))
    evaluate.add_argument("--split", choices=("dev", "test"), default="dev")
    evaluate.add_argument("--allow-test", action="store_true")
    evaluate.add_argument("--chunk-ms", type=int, default=250)
    evaluate.add_argument("--terms-file", type=Path, default=Path(__file__).resolve().parents[1] / "technical_terms.json")
    evaluate.add_argument("--it-mode", action="store_true")
    evaluate.add_argument("--hotwords-file", type=Path)
    realtime = commands.add_parser(
        "realtime",
        help="Measure paced end-to-end recognition latency and accuracy.",
    )
    realtime.add_argument("manifest", type=Path)
    realtime.add_argument("--model", type=Path, required=True, help="Existing local CTranslate2 model directory.")
    realtime.add_argument("--output", type=Path, required=True, help="New report directory; never overwritten.")
    realtime.add_argument("--device", choices=("gpu", "cpu"), default="gpu")
    realtime.add_argument("--profile", choices=tuple(PROFILES), default="production_pause")
    realtime.add_argument("--split", choices=("dev", "test"), default="dev")
    realtime.add_argument("--allow-test", action="store_true")
    realtime.add_argument("--chunk-ms", type=int, default=250)
    realtime.add_argument("--ui-poll-ms", type=int, default=120)
    realtime.add_argument("--trailing-silence-seconds", type=float, default=1.25)
    realtime.add_argument("--terms-file", type=Path, default=Path(__file__).resolve().parents[1] / "technical_terms.json")
    realtime.add_argument("--it-mode", action="store_true")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        if args.command == "profiles":
            from dataclasses import asdict
            print(json.dumps([asdict(profile) for profile in PROFILES.values()], indent=2))
        elif args.command == "check":
            print(json.dumps(corpus_summary(load_manifest(args.manifest)), ensure_ascii=False, indent=2))
        elif args.command == "convert":
            from .preparation import convert_audio
            print(json.dumps(convert_audio(args.source, args.output, permission_confirmed=args.permission_confirmed), ensure_ascii=False, indent=2))
        elif args.command == "export-training":
            from .preparation import export_training_pairs
            print(json.dumps(export_training_pairs(load_manifest(args.manifest), args.output), ensure_ascii=False, indent=2))
        elif args.command == "evaluate":
            from .benchmark import evaluate
            hotwords = args.hotwords_file.read_text(encoding="utf-8-sig") if args.hotwords_file else ""
            success = evaluate(load_manifest(args.manifest), manifest_path=args.manifest,
                               profiles=[PROFILES[name] for name in args.profiles], model_dir=args.model,
                               device=args.device, terms_path=args.terms_file, it_mode=args.it_mode,
                               hotwords=hotwords, output_dir=args.output, split=args.split,
                               allow_test=args.allow_test, chunk_ms=args.chunk_ms)
            print(f"Report: {args.output.resolve()}")
            return 0 if success else 1
        elif args.command == "realtime":
            from .realtime import evaluate_realtime
            success = evaluate_realtime(
                load_manifest(args.manifest),
                manifest_path=args.manifest,
                profile=PROFILES[args.profile],
                model_dir=args.model,
                device=args.device,
                terms_path=args.terms_file,
                it_mode=args.it_mode,
                output_dir=args.output,
                split=args.split,
                allow_test=args.allow_test,
                chunk_ms=args.chunk_ms,
                ui_poll_ms=args.ui_poll_ms,
                trailing_silence_seconds=args.trailing_silence_seconds,
            )
            print(f"Report: {args.output.resolve()}")
            return 0 if success else 1
        return 0
    except (ValueError, OSError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
