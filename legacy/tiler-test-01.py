#!/usr/bin/env python3
"""
tile_zoom.py

Open a local image, pick a random rectangular tile inside it, magnify that tile by a random
factor between 1.2 and 1.6, create a blank frame the same size as the original image, and
place the magnified tile into that frame so the magnified tile's center matches the original
tile's center.

Usage:
  python tile_zoom.py input.jpg output.png
  python tile_zoom.py input.jpg output.png --tile-w 200 --tile-h 150 --seed 42 --min-scale 1.3 --max-scale 1.5

Arguments / options:
  input_path      Path to the existing local image file.
  output_path     Path where the result will be written.

Options:
  --tile-w INT            Tile width in pixels. If omitted, uses tile-size-percent of min(image_w, image_h).
  --tile-h INT            Tile height in pixels. If omitted, uses tile-size-percent of min(image_w, image_h).
  --tile-size-percent F   Fraction of min(image_w,image_h) to use for both tile dimensions (default 0.25).
  --min-scale F           Minimum magnification (default 1.2).
  --max-scale F           Maximum magnification (default 1.6).
  --seed INT              Random seed for reproducibility.
  --background COLOR      Optional background color for the blank frame (hex or name). If omitted, the frame is transparent (saved as PNG/WebP) or white for JPEG output.
"""

import argparse
import os
import random
from PIL import Image

def parse_args():
    p = argparse.ArgumentParser(description="Extract a random tile, magnify it, and paste into a blank frame at the same center.")
    p.add_argument("input_path")
    p.add_argument("output_path")
    p.add_argument("--tile-w", type=int, default=None)
    p.add_argument("--tile-h", type=int, default=None)
    p.add_argument("--tile-size-percent", type=float, default=0.25,
                   help="Fraction of min(image_w,image_h) to use for tile width and height when --tile-w/--tile-h aren't set.")
    p.add_argument("--min-scale", type=float, default=1.2)
    p.add_argument("--max-scale", type=float, default=1.6)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--background", default=None,
                   help="Background color (hex like '#ffffff' or color name). If omitted, use transparent for formats that support it.")
    return p.parse_args()

def choose_random_tile_position(img_w, img_h, tile_w, tile_h):
    """Return integer (left, top, center_x, center_y) for a tile fully inside the image."""
    if tile_w > img_w or tile_h > img_h:
        raise ValueError("Tile size is larger than the image.")
    max_left = img_w - tile_w
    max_top = img_h - tile_h
    left = random.randint(0, max_left)
    top = random.randint(0, max_top)
    center_x = left + tile_w // 2
    center_y = top + tile_h // 2
    return left, top, center_x, center_y

def paste_with_center(dest_img, src_img, center_x, center_y):
    """
    Paste src_img into dest_img so that src_img's center aligns with (center_x, center_y) on dest_img.
    Handles cases where src_img extends beyond dest_img borders by cropping.
    Both images are PIL Images. dest_img is modified in place.
    """
    dest_w, dest_h = dest_img.size
    src_w, src_h = src_img.size

    paste_x = center_x - src_w // 2
    paste_y = center_y - src_h // 2

    # Compute overlapping region between src and dest
    src_left = 0
    src_top = 0
    dst_left = paste_x
    dst_top = paste_y

    if paste_x < 0:
        src_left = -paste_x
        dst_left = 0
    if paste_y < 0:
        src_top = -paste_y
        dst_top = 0

    src_right = src_w
    src_bottom = src_h
    if paste_x + src_w > dest_w:
        src_right = src_w - ((paste_x + src_w) - dest_w)
    if paste_y + src_h > dest_h:
        src_bottom = src_h - ((paste_y + src_h) - dest_h)

    # If there's no overlap, nothing to paste
    if src_left >= src_right or src_top >= src_bottom:
        return

    src_crop = src_img.crop((src_left, src_top, src_right, src_bottom))
    dest_img.paste(src_crop, (dst_left, dst_top), src_crop if src_crop.mode == "RGBA" else None)

def main():
    args = parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    if not os.path.exists(args.input_path):
        raise SystemExit(f"Input file not found: {args.input_path}")

    # Open input image as RGBA for safe processing (keeps transparency if present)
    src = Image.open(args.input_path).convert("RGBA")
    img_w, img_h = src.size

    # Determine tile size
    if args.tile_w is None or args.tile_h is None:
        base = int(round(min(img_w, img_h) * args.tile_size_percent))
        tile_w = args.tile_w if args.tile_w is not None else base
        tile_h = args.tile_h if args.tile_h is not None else base
    else:
        tile_w = args.tile_w
        tile_h = args.tile_h

    if tile_w <= 0 or tile_h <= 0:
        raise SystemExit("Tile width/height must be positive integers.")

    # Choose random tile position fully inside image
    left, top, center_x, center_y = choose_random_tile_position(img_w, img_h, tile_w, tile_h)
    right = left + tile_w
    bottom = top + tile_h

    tile = src.crop((left, top, right, bottom))

    # Choose random scale
    min_s = args.min_scale
    max_s = args.max_scale
    if min_s <= 0 or max_s <= 0 or min_s > max_s:
        raise SystemExit("Invalid scale range.")
    scale = random.uniform(min_s, max_s)

    new_w = max(1, int(round(tile_w * scale)))
    new_h = max(1, int(round(tile_h * scale)))
    tile_resized = tile.resize((new_w, new_h), resample=Image.LANCZOS)

    # Create blank frame (RGBA). Use provided background when saving to non-alpha formats.
    out_mode = "RGBA"
    canvas = Image.new(out_mode, (img_w, img_h), (0, 0, 0, 0))

    # Paste the magnified tile so its center aligns with original center
    paste_with_center(canvas, tile_resized, center_x, center_y)

    # Prepare for saving: if output is JPEG force RGB and use background if provided else white
    out_ext = os.path.splitext(args.output_path)[1].lower()
    if out_ext in (".jpg", ".jpeg"):
        bg = args.background or "#ffffff"
        final = Image.new("RGB", (img_w, img_h), bg)
        final.paste(canvas, mask=canvas.split()[-1])  # use alpha channel as mask
        final.save(args.output_path, quality=95)
    else:
        # If user provided a background color and asked for a non-alpha format (or still wants bg),
        # flatten to that background; otherwise preserve alpha.
        if args.background is not None:
            bg = args.background
            final = Image.new("RGBA", (img_w, img_h), bg)
            final.paste(canvas, mask=canvas.split()[-1])
            # If output format doesn't support alpha (rare here), convert later; for typical formats PNG supports RGBA.
            final.save(args.output_path)
        else:
            # Save with alpha preserved
            canvas.save(args.output_path)

    # Print summary to stdout
    print(f"Input image: {args.input_path} ({img_w}x{img_h})")
    print(f"Tile extracted: left={left}, top={top}, w={tile_w}, h={tile_h}")
    print(f"Tile center: x={center_x}, y={center_y}")
    print(f"Scale applied: {scale:.4f} -> resized tile {new_w}x{new_h}")
    print(f"Saved output to: {args.output_path}")

if __name__ == "__main__":
    main()
