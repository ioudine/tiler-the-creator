#!/usr/bin/env python3
"""
tile_zoom_gif.py

Generate multiple composited images from a single input photo (using the same settings each time
but allowing randomized tile placements/scales per frame), then assemble those images into a
short GIF animation.

Each frame is produced by:
 - sampling N rectangular tiles fully inside the source image,
 - magnifying each tile by a random scale between min-scale and max-scale,
 - flattening each tile to opaque RGB on the chosen background color,
 - shuffling the layer order randomly, and pasting the tiles (opaque) onto a background canvas
   the same size as the source image (later layers overwrite earlier ones).

Usage examples:
  python tile_zoom_gif.py input.jpg out.gif --frames 12 --tiles 6 --tile-size-percent 0.18 --min-scale 1.2 --max-scale 1.6 --duration 80 --seed 42
  python tile_zoom_gif.py input.jpg animation.gif --frames 20 --tiles 8 --background "#000000" --save-frames-dir frames/

Dependencies:
  pip install pillow

Author: Copied/derived from earlier tile_zoom_layers logic
"""
import argparse
import os
import random
from typing import Tuple, List
from PIL import Image

def parse_args():
    p = argparse.ArgumentParser(description="Produce several composited outputs from one photo and assemble them into a GIF.")
    p.add_argument("input_path", help="Input image file.")
    p.add_argument("output_gif", help="Output GIF path.")
    p.add_argument("--frames", type=int, default=12, help="Number of frames to generate.")
    p.add_argument("--tiles", type=int, default=5, help="Number of tiles (layers) per frame.")
    p.add_argument("--tile-w", type=int, default=None, help="Tile width in pixels (optional).")
    p.add_argument("--tile-h", type=int, default=None, help="Tile height in pixels (optional).")
    p.add_argument("--tile-size-percent", type=float, default=0.20,
                   help="Fraction of min(image_w,image_h) used when tile-w/tile-h are not set.")
    p.add_argument("--min-scale", type=float, default=1.2, help="Minimum magnification factor.")
    p.add_argument("--max-scale", type=float, default=1.6, help="Maximum magnification factor.")
    p.add_argument("--background", default="#ffffff",
                   help="Background color used to flatten tiles and for final canvas (hex or name). Default white.")
    p.add_argument("--duration", type=int, default=100,
                   help="Frame duration in milliseconds for the resulting GIF.")
    p.add_argument("--loop", type=int, default=0, help="GIF loop count (0 = infinite).")
    p.add_argument("--seed", type=int, default=None,
                   help="Optional integer seed for deterministic output. If provided, frames are generated using seeds seed + frame_index.")
    p.add_argument("--save-frames-dir", default=None,
                   help="Optional directory to save each intermediate frame as PNG for inspection.")
    p.add_argument("--verbose", action="store_true", help="Print per-frame and per-tile diagnostics.")
    return p.parse_args()

def choose_random_tile_position(rng: random.Random, img_w: int, img_h: int, tile_w: int, tile_h: int) -> Tuple[int,int,int,int]:
    """Return (left, top, center_x, center_y) where the tile is fully inside the image."""
    if tile_w > img_w or tile_h > img_h:
        raise ValueError("Tile size is larger than the image.")
    max_left = img_w - tile_w
    max_top = img_h - tile_h
    left = rng.randint(0, max_left)
    top = rng.randint(0, max_top)
    center_x = left + tile_w // 2
    center_y = top + tile_h // 2
    return left, top, center_x, center_y

