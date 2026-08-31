#!/usr/bin/env python3
"""Profile candidate chunking configurations against a local corpus."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluations.chunking import (  # noqa: E402
    load_corpus,
    profile_chunking,
    render_markdown_report,
)
from ingestion.chunker import ChunkingConfig  # noqa: E402


def _config(value: str) -> ChunkingConfig:
    try:
        maximum, overlap = (int(item) for item in value.split(":", 1))
        return ChunkingConfig(maximum, overlap)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(
            "Use MAX_CHARACTERS:OVERLAP_CHARACTERS, for example 2400:300."
        ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare paragraph-aware chunking settings on local source files."
    )
    parser.add_argument("corpus_directory", type=Path)
    parser.add_argument(
        "--config",
        action="append",
        type=_config,
        dest="configs",
        help="Repeatable MAX:OVERLAP setting. Defaults to three candidates.",
    )
    parser.add_argument("--output", type=Path, help="Optional Markdown report path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configs = args.configs or [
        ChunkingConfig(1_200, 150),
        ChunkingConfig(2_400, 300),
        ChunkingConfig(3_600, 450),
    ]
    try:
        documents = load_corpus(args.corpus_directory)
        profiles = [profile_chunking(documents, config) for config in configs]
        report = render_markdown_report(documents, profiles)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        print(f"Saved chunking profile to {args.output}")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

