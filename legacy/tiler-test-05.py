#!/usr/bin/env python3
"""
tile_zoom_gif_same_tiles.py

Generate a fixed set of magnified tiles once from a single input photo, then produce multiple
frames by re-ordering (shuffling) those same tiles' layer order for each frame, and assemble
the frames into a GIF animation.

This enhanced version adds two new features requested:
  1) unique permutations option: try to ensure each frame uses a unique permutation of the
     tile set until permutations are exhausted (or a practical limit is reached).
  2) animate subset option: choose a subset of tiles to animate across frames (their center and/or
     scale smoothly interpolate between start and target values). Non-animated tiles remain fixed.

Usage example:
  python tile_zoom_gif_same_tiles.py input.jpg out.gif --frames 24 --tiles 6 --animate-count 2 \
    --unique-permutations --duration 80 --seed 42 --save-frames-dir frames/

Notes:
 - Duration is in milliseconds per frame.
 - If --unique-permutations is used and the number of tiles is small enough, the script will
   enumerate permutations and sample without repeats. If that's impractical, it will try to
   generate unique permutations by random shuffling (with a pragmatic attempt limit).
 - Animated tiles are re-resized per-frame from the source image (so quality is preserved).
 - All tiles are flattened to opaque RGB using --background so final frames have no transparency.

Dependencies:
  pip install pillow
"""
from __future__ import annotations
import argparse
import itertools
import math
import os
import random
import sys
from typing import Dict, List, Tuple
from PIL import Image

def parse_args():
    p = argparse.ArgumentParser(description="Create GIF frames by shuffling a fixed set of tiles, with optional unique permutations and animating a subset of tiles.")
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

    # New options:
    p.add_argument("--unique-permutations", action="store_true",
                   help="Try to ensure each frame uses a unique permutation of the tile set until exhausted (practical limits apply).")
    p.add_argument("--animate-count", type=int, default=0,
                   help="Number of tiles (out of --tiles) to animate across frames. Animated tiles will have smoothly interpolated center offsets and scale.")
    p.add_argument("--animate-max-offset-frac", type=float, default=0.18,
                   help="Max translation for animated tiles as fraction of tile size (default 0.18).")
    p.add_argument("--animate-scale-delta-frac", type=float, default=0.25,
                   help="Max +/- fractional change to tile scale for animated tiles (default 0.25). e.g., 0.25 => scale varies up to +/-25%% from base).")
    return p.parse_args()

def choose_random_tile_position(rng: random.Random, img_w: int, img_h: int, tile_w: int, tile_h: int) -> Tuple[int,int,int,int]:
    if tile_w > img_w or tile_h > img_h:
        raise ValueError("Tile size is larger than the image.")
    left = rng.randint(0, img_w - tile_w)
    top = rng.randint(0, img_h - tile_h)
    center_x = left + tile_w // 2
    center_y = top + tile_h // 2
    return left, top, center_x, center_y

def crop_and_scale_tile_from_src(src_img: Image.Image, left: int, top: int, tile_w: int, tile_h: int, scale: float) -> Image.Image:
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

def factorial(n: int) -> int:
    return math.factorial(n)

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
        # Keep base parameters; we'll precompute an opaque "static" image for non-animated tiles.
        tile_resized = crop_and_scale_tile_from_src(src_rgba, left, top, tile_w, tile_h, scale)
        tile_opaque = flatten_tile_to_opaque(tile_resized, bg_color)
        tiles.append({
            "index": i,
            "left": left,
            "top": top,
            "tile_w": tile_w,
            "tile_h": tile_h,
            "base_center": (center_x, center_y),
            "base_scale": scale,
            "static_img": tile_opaque,  # opaque precomputed image for the base scale
            "orig_box": (left, top, left + tile_w, top + tile_h),
        })
        if verbose:
            print(f"[tile #{i}] box={left,top,tile_w,tile_h} center=({center_x},{center_y}) base_scale={scale:.3f} resized={tile_resized.size}")
    return tiles

