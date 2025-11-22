"""Utility functions to remix the experimental tiler scripts into a reusable library.

The module exposes small helpers for the common operations implemented across the
prototype scripts:
* Random tile selection and scaling
* Layered tile compositing
* Animated tile sequences
* Image upscaling with padding/cropping rules

The functions are intentionally lightweight wrappers around Pillow so they can be
used by a CLI or imported into other projects.
"""
from __future__ import annotations

import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple

from PIL import Image


@dataclass
class TilePlacement:
    """Describes a tile cropped from the source image and how to paste it."""

    image: Image.Image
    center: Tuple[int, int]
    scale: float
    box: Tuple[int, int, int, int]


def _ensure_positive(value: int, name: str) -> int:
    if value <= 0:
        raise ValueError(f"{name} must be positive; got {value}")
    return value


def _resolve_resample(filter_name: str) -> int:
    filter_map = {
        "nearest": Image.NEAREST,
        "bilinear": Image.BILINEAR,
        "bicubic": Image.BICUBIC,
        "lanczos": Image.LANCZOS,
    }
    try:
        return filter_map[filter_name.lower()]
    except KeyError as exc:
        raise ValueError(f"Unknown filter '{filter_name}'") from exc


def rescale_image(
    img: Image.Image,
    *,
    width: int | None = None,
    height: int | None = None,
    scale: float | None = None,
    filter_name: str = "lanczos",
) -> Image.Image:
    """Resize ``img`` with a uniform scale factor or explicit dimensions."""

    if scale is None and (width is None or height is None):
        raise ValueError("Provide either scale or both width and height")
    if scale is not None and (width is not None or height is not None):
        raise ValueError("Specify either scale or width/height, not both")

    if scale is not None:
        if scale <= 0:
            raise ValueError("scale must be positive")
        width = max(1, int(round(img.size[0] * scale)))
        height = max(1, int(round(img.size[1] * scale)))

    assert width is not None and height is not None
    _ensure_positive(width, "width")
    _ensure_positive(height, "height")

    resample = _resolve_resample(filter_name)
    return img.resize((width, height), resample=resample)


def choose_random_tile_position(img_w: int, img_h: int, tile_w: int, tile_h: int) -> Tuple[int, int, int, int]:
    """Return (left, top, center_x, center_y) for a tile fully inside the image."""
    _ensure_positive(tile_w, "tile_w")
    _ensure_positive(tile_h, "tile_h")
    if tile_w > img_w or tile_h > img_h:
        raise ValueError("Tile size is larger than the image")

    max_left = img_w - tile_w
    max_top = img_h - tile_h
    left = random.randint(0, max_left)
    top = random.randint(0, max_top)
    center_x = left + tile_w // 2
    center_y = top + tile_h // 2
    return left, top, center_x, center_y


def crop_and_scale_tile(
    src_img: Image.Image,
    left: int,
    top: int,
    tile_w: int,
    tile_h: int,
    scale: float,
) -> Image.Image:
    right = left + tile_w
    bottom = top + tile_h
    tile = src_img.crop((left, top, right, bottom))
    new_w = max(1, int(round(tile_w * scale)))
    new_h = max(1, int(round(tile_h * scale)))
    return tile.resize((new_w, new_h), resample=Image.LANCZOS)


def paste_with_center(dest: Image.Image, src: Image.Image, center_x: int, center_y: int):
    """Paste ``src`` into ``dest`` so their centers align; crops when necessary."""
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
    mask = src_crop if src_crop.mode == "RGBA" else None
    dest.paste(src_crop, (dst_left, dst_top), mask)


def flatten_opaque(img: Image.Image, bg_color: str) -> Image.Image:
    """Ensure the tile is opaque by compositing onto ``bg_color``."""
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, bg_color)
        bg.paste(img, mask=img.split()[-1])
        return bg
    return img.convert("RGB")


def build_single_tile(
    src: Image.Image,
    tile_w: int,
    tile_h: int,
    min_scale: float,
    max_scale: float,
    background: str | None,
    rng: random.Random | None = None,
) -> Image.Image:
    rng = rng or random
    img_w, img_h = src.size
    left, top, center_x, center_y = choose_random_tile_position(img_w, img_h, tile_w, tile_h)
    scale = rng.uniform(min_scale, max_scale)
    tile = crop_and_scale_tile(src, left, top, tile_w, tile_h, scale)

    canvas = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    paste_with_center(canvas, tile, center_x, center_y)

    if background:
        final = Image.new("RGB", (img_w, img_h), background)
        final.paste(canvas, mask=canvas.split()[-1])
        return final
    return canvas


