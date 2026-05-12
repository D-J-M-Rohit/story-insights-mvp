"""CLI: produce controlled metric simulation graphs as PNG files.

Usage:
    python -m app.scripts.generate_metric_simulation_graphs
    python -m app.scripts.generate_metric_simulation_graphs --output-dir backend/generated_graphs
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from app.evaluation_graphs import generate_metric_simulation_graphs


def _default_output_dir() -> str:
    backend_root = Path(__file__).resolve().parents[2]
    return str(backend_root / "generated_graphs")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate controlled scoring simulation graphs.")
    parser.add_argument(
        "--output-dir",
        default=_default_output_dir(),
        help="Directory to write generated PNG files (default: backend/generated_graphs).",
    )
    parser.add_argument(
        "--format",
        default="png",
        choices=["png"],
        help="Output format (currently only png is supported).",
    )
    parser.add_argument(
        "--show",
        default="false",
        choices=["true", "false"],
        help="Interactive display is disabled; flag accepted for compatibility.",
    )
    args = parser.parse_args(argv)

    output_dir = os.path.abspath(args.output_dir)
    paths = generate_metric_simulation_graphs(output_dir)

    print(f"Controlled simulation graphs written to: {output_dir}")
    for p in paths:
        print(f"  - {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
