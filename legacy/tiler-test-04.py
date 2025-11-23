#!/usr/bin/env python3
"""
tile_zoom_gif_same_tiles.py

Generate a set of magnified tiles once from a single input photo, then produce multiple frames
by re-ordering (shuffling) those same tiles' layer order for each frame, and finally assemble
the frames into a GIF animation.

Per-frame differences come only from the layer ordering; tile crops/scales/positions are fixed
across frames (they are sampled once at the start). Tiles are flattened to opaque RGB so the
final frames have no transparency.

Usage example:
  python tile_zoom_gif_same_tiles.py input.jpg out.gif --frames 16 --tiles 6 --tile-size-percent 0.18 --min-scale 1.2 --max-scale 1.6 --duration 100 --seed 42

Options:
 - Duration is in milliseconds (GIF delays are quantized to 10ms steps by most encoders/viewers).
 - If frames exceeds the number of unique permutations of the tile set, permutations will repeat.
"""
from __future__ import annotations
import argparse
import os
import random
from typing import Tuple, List, Dict
from PIL import Image

def parse_args():
    p = argparse.ArgumentParser(description="Create GIF frames by shuffling a fixed set of tiles sampled from one photo.")
    p.add_argument("input_path")
    p.add_argument("output_gif")
    p.add_argument("--frames", type=int, default=12)
    p.add_argument("--tiles", type=int, default=5)
    p.add_argument("--tile-w", type=int, default=None)
    p.add_argument("--tile-h", type=int, default=None)
    p.add_argument("--tile-size-percent", type=float, default=0.20)
    p.add_argument("--min-scale", type=float, default=1.2)
    p.add_argument("--max-scale", type=float, default=1.6)
    p.add_argument("--background", default="#ffffff")
    p.add_argument("--duration", type=int, default=100)
    p.add_argument("--loop", type=int, default=0)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--save-frames-dir", default=None)
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()

def choose_random_tile_position(rng: random.Random, img_w: int, img_h: int, tile_w: int, tile_h: int) -> Tuple[int,int,int,int]:
    if tile_w > img_w or tile_h > img_h:
        raise ValueError("Tile size is larger than the image.")
    left = rng.randint(0, img_w - tile_w)
    top = rng.randint(0, img_h - tile_h)
    center_x = left + tile_w // 2
    center_y = top + tile_h // 2
    return left, top, center_x, center_y

def crop_and_scale_tile(src_img: Image.Image, left: int, top: int, tile_w: int, tile_h: int, scale: float) -> Image.Image:
    right = left + tile_w
    bottom = top + tile_h
    tile = src_img.crop((left, top, right, bottom))
    new_w = max(1, int(round(tile_w * scale)))
    new_h = max(1, int(round(tile_h * scale)))
    return tile.resize((new_w, new_h), resample=Image.LANCZOS)

def flatten_tile_to_opaque(tile: Image.Image, bg_color: str) -> Image.Image:
    if tile.mode == "RGBA":
        bg = Image.new("RGB", tile.size, bg_color)
        bg.paste(tile, mask=tile.split()[-1])
        return bg
    else:
        return tile.convert("RGB")

def paste_opaque_with_center(dest: Image.Image, src: Image.Image, center_x: int, center_y: int):
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
        return

    src_crop = src.crop((src_left, src_top, src_right, src_bottom))
    dest.paste(src_crop, (dst_left, dst_top))

def generate_tiles_once(src_rgba: Image.Image,
                        tiles_count: int,
                        tile_w: int,
                        tile_h: int,
                        min_scale: float,
                        max_scale: float,
                        bg_color: str,
                        rng: random.Random,
                        verbose: bool = False) -> List[Dict]:
    img_w, img_h = src_rgba.size
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
            print(f"[tile #{i}] box={left,top,tile_w,tile_h} center=({center_x},{center_y}) scale={scale:.3f} resized={tile_resized.size}")
    return tiles

def main():
    args = parse_args()

    if not os.path.exists(args.input_path):
        raise SystemExit(f"Input file not found: {args.input_path}")

    src = Image.open(args.input_path).convert("RGBA")
    img_w, img_h = src.size

    # tile sizing
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
    if args.tiles <= 0:
        raise SystemExit("Tiles must be >= 1.")
    if args.frames <= 0:
        raise SystemExit("Frames must be >= 1.")

    if args.save_frames_dir:
        os.makedirs(args.save_frames_dir, exist_ok=True)

    # deterministic master RNG if seed given
    if args.seed is None:
        master_rng = random.Random()
    else:
        master_rng = random.Random(args.seed)

    # Generate tiles once
    tiles = generate_tiles_once(
        src_rgba=src,
        tiles_count=args.tiles,
        tile_w=tile_w,
        tile_h=tile_h,
        min_scale=args.min_scale,
        max_scale=args.max_scale,
        bg_color=args.background,
        rng=master_rng,
        verbose=args.verbose
    )

    if args.verbose:
        print(f"Generated {len(tiles)} tiles once; producing {args.frames} frames by shuffling their order.")

    frames = []
    for fi in range(args.frames):
        # derive a reproducible per-frame RNG from master_rng so GIF is reproducible with a single seed
        frame_seed = master_rng.randint(0, 2**63 - 1)
        frame_rng = random.Random(frame_seed)
        order = list(range(len(tiles)))
        frame_rng.shuffle(order)
        if args.verbose:
            print(f"[frame {fi}] seed={frame_seed} order={order}")

        canvas = Image.new("RGB", (img_w, img_h), args.background)
        # paste tiles in this order (later tiles overwrite earlier ones)
        for layer_pos, idx in enumerate(order):
            entry = tiles[idx]
            paste_opaque_with_center(canvas, entry["img"], entry["center"][0], entry["center"][1])
            if args.verbose:
                print(f"  pasted layer {layer_pos} -> tile#{entry['index']} center={entry['center']} size={entry['img'].size}")

        if args.save_frames_dir:
            frame_path = os.path.join(args.save_frames_dir, f"frame_{fi:03d}.png")
            canvas.save(frame_path)
            if args.verbose:
                print(f"  saved frame PNG: {frame_path}")

        frames.append(canvas)

    # Convert to palette mode for GIF
    frames_for_gif = [f.convert("P", palette=Image.ADAPTIVE, colors=256) for f in frames]
    first, rest = frames_for_gif[0], frames_for_gif[1:]
    save_kwargs = {
        "save_all": True,
        "append_images": rest,
        "duration": args.duration,
        "loop": args.loop,
        "optimize": False,
    }
    first.save(args.output_gif, format="GIF", **save_kwargs)
    print(f"Saved GIF: {args.output_gif} ({img_w}x{img_h}), frames={len(frames)}, tiles={len(tiles)}, duration={args.duration}ms loop={args.loop}")

if __name__ == "__main__":
    main()