def build_layered_tiles(
    src: Image.Image,
    tile_w: int,
    tile_h: int,
    tile_count: int,
    min_scale: float,
    max_scale: float,
    background: str,
    rng: random.Random,
    verbose: bool = False,
) -> Image.Image:
    img_w, img_h = src.size
    placements: List[TilePlacement] = []
    for idx in range(tile_count):
        left, top, cx, cy = choose_random_tile_position(img_w, img_h, tile_w, tile_h)
        scale = rng.uniform(min_scale, max_scale)
        tile = crop_and_scale_tile(src, left, top, tile_w, tile_h, scale)
        placements.append(
            TilePlacement(
                image=flatten_opaque(tile, background),
                center=(cx, cy),
                scale=scale,
                box=(left, top, left + tile_w, top + tile_h),
            )
        )
        if verbose:
            print(f"tile#{idx}: box={left,top,tile_w,tile_h} center=({cx},{cy}) scale={scale:.3f} size={tile.size}")

    order = list(range(tile_count))
    rng.shuffle(order)
    if verbose:
        print(f"layer order: {order}")

    canvas = Image.new("RGB", (img_w, img_h), background)
    for layer_pos, idx in enumerate(order):
        placement = placements[idx]
        paste_with_center(canvas, placement.image, placement.center[0], placement.center[1])
        if verbose:
            print(f" paste layer {layer_pos} -> tile#{idx} size={placement.image.size}")
    return canvas


def build_animation_frames(
    src: Image.Image,
    frames: int,
    tiles_per_frame: int,
    tile_w: int,
    tile_h: int,
    min_scale: float,
    max_scale: float,
    background: str,
    seed: int | None = None,
    verbose: bool = False,
) -> List[Image.Image]:
    base_rng = random.Random(seed) if seed is not None else random.Random()
    result: List[Image.Image] = []
    for fi in range(frames):
        frame_seed = base_rng.randint(0, 2**63 - 1)
        frame_rng = random.Random(frame_seed)
        if verbose:
            print(f"[frame {fi}] seed={frame_seed}")
        frame = build_layered_tiles(
            src,
            tile_w=tile_w,
            tile_h=tile_h,
            tile_count=tiles_per_frame,
            min_scale=min_scale,
            max_scale=max_scale,
            background=background,
            rng=frame_rng,
            verbose=verbose,
        )
        result.append(frame)
    return result


def upscale_image(
    img: Image.Image,
    *,
    width: int | None = None,
    height: int | None = None,
    scale: float | None = None,
    mode: str = "fit",
    filter_name: str = "lanczos",
    background: str = "#000000",
) -> Image.Image:
    """Upscale ``img`` using the behaviour from ``upscaler.py``."""
    if scale is None and (width is None or height is None):
        raise ValueError("Provide either scale or both width and height")
    if scale is not None and (width is not None or height is not None):
        raise ValueError("Specify either scale or width/height, not both")

    src_w, src_h = img.size
    if scale is not None:
        width = int(round(src_w * scale))
        height = int(round(src_h * scale))
    assert width is not None and height is not None

    mode = mode.lower()
    if mode not in {"fit", "fill", "stretch"}:
        raise ValueError("mode must be one of fit|fill|stretch")

    resample = _resolve_resample(filter_name)

    if mode == "stretch":
        return img.resize((width, height), resample=resample)

    src_ratio = src_w / src_h
    target_ratio = width / height

    if mode == "fit":
        if src_ratio > target_ratio:
            new_w = width
            new_h = int(round(width / src_ratio))
        else:
            new_h = height
            new_w = int(round(height * src_ratio))
        resized = img.resize((new_w, new_h), resample=resample)
        canvas = Image.new("RGB", (width, height), background)
        offset = ((width - new_w) // 2, (height - new_h) // 2)
        canvas.paste(resized, offset)
        return canvas

    # fill
    if src_ratio > target_ratio:
        new_h = height
        new_w = int(round(height * src_ratio))
    else:
        new_w = width
        new_h = int(round(width / src_ratio))
    resized = img.resize((new_w, new_h), resample=resample)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    return resized.crop((left, top, left + width, top + height))


def save_animation(frames: Sequence[Image.Image], output_path: os.PathLike[str] | str, fps: int = 6):
    if not frames:
        raise ValueError("No frames to save")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    duration_ms = int(1000 / fps)
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
    )
