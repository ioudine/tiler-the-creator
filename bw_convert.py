"""Convert a color image to black-and-white.

This script uses Pillow to load an input image, convert it to grayscale,
optionally apply a binary threshold, and save the result.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a color image to black-and-white (grayscale)",
    )
    parser.add_argument("input", type=Path, help="Path to the input image")
    parser.add_argument(
        "output",
        type=Path,
        help="Destination path for the black-and-white image",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=None,
        help=(
            "Optional 0-255 threshold for binary output. If omitted, the output"
            " remains grayscale."
        ),
    )
    return parser.parse_args()


def convert_to_bw(
    input_path: Path, output_path: Path, threshold: Optional[int] = None
) -> None:
    """Convert an image to grayscale and optionally apply a binary threshold."""
    with Image.open(input_path) as img:
        grayscale = img.convert("L")

        if threshold is not None:
            if not 0 <= threshold <= 255:
                raise ValueError("threshold must be between 0 and 255")
            grayscale = grayscale.point(lambda p: 255 if p >= threshold else 0)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        grayscale.save(output_path)


def main() -> None:
    args = parse_args()
    convert_to_bw(args.input, args.output, args.threshold)


if __name__ == "__main__":
    main()
