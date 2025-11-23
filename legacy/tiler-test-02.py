#!/usr/bin/env python3
"""
tile_zoom_layers.py

Generate multiple magnified tiles from a single input image, place each tile into a blank
frame (same size as the original) at the tile's original center, treat tiles as layers,
shuffle their layer order randomly, ensure tiles are fully opaque (no transparency), and
save the final composited image.

Usage:
  python tile_zoom_layers.py input.jpg output.png --count 8
  python tile_zoom_layers.py input.jpg output.jpg --count 5 --tile-size-percent 0.2 --min-scale 1.2 --max-scale 1.6 --seed 42 --background "#ffffff"

Arguments:
  input_path    Path to the existing image file.
  output_path   Path to write the final composited image.

Options:
  --count INT                Number of tiles/layers to generate (default 5).
  --tile-w INT               Tile width in pixels (optional).
  --tile-h INT               Tile height in pixels (optional).
  --tile-size-percent F      Fraction of min(image_w,image_h) for tile size if tile-w/--tile-h not set (default 0.20).
  --min-scale F              Minimum magnification (default 1.2).
  --max-scale F              Maximum magnification (default 1.6).
  --seed INT                 Random seed for reproducibility.
  --background COLOR         Background color for final image and to flatten tiles (default "#ffffff").
  --keep-seed-order          If set, the layer generation order is preserved and only final ordering is shuffled by seed.
  --verbose                  Print per-tile details while running.
"""

import argparse
import os
import random
from typing import List, Tuple
from PIL import Image

def parse_args():
    p = argparse.ArgumentParser(description="Generate multiple magnified tiles and composite as shuffled layers (opaque).")
    p.add_argument("input_path")
    p.add_argument("output_path")
    p.add_argument("--count", type=int, default=5, help="Number of tiles/layers to generate.")
    p.add_argument("--tile-w", type=int, default=None)
    p.add_argument("--tile-h", type=int, default=None)
    p.add_argument("--tile-size-percent", type=float, default=0.20,
                   help="Fraction of min(image_w,image_h) for tile size when tile-w/--tile-h are not provided.")
    p.add_argument("--min-scale", type=float, default=1.2)
    p.add_argument("--max-scale", type=float, default=1.6)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--background", default="#ffffff",
                   help="Background color used for final canvas and to flatten tiles (default white).")
    p.add_argument("--keep-seed-order", action="store_true",
                   help="Generate tiles in seeded order then shuffle layers; if not set behavior is fully randomized by seed.")
    p.add_argument("--verbose", action="store_true", help="Print per-tile diagnostics.")
    return p.parse_args()

def choose_random_tile_position(img_w: int, img_h: int, tile_w: int, tile_h: int) -> Tuple[int,int,int,int]:
    """Return (left, top, center_x, center_y) where the tile is fully inside the image."""
    if tile_w > img_w or tile_h > img_h:
        raise ValueError("Tile size is larger than the image.")
    max_left = img_w - tile_w
    max_top = img_h - tile_h
    left = random.randint(0, max_left)
    top = random.randint(0, max_top)
    center_x = left + tile_w // 2
    center_y = top + tile_h // 2
    return left, top, center_x, center_y

def crop_and_scale_tile(src_img: Image.Image, left: int, top: int, tile_w: int, tile_h: int, scale: float) -> Image.Image:
    """Crop original tile and scale it by 'scale' returning an Image (may be RGBA)."""
    right = left + tile_w
    bottom = top + tile_h
    tile = src_img.crop((left, top, right, bottom))
    new_w = max(1, int(round(tile_w * scale)))
    new_h = max(1, int(round(tile_h * scale)))
    tile_resized = tile.resize((new_w, new_h), resample=Image.LANCZOS)
    return tile_resized

def flatten_tile_to_opaque(tile: Image.Image, bg_color: str) -> Image.Image:
    """
    Return an opaque RGB image where tile (which might contain alpha) is flattened onto bg_color.
    This ensures tiles have 0 transparency in final compositing.
    """
    if tile.mode == "RGBA":
        # Create RGB background and paste using alpha as mask
        bg = Image.new("RGB", tile.size, bg_color)
        bg.paste(tile, mask=tile.split()[-1])  # alpha channel
        return bg
    else:
        # Already opaque (e.g., RGB)
        return tile.convert("RGB")

