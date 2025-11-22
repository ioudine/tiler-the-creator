#!/usr/bin/env python3
"""Command-line interface that wraps the experimental tiler scripts.

Examples:
    python tiler_cli.py single input.jpg out.png --tile-size 0.25
    python tiler_cli.py layers input.jpg out.png --count 8 --tile-size 0.2 --seed 42
    python tiler_cli.py gif input.jpg out.gif --frames 16 --tiles 6 --fps 8
    python tiler_cli.py upscale input.jpg out.png --scale 2 --filter lanczos
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Tuple

from PIL import Image

import tiler_toolkit as tt


def _parse_tile_size(args: argparse.Namespace, img_size: Tuple[int, int]) -> Tuple[int, int]:
    img_w, img_h = img_size
    if args.tile_width and args.tile_height:
        return args.tile_width, args.tile_height
    base = int(round(min(img_w, img_h) * args.tile_size))
    return args.tile_width or base, args.tile_height or base


def _add_common_tile_args(parser: argparse.ArgumentParser, default_tile_size: float = 0.25):
    parser.add_argument("input", help="Path to input image")
    parser.add_argument("output", help="Path for the generated file")
    parser.add_argument("--tile-width", type=int, help="Tile width in pixels")
    parser.add_argument("--tile-height", type=int, help="Tile height in pixels")
    parser.add_argument(
        "--tile-size",
        type=float,
        default=default_tile_size,
        help="Fraction of the smaller image dimension used when explicit width/height are omitted",
    )
    parser.add_argument("--min-scale", type=float, default=1.2)
    parser.add_argument("--max-scale", type=float, default=1.6)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--background", default=None, help="Optional background color; preserves alpha when omitted")


def cmd_single(args: argparse.Namespace):
    img = Image.open(args.input).convert("RGBA")
    tile_w, tile_h = _parse_tile_size(args, img.size)
    rng = random.Random(args.seed) if args.seed is not None else None
    result = tt.build_single_tile(
        img,
        tile_w=tile_w,
        tile_h=tile_h,
        min_scale=args.min_scale,
        max_scale=args.max_scale,
        background=args.background,
        rng=rng,
    )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    result.save(args.output)
    print(f"Saved single tile remix -> {args.output}")


def cmd_layers(args: argparse.Namespace):
    img = Image.open(args.input).convert("RGBA")
    tile_w, tile_h = _parse_tile_size(args, img.size)
    rng = random.Random(args.seed) if args.seed is not None else random.Random()
    result = tt.build_layered_tiles(
        img,
        tile_w=tile_w,
        tile_h=tile_h,
        tile_count=args.count,
        min_scale=args.min_scale,
        max_scale=args.max_scale,
        background=args.background,
        rng=rng,
        verbose=args.verbose,
    )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    result.save(args.output)
    print(f"Saved layered remix with {args.count} tiles -> {args.output}")


def cmd_gif(args: argparse.Namespace):
    img = Image.open(args.input).convert("RGBA")
    tile_w, tile_h = _parse_tile_size(args, img.size)
    frames = tt.build_animation_frames(
        img,
        frames=args.frames,
        tiles_per_frame=args.tiles,
        tile_w=tile_w,
        tile_h=tile_h,
        min_scale=args.min_scale,
        max_scale=args.max_scale,
        background=args.background,
        seed=args.seed,
        verbose=args.verbose,
    )
    tt.save_animation(frames, args.output, fps=args.fps)
    print(f"Saved animation with {args.frames} frames -> {args.output}")


def cmd_upscale(args: argparse.Namespace):
    img = Image.open(args.input)
    kwargs = {
        "mode": args.mode,
        "filter_name": args.filter,
        "background": args.background,
    }
    if args.scale:
        kwargs["scale"] = args.scale
    else:
        kwargs["width"] = args.width
        kwargs["height"] = args.height

    result = tt.upscale_image(img, **kwargs)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    result.save(args.output)
    print(f"Upscaled image saved -> {args.output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Swiss-army CLI built from the tiler prototypes")
    sub = parser.add_subparsers(dest="command", required=True)

    # single
    single = sub.add_parser("single", help="Generate one magnified tile and place it back onto a blank canvas")
    _add_common_tile_args(single)
    single.set_defaults(func=cmd_single)

    # layers
    layers = sub.add_parser("layers", help="Create a shuffled layered composite of magnified tiles")
    _add_common_tile_args(layers, default_tile_size=0.2)
    layers.add_argument("--count", type=int, default=5, help="Number of tiles to generate")
    layers.add_argument("--verbose", action="store_true")
    layers.set_defaults(func=cmd_layers)

    # gif
    gif = sub.add_parser("gif", help="Build a GIF of layered tile frames")
    _add_common_tile_args(gif, default_tile_size=0.2)
    gif.add_argument("--frames", type=int, default=12)
    gif.add_argument("--tiles", type=int, default=6, help="Tiles per frame")
    gif.add_argument("--fps", type=int, default=6)
    gif.add_argument("--verbose", action="store_true")
    gif.set_defaults(func=cmd_gif)

    # upscale
    upscale = sub.add_parser("upscale", help="Upscale an image using fit/fill/stretch modes")
    upscale.add_argument("input")
    upscale.add_argument("output")
    upscale.add_argument("--width", type=int)
    upscale.add_argument("--height", type=int)
    upscale.add_argument("--scale", type=float, help="Uniform scale factor; alternative to width/height")
    upscale.add_argument("--mode", choices=["fit", "fill", "stretch"], default="fit")
    upscale.add_argument("--filter", choices=["nearest", "bilinear", "bicubic", "lanczos"], default="lanczos")
    upscale.add_argument("--background", default="#000000")
    upscale.set_defaults(func=cmd_upscale)

    return parser


def main(argv: list[str] | None = None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "upscale" and not args.scale and (args.width is None or args.height is None):
        parser.error("upscale requires --scale or both --width and --height")

    args.func(args)


if __name__ == "__main__":
    main()