def build_unique_orders(tiles_n: int, frames: int, rng: random.Random, verbose: bool = False) -> List[List[int]]:
    """
    Build a list of permutation orders.
    If possible and practical, enumerate all permutations and sample without replacement.
    Otherwise try to generate unique permutations by shuffling until frames are collected or attempts exhausted.
    """
    max_enum = 200_000  # don't enumerate more than this many permutations
    orders: List[List[int]] = []

    total_perms = factorial(tiles_n)
    if verbose:
        print(f"[perm] tiles={tiles_n} total_perms={total_perms}, requested frames={frames}")

    if frames <= total_perms and total_perms <= max_enum:
        # enumerate all permutations and sample frames many
        if verbose:
            print("[perm] enumerating all permutations and sampling without replacement")
        all_perms = list(itertools.permutations(range(tiles_n)))
        rng.shuffle(all_perms)
        for p in all_perms[:frames]:
            orders.append(list(p))
        return orders

    # Fallback: try to generate unique permutations by random shuffles
    seen = set()
    attempts = 0
    max_attempts = max(1000, frames * 50)
    if verbose:
        print(f"[perm] generating unique permutations by random shuffle (max_attempts={max_attempts})")
    while len(orders) < frames and attempts < max_attempts:
        candidate = list(range(tiles_n))
        rng.shuffle(candidate)
        tup = tuple(candidate)
        attempts += 1
        if tup in seen:
            continue
        seen.add(tup)
        orders.append(candidate.copy())
    if len(orders) < frames and verbose:
        print(f"[perm] Warning: could only generate {len(orders)} unique permutations after {attempts} attempts.")
    return orders

def ease_smooth_sine(t: float) -> float:
    # Smooth sinusoidal easing from 0..1: 0.5 * (1 - cos(pi * t)) gives ease-in-out over [0,1]
    return 0.5 * (1 - math.cos(math.pi * t))