def paste_opaque_with_center(dest: Image.Image, src: Image.Image, center_x: int, center_y: int):
    """
    Paste src (RGB, opaque) into dest (RGB) so that src's center aligns with (center_x, center_y).
    Crops src if it would extend outside dest.
    """
    dest_w, dest_h = dest.size
    src_w, src_h = src.size
    paste_x = center_x - src_w // 2
    paste_y = center_y - src_h // 2

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

    if src_left >= src_right or src_top >= src_bottom:
        # No overlap
        return

    src_crop = src.crop((src_left, src_top, src_right, src_bottom))
    dest.paste(src_crop, (dst_left, dst_top))

def main():
    args = parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    if not os.path.exists(args.input_path):
        raise SystemExit(f"Input file not found: {args.input_path}")

    src = Image.open(args.input_path).convert("RGBA")
    img_w, img_h = src.size

    # Determine base tile size
    if args.tile_w is None or args.tile_h is None:
        base = int(round(min(img_w, img_h) * args.tile_size_percent))
        tile_w = args.tile_w if args.tile_w is not None else base
        tile_h = args.tile_h if args.tile_h is not None else base
    else:
        tile_w = args.tile_w
        tile_h = args.tile_h

    if tile_w <= 0 or tile_h <= 0:
        raise SystemExit("Tile width/height must be positive integers.")

    if args.min_scale <= 0 or args.max_scale <= 0 or args.min_scale > args.max_scale:
        raise SystemExit("Invalid scale range.")

    # Prepare list of generated tiles (each entry: dict with keys 'img', 'center', 'scale', 'orig_box', 'index')
    tiles = []

    # If user wants deterministic generation order separate from layer shuffle, we generate tiles first deterministically
    for i in range(args.count):
        left, top, center_x, center_y = choose_random_tile_position(img_w, img_h, tile_w, tile_h)
        scale = random.uniform(args.min_scale, args.max_scale)
        tile_resized = crop_and_scale_tile(src, left, top, tile_w, tile_h, scale)

        # Flatten to opaque RGB so tiles have 0 transparency
        tile_opaque = flatten_tile_to_opaque(tile_resized, args.background)

        tiles.append({
            "img": tile_opaque,
            "center": (center_x, center_y),
            "scale": scale,
            "orig_box": (left, top, left + tile_w, top + tile_h),
            "index": i,
        })
        if args.verbose:
            print(f"[gen] tile#{i}: orig_box={left,top,tile_w,tile_h} center={center_x,center_y} scale={scale:.3f} resized={tile_resized.size}")

    # Randomize layer order: shuffle list copy so generation list remains available if desired
    # Use a deterministic shuffle when seed provided
    layer_order = list(range(len(tiles)))
    random.shuffle(layer_order)

    if args.verbose:
        print(f"[info] layer order (shuffled): {layer_order}")

    # Create final canvas as opaque RGB using background color (final image will have no alpha)
    canvas = Image.new("RGB", (img_w, img_h), args.background)

    # Paste tiles in shuffled order; later tiles overwrite earlier ones (no blending)
    for layer_pos, idx in enumerate(layer_order):
        entry = tiles[idx]
        tile_img: Image.Image = entry["img"]
        cx, cy = entry["center"]

        paste_opaque_with_center(canvas, tile_img, cx, cy)
        if args.verbose:
            print(f"[paste] layer {layer_pos} -> tile#{entry['index']} center={cx,cy} tile_size={tile_img.size}")

    # Save final image. Force opaque output: JPEG/RGB or PNG/RGB (no alpha)
    out_ext = os.path.splitext(args.output_path)[1].lower()
    # If user asked for JPEG or omitted alpha, keep RGB; PNG will also be RGB here (no alpha).
    save_params = {}
    if out_ext in (".jpg", ".jpeg"):
        save_params["quality"] = 95
    elif out_ext == ".webp":
        save_params["quality"] = 95

    canvas.save(args.output_path, **save_params)

    # Print summary
    print(f"Saved final composited image to: {args.output_path} ({img_w}x{img_h})")
    print(f"Tiles generated: {len(tiles)}; layer order (shuffled): {layer_order}")
    if not args.verbose:
        # print basic per-tile summary
        for t in tiles:
            cx, cy = t["center"]
            w, h = t["img"].size
            print(f" tile#{t['index']}: center=({cx},{cy}) final_size={w}x{h} scale~{t['scale']:.3f}")

if __name__ == "__main__":
    main()