def crop_and_scale_tile(src_img: Image.Image, left: int, top: int, tile_w: int, tile_h: int, scale: float) -> Image.Image:
    """Crop original tile and scale it by 'scale' returning an Image (RGBA or RGB depending on source)."""
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
    Ensures tiles have no transparency.
    """
    if tile.mode == "RGBA":
        bg = Image.new("RGB", tile.size, bg_color)
        bg.paste(tile, mask=tile.split()[-1])  # use alpha as mask
        return bg
    else:
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

def generate_single_frame(src_rgba: Image.Image,
                          img_w: int,
                          img_h: int,
                          tiles_count: int,
                          tile_w: int,
                          tile_h: int,
                          min_scale: float,
                          max_scale: float,
                          bg_color: str,
                          rng: random.Random,
                          verbose: bool = False):
    """
    Generate one composited RGB frame. Uses rng for all randomness to make generation deterministic
    for a given rng state.
    Returns an RGB Image.
    """
    # Generate tile entries
    tiles = []
    for i in range(tiles_count):
        left, top, center_x, center_y = choose_random_tile_position(rng, img_w, img_h, tile_w, tile_h)
        scale = rng.uniform(min_scale, max_scale)
        tile_resized = crop_and_scale_tile(src_rgba, left, top, tile_w, tile_h, scale)
        tile_opaque = flatten_tile_to_opaque(tile_resized, bg_color)
        tiles.append({
            "img": tile_opaque,
            "center": (center_x, center_y),
            "scale": scale,
            "orig_box": (left, top, left + tile_w, top + tile_h),
            "index": i,
        })
        if verbose:
            print(f"  [tile gen] idx={i} orig_box={(left,top,tile_w,tile_h)} center=({center_x},{center_y}) scale={scale:.3f} resized={tile_resized.size}")

    # Shuffle layer order using rng
    order = list(range(len(tiles)))
    rng.shuffle(order)
    if verbose:
        print(f"  [layer order] {order}")

    # Create opaque RGB canvas and paste
    canvas = Image.new("RGB", (img_w, img_h), bg_color)
    for layer_pos, idx in enumerate(order):
        entry = tiles[idx]
        paste_opaque_with_center(canvas, entry["img"], entry["center"][0], entry["center"][1])
        if verbose:
            print(f"   [paste] layer={layer_pos} -> tile#{entry['index']} center={entry['center']} size={entry['img'].size}")

    return canvas

def main():
    args = parse_args()

    if not os.path.exists(args.input_path):
        raise SystemExit(f"Input file not found: {args.input_path}")

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

    if args.min_scale <= 0 or args.max_scale <= 0 or args.min_scale > args.max_scale:
        raise SystemExit("Invalid scale range.")

    if args.save_frames_dir:
        os.makedirs(args.save_frames_dir, exist_ok=True)

    frames: List[Image.Image] = []

    # Create a base RNG if seed provided else use a nondeterministic RNG for frames
    base_seed = args.seed
    if base_seed is None:
        master_rng = random.Random()  # system-seeded
    else:
        master_rng = random.Random(base_seed)

    if args.verbose:
        print(f"Generating {args.frames} frames, each with {args.tiles} tiles (tile size {tile_w}x{tile_h}), background={args.background}")

    for fi in range(args.frames):
        # Derive a per-frame seed to ensure each frame differs but is reproducible when base seed is set
        frame_seed = master_rng.randint(0, 2**63 - 1)
        frame_rng = random.Random(frame_seed)
        if args.verbose:
            print(f"[frame {fi}] seed={frame_seed}")

        frame_img = generate_single_frame(
            src_rgba=src,
            img_w=img_w,
            img_h=img_h,
            tiles_count=args.tiles,
            tile_w=tile_w,
            tile_h=tile_h,
            min_scale=args.min_scale,
            max_scale=args.max_scale,
            bg_color=args.background,
            rng=frame_rng,
            verbose=args.verbose
        )

        # Optionally save each frame PNG for inspection
        if args.save_frames_dir:
            frame_path = os.path.join(args.save_frames_dir, f"frame_{fi:03d}.png")
            frame_img.save(frame_path)
            if args.verbose:
                print(f"  Saved intermediate frame: {frame_path}")

        frames.append(frame_img)

    # Convert frames to palette mode to make a compact GIF (Pillow will convert if necessary)
    frames_for_gif = [f.convert("P", palette=Image.ADAPTIVE, colors=256) for f in frames]

    # Save GIF
    first, rest = frames_for_gif[0], frames_for_gif[1:]
    save_kwargs = {
        "save_all": True,
        "append_images": rest,
        "duration": args.duration,
        "loop": args.loop,
        "optimize": False,
    }
    # Pillow will choose GIF by extension; enforce format param is optional
    first.save(args.output_gif, format="GIF", **save_kwargs)

    print(f"Saved GIF: {args.output_gif} ({img_w}x{img_h}), frames={len(frames)}, duration={args.duration}ms loop={args.loop}")
    if args.save_frames_dir:
        print(f"Intermediate frames saved to: {args.save_frames_dir}")

if __name__ == "__main__":
    main()