def main():
    args = parse_args()

    if not os.path.exists(args.input_path):
        raise SystemExit(f"Input file not found: {args.input_path}")

    # Validate args
    if args.tiles <= 0 or args.frames <= 0:
        raise SystemExit("tiles and frames must be >= 1")
    if args.animate_count < 0 or args.animate_count > args.tiles:
        raise SystemExit("animate-count must be between 0 and --tiles")
    if args.min_scale <= 0 or args.max_scale <= 0 or args.min_scale > args.max_scale:
        raise SystemExit("Invalid scale range")

    # Prepare RNG
    master_rng = random.Random(args.seed) if args.seed is not None else random.Random()

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

    if args.save_frames_dir:
        os.makedirs(args.save_frames_dir, exist_ok=True)

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

    # Choose which tiles to animate (by index)
    animate_indices: List[int] = []
    if args.animate_count > 0:
        # pick animate_count distinct indices
        all_indices = list(range(len(tiles)))
        master_rng.shuffle(all_indices)
        animate_indices = all_indices[:args.animate_count]
        if args.verbose:
            print(f"[animate] selected indices to animate: {animate_indices}")

    # For each animated tile, generate animation targets (translation dx,dy and scale multiplier)
    anim_specs: Dict[int, Dict] = {}
    for idx in animate_indices:
        t = tiles[idx]
        # max offset in pixels is fraction of tile size
        max_dx = int(round(t["tile_w"] * args.animate_max_offset_frac))
        max_dy = int(round(t["tile_h"] * args.animate_max_offset_frac))
        dx = master_rng.randint(-max_dx, max_dx)
        dy = master_rng.randint(-max_dy, max_dy)
        # scale delta fraction (e.g., 0.25 means +/-25%)
        delta_frac = args.animate_scale_delta_frac
        scale_target = t["base_scale"] * (1.0 + master_rng.uniform(-delta_frac, delta_frac))
        # We'll animate smoothly from base -> target -> base for looping continuity by using a sine ease over 0..1
        anim_specs[idx] = {
            "dx": dx,
            "dy": dy,
            "scale_target": scale_target,
            "base_scale": t["base_scale"],
        }
        if args.verbose:
            print(f"[anim-spec] tile#{idx}: dx={dx} dy={dy} base_scale={t['base_scale']:.3f} target_scale={scale_target:.3f}")

    # Build orders for each frame
    if args.unique_permutations:
        orders = build_unique_orders(len(tiles), args.frames, master_rng, verbose=args.verbose)
        # If we couldn't build enough unique orders, we will fill remaining frames by random shuffles
        if len(orders) < args.frames:
            if args.verbose:
                print(f"[perm] filling remaining {args.frames - len(orders)} frames with random shuffles")
            while len(orders) < args.frames:
                cand = list(range(len(tiles)))
                master_rng.shuffle(cand)
                orders.append(cand)
    else:
        # simple per-frame RNG-shuffle using derived per-frame seeds for reproducibility
        orders = []
        for fi in range(args.frames):
            frame_seed = master_rng.randint(0, 2**63 - 1)
            frame_rng = random.Random(frame_seed)
            order = list(range(len(tiles)))
            frame_rng.shuffle(order)
            orders.append(order)
            if args.verbose:
                print(f"[frame-order] frame={fi} seed={frame_seed} order={order}")

    # Generate frames
    frames: List[Image.Image] = []
    for fi in range(args.frames):
        if args.verbose:
            print(f"[frame] generating frame {fi+1}/{args.frames}")

        # Create canvas
        canvas = Image.new("RGB", (img_w, img_h), args.background)

        # Compute per-frame images for animated tiles (others use precomputed static_img)
        per_frame_imgs: Dict[int, Image.Image] = {}

        for idx in animate_indices:
            spec = anim_specs[idx]
            t_tile = tiles[idx]
            # normalized time 0..1 across frames; for smooth loop use sine easing with full-period
            if args.frames == 1:
                tt = 0.0
            else:
                tt = fi / (args.frames - 1)
            eased = ease_smooth_sine(tt)  # 0..1
            # compute center offset and scale at this frame
            cx_base, cy_base = t_tile["base_center"]
            cx = int(round(cx_base + spec["dx"] * eased))
            cy = int(round(cy_base + spec["dy"] * eased))
            scale = t_tile["base_scale"] + (spec["scale_target"] - t_tile["base_scale"]) * eased

            # crop and resize from source to keep quality
            img_resized = crop_and_scale_tile_from_src(src, t_tile["left"], t_tile["top"], t_tile["tile_w"], t_tile["tile_h"], scale)
            img_opaque = flatten_tile_to_opaque(img_resized, args.background)
            per_frame_imgs[idx] = {
                "img": img_opaque,
                "center": (cx, cy),
            }
            if args.verbose:
                print(f"  [anim] tile#{idx} frame#{fi} center=({cx},{cy}) scale={scale:.3f} size={img_opaque.size}")

        # Paste tiles in the order specified for this frame
        order = orders[fi]
        for layer_pos, idx in enumerate(order):
            if idx in per_frame_imgs:
                entry_img = per_frame_imgs[idx]["img"]
                cx, cy = per_frame_imgs[idx]["center"]
            else:
                entry_img = tiles[idx]["static_img"]
                cx, cy = tiles[idx]["base_center"]
            paste_opaque_with_center(canvas, entry_img, cx, cy)
            if args.verbose:
                print(f"   [paste] layer {layer_pos} -> tile#{idx} center=({cx},{cy}) size={entry_img.size}")

        # Optionally save intermediate frame
        if args.save_frames_dir:
            frame_path = os.path.join(args.save_frames_dir, f"frame_{fi:03d}.png")
            canvas.save(frame_path)
            if args.verbose:
                print(f"  saved frame PNG: {frame_path}")

        frames.append(canvas)

    # Convert frames for GIF and save
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
    if args.save_frames_dir:
        print(f"Intermediate frames saved to: {args.save_frames_dir}")

if __name__ == "__main__":
    main()
