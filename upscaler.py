#!/usr/bin/env python3
"""
Small utility to upsample an image to a specified resolution.

Features:
- Accepts either target width+height or a scale factor.
- Three resizing modes:
  * stretch - force the image into the requested size (may distort).
  * fit     - preserve aspect ratio, place image centered and pad with background color.
  * fill    - preserve aspect ratio, crop to fill the target (like "cover").
- Several resampling filters (nearest, bilinear, bicubic, lanczos).
- Saves output in the format implied by the output filename.

Requires: Pillow
    pip install pillow

Usage examples:
    # Upsample to 1920x1080, preserving aspect ratio and padding with black:
    python upsample_image.py input.jpg output.jpg --width 1920 --height 1080 --mode fit

    # Upsample by 2x using lanczos:
    python upsample_image.py in.png out.png --scale 2 --filter lanczos

    # Force-stretch to exact resolution:
    python upsample_image.py in.jpg out.jpg --width 800 --height 600 --mode stretch --filter bicubic
"""

from PIL import Image, ImageColor
import argparse
import sys
from typing import Tuple


FILTERS = {
    "nearest": Image.NEAREST,
    "bilinear": Image.BILINEAR,
    "bicubic": Image.BICUBIC,
    "lanczos": Image.LANCZOS,
}


def parse_args():
    p = argparse.ArgumentParser(description="Upsample an image to a target resolution.")
    p.add_argument("input", help="Path to input image")
    p.add_argument("output", help="Path to output image")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--scale", type=float, help="Scale factor (e.g. 2.0 to double dimensions)")
    group.add_argument("--width", type=int, help="Target width in pixels (requires --height)")
    p.add_argument("--height", type=int, help="Target height in pixels (required with --width)")
    p.add_argument("--mode",
                   choices=("stretch", "fit", "fill"),
                   default="lanczos" if False else "fit",
                   help="Resize mode: stretch (force), fit (pad), fill (crop). Default: fit")
    p.add_argument("--filter",
                   choices=list(FILTERS.keys()),
                   default="lanczos",
                   help="Resampling filter to use. Default: lanczos")
    p.add_argument("--bg", default="#000000",
                   help="Background color for padding (used with --mode fit). Accepts any CSS color. Default: black")
    return p.parse_args()


def compute_target_size(orig_size: Tuple[int, int], args) -> Tuple[int, int]:
    ow, oh = orig_size
    if args.scale:
        if args.scale <= 0:
            raise ValueError("scale must be positive")
        return int(round(ow * args.scale)), int(round(oh * args.scale))
    if args.width is None or args.height is None:
        raise ValueError("Both width and height must be provided when not using --scale")
    return args.width, args.height


def resize_stretch(img: Image.Image, target_size: Tuple[int, int], resample):
    return img.resize(target_size, resample=resample)


def resize_fit(img: Image.Image, target_size: Tuple[int, int], resample, bg_color):
    tw, th = target_size
    ow, oh = img.size
    # Compute scale to fit inside target
    scale = min(tw / ow, th / oh)
    new_w = int(round(ow * scale))
    new_h = int(round(oh * scale))
    resized = img.resize((new_w, new_h), resample=resample)
    # Create background and paste centered
    mode = "RGBA" if (img.mode in ("RGBA", "LA") or ("transparency" in img.info)) else "RGB"
    background = Image.new(mode, (tw, th), bg_color)
    # If resized has alpha but background is RGB, convert background to RGBA
    if resized.mode == "RGBA" and background.mode != "RGBA":
        background = background.convert("RGBA")
    paste_x = (tw - new_w) // 2
    paste_y = (th - new_h) // 2
    background.paste(resized, (paste_x, paste_y), resized if resized.mode == "RGBA" else None)
    return background


def resize_fill(img: Image.Image, target_size: Tuple[int, int], resample):
    tw, th = target_size
    ow, oh = img.size
    # Compute scale to cover target
    scale = max(tw / ow, th / oh)
    new_w = int(round(ow * scale))
    new_h = int(round(oh * scale))
    resized = img.resize((new_w, new_h), resample=resample)
    # Crop center to target size
    left = (new_w - tw) // 2
    top = (new_h - th) // 2
    return resized.crop((left, top, left + tw, top + th))


def main():
    args = parse_args()

    # Validate mode default choice bugfix: ensure default is 'fit' if not provided.
    if args.mode is None:
        args.mode = "fit"

    try:
        img = Image.open(args.input)
    except Exception as e:
        print(f"Failed to open input image: {e}", file=sys.stderr)
        sys.exit(2)

    try:
        target_size = compute_target_size(img.size, args)
    except Exception as e:
        print(f"Invalid target specification: {e}", file=sys.stderr)
        sys.exit(2)

    # Ensure we're "upsampling" (optional warning)
    ow, oh = img.size
    tw, th = target_size
    if tw < ow or th < oh:
        print("Warning: target size is smaller than the input for at least one dimension. "
              "This will downsample instead of upsample.", file=sys.stderr)

    filter_name = args.filter.lower()
    if filter_name not in FILTERS:
        print(f"Unknown filter '{args.filter}'. Valid: {', '.join(FILTERS.keys())}", file=sys.stderr)
        sys.exit(2)
    resample = FILTERS[filter_name]

    # Parse background color
    try:
        bg_color = ImageColor.getcolor(args.bg, "RGBA")
    except Exception:
        try:
            bg_color = ImageColor.getcolor(args.bg, "RGB")
        except Exception:
            print(f"Invalid background color: {args.bg}", file=sys.stderr)
            sys.exit(2)

    # Run chosen mode
    if args.mode == "stretch":
        out = resize_stretch(img, target_size, resample)
    elif args.mode == "fit":
        out = resize_fit(img, target_size, resample, bg_color)
    elif args.mode == "fill":
        out = resize_fill(img, target_size, resample)
    else:
        print(f"Unsupported mode: {args.mode}", file=sys.stderr)
        sys.exit(2)

    # Try to preserve format and quality where reasonable
    save_kwargs = {}
    fmt = None
    if "format" in img.info and img.format:
        fmt = img.format  # e.g., 'JPEG', 'PNG'
    # If output filename extension implies format, PIL will handle it automatically.
    try:
        out.save(args.output, **save_kwargs)
    except Exception as e:
        print(f"Failed to save output: {e}", file=sys.stderr)
        sys.exit(2)

    print(f"Saved upsampled image to {args.output} ({tw}x{th}), mode={args.mode}, filter={filter_name}")


if __name__ == "__main__":
    main()