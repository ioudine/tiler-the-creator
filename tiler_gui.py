#!/usr/bin/env python3
"""Lightweight Tkinter GUI for running tiler workflows locally."""
from __future__ import annotations

import random
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from PIL import Image

import tiler_toolkit as tt

RESAMPLE_CHOICES = ["nearest", "bilinear", "bicubic", "lanczos"]
UPSCALE_MODES = ["fit", "fill", "stretch"]


def _parse_int(value: str) -> Optional[int]:
    value = value.strip()
    if not value:
        return None
    return int(value)


def _parse_float(value: str) -> Optional[float]:
    value = value.strip()
    if not value:
        return None
    return float(value)


def _parse_seed(value: str) -> Optional[int]:
    return _parse_int(value)


def _rescale_if_needed(img: Image.Image, scale_var: tk.StringVar, width_var: tk.StringVar, height_var: tk.StringVar, filter_var: tk.StringVar) -> Image.Image:
    scale = _parse_float(scale_var.get())
    width = _parse_int(width_var.get())
    height = _parse_int(height_var.get())

    if scale is None and width is None and height is None:
        return img

    if scale is not None and (width is not None or height is not None):
        raise ValueError("Provide either input scale or both input width/height, not both.")

    if scale is None and (width is None or height is None):
        raise ValueError("Input width and height are both required when scale is omitted.")

    return tt.rescale_image(img, width=width, height=height, scale=scale, filter_name=filter_var.get())


def _compute_tile_size(img: Image.Image, tile_size_var: tk.StringVar, tile_w_var: tk.StringVar, tile_h_var: tk.StringVar) -> tuple[int, int]:
    img_w, img_h = img.size
    tile_w = _parse_int(tile_w_var.get())
    tile_h = _parse_int(tile_h_var.get())
    if tile_w is not None and tile_h is not None:
        return tile_w, tile_h

    fraction = float(tile_size_var.get() or 0.25)
    base = int(round(min(img_w, img_h) * fraction))
    return tile_w or base, tile_h or base


def _save_image(result: Image.Image, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path)


def _run_tiler(mode: str, state: dict[str, tk.StringVar], verbose: tk.BooleanVar):
    try:
        input_path = Path(state["input"].get())
        output_path = Path(state["output"].get())
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        if not output_path.suffix:
            raise ValueError("Output path must include a file extension.")

        if mode in {"single", "layers", "gif"}:
            img = Image.open(input_path).convert("RGBA")
            img = _rescale_if_needed(img, state["input_scale"], state["input_width"], state["input_height"], state["input_filter"])
            tile_w, tile_h = _compute_tile_size(img, state["tile_size"], state["tile_width"], state["tile_height"])
            min_scale = float(state["min_scale"].get() or 1.2)
            max_scale = float(state["max_scale"].get() or 1.6)
            background = state["background"].get() or None
            tile_filter = state["tile_filter"].get()
            seed = _parse_seed(state["seed"].get())

            if mode == "single":
                rng = random.Random(seed) if seed is not None else None
                result = tt.build_single_tile(
                    img,
                    tile_w=tile_w,
                    tile_h=tile_h,
                    min_scale=min_scale,
                    max_scale=max_scale,
                    background=background,
                    tile_filter=tile_filter,
                    rng=rng,
                )
                _save_image(result, output_path)
            elif mode == "layers":
                rng = random.Random(seed) if seed is not None else random.Random()
                count = int(state["count"].get() or 5)
                result = tt.build_layered_tiles(
                    img,
                    tile_w=tile_w,
                    tile_h=tile_h,
                    tile_count=count,
                    min_scale=min_scale,
                    max_scale=max_scale,
                    background=background,
                    tile_filter=tile_filter,
                    rng=rng,
                    verbose=verbose.get(),
                )
                _save_image(result, output_path)
            else:
                frames = int(state["frames"].get() or 12)
                tiles = int(state["tiles"].get() or 6)
                fps = int(state["fps"].get() or 6)
                frames_seq = tt.build_animation_frames(
                    img,
                    frames=frames,
                    tiles_per_frame=tiles,
                    tile_w=tile_w,
                    tile_h=tile_h,
                    min_scale=min_scale,
                    max_scale=max_scale,
                    background=background,
                    tile_filter=tile_filter,
                    seed=seed,
                    verbose=verbose.get(),
                )
                tt.save_animation(frames_seq, output_path, fps=fps)
        else:
            img = Image.open(input_path)
            mode_choice = state["mode"].get()
            filter_name = state["filter"].get()
            background = state["background"].get() or "#000000"
            kwargs: dict[str, float | int | str] = {
                "mode": mode_choice,
                "filter_name": filter_name,
                "background": background,
            }
            scale = _parse_float(state["scale"].get())
            width = _parse_int(state["width"].get())
            height = _parse_int(state["height"].get())
            if scale is not None:
                kwargs["scale"] = scale
            else:
                if width is None or height is None:
                    raise ValueError("Upscale requires either scale or both width and height.")
                kwargs["width"] = width
                kwargs["height"] = height

            result = tt.upscale_image(img, **kwargs)
            _save_image(result, output_path)

        messagebox.showinfo("Success", f"Saved output to {output_path}")
    except Exception as exc:  # noqa: BLE001 - surface user-friendly errors
        messagebox.showerror("Error", str(exc))


def _choose_input(var: tk.StringVar):
    path = filedialog.askopenfilename()
    if path:
        var.set(path)


def _choose_output(var: tk.StringVar):
    path = filedialog.asksaveasfilename(defaultextension=".png")
    if path:
        var.set(path)


def _build_shared_inputs(frame: ttk.Frame, state: dict[str, tk.StringVar]):
    ttk.Label(frame, text="Input").grid(row=0, column=0, sticky="e", padx=4, pady=2)
    ttk.Entry(frame, textvariable=state["input"], width=40).grid(row=0, column=1, sticky="we", padx=4, pady=2)
    ttk.Button(frame, text="Browse", command=lambda: _choose_input(state["input"])).grid(row=0, column=2, padx=4)

    ttk.Label(frame, text="Output").grid(row=1, column=0, sticky="e", padx=4, pady=2)
    ttk.Entry(frame, textvariable=state["output"], width=40).grid(row=1, column=1, sticky="we", padx=4, pady=2)
    ttk.Button(frame, text="Save As", command=lambda: _choose_output(state["output"])).grid(row=1, column=2, padx=4)


def _build_pre_scale(frame: ttk.LabelFrame, state: dict[str, tk.StringVar]):
    ttk.Label(frame, text="Scale").grid(row=0, column=0, sticky="e", padx=4, pady=2)
    ttk.Entry(frame, textvariable=state["input_scale"], width=8).grid(row=0, column=1, sticky="w", padx=4, pady=2)
    ttk.Label(frame, text="Width").grid(row=0, column=2, sticky="e", padx=4, pady=2)
    ttk.Entry(frame, textvariable=state["input_width"], width=8).grid(row=0, column=3, sticky="w", padx=4, pady=2)
    ttk.Label(frame, text="Height").grid(row=0, column=4, sticky="e", padx=4, pady=2)
    ttk.Entry(frame, textvariable=state["input_height"], width=8).grid(row=0, column=5, sticky="w", padx=4, pady=2)

    ttk.Label(frame, text="Filter").grid(row=0, column=6, sticky="e", padx=4, pady=2)
    ttk.OptionMenu(frame, state["input_filter"], state["input_filter"].get(), *RESAMPLE_CHOICES).grid(row=0, column=7, sticky="w", padx=4, pady=2)


def _build_tile_settings(frame: ttk.LabelFrame, state: dict[str, tk.StringVar]):
    ttk.Label(frame, text="Tile Size" ).grid(row=0, column=0, sticky="e", padx=4, pady=2)
    ttk.Entry(frame, textvariable=state["tile_size"], width=6).grid(row=0, column=1, sticky="w", padx=4, pady=2)
    ttk.Label(frame, text="Width").grid(row=0, column=2, sticky="e", padx=4, pady=2)
    ttk.Entry(frame, textvariable=state["tile_width"], width=6).grid(row=0, column=3, sticky="w", padx=4, pady=2)
    ttk.Label(frame, text="Height").grid(row=0, column=4, sticky="e", padx=4, pady=2)
    ttk.Entry(frame, textvariable=state["tile_height"], width=6).grid(row=0, column=5, sticky="w", padx=4, pady=2)

    ttk.Label(frame, text="Min Scale").grid(row=1, column=0, sticky="e", padx=4, pady=2)
    ttk.Entry(frame, textvariable=state["min_scale"], width=6).grid(row=1, column=1, sticky="w", padx=4, pady=2)
    ttk.Label(frame, text="Max Scale").grid(row=1, column=2, sticky="e", padx=4, pady=2)
    ttk.Entry(frame, textvariable=state["max_scale"], width=6).grid(row=1, column=3, sticky="w", padx=4, pady=2)

    ttk.Label(frame, text="Background").grid(row=1, column=4, sticky="e", padx=4, pady=2)
    ttk.Entry(frame, textvariable=state["background"], width=10).grid(row=1, column=5, sticky="w", padx=4, pady=2)

    ttk.Label(frame, text="Filter").grid(row=1, column=6, sticky="e", padx=4, pady=2)
    ttk.OptionMenu(frame, state["tile_filter"], state["tile_filter"].get(), *RESAMPLE_CHOICES).grid(row=1, column=7, sticky="w", padx=4, pady=2)

    ttk.Label(frame, text="Seed").grid(row=1, column=8, sticky="e", padx=4, pady=2)
    ttk.Entry(frame, textvariable=state["seed"], width=8).grid(row=1, column=9, sticky="w", padx=4, pady=2)


def _build_mode_specific(frame: ttk.Frame, mode: str, state: dict[str, tk.StringVar], verbose: tk.BooleanVar):
    for widget in frame.winfo_children():
        widget.destroy()

    if mode == "layers":
        ttk.Label(frame, text="Tile Count").grid(row=0, column=0, sticky="e", padx=4, pady=2)
        ttk.Entry(frame, textvariable=state["count"], width=6).grid(row=0, column=1, sticky="w", padx=4, pady=2)
        ttk.Checkbutton(frame, text="Verbose", variable=verbose).grid(row=0, column=2, padx=4, pady=2)
    elif mode == "gif":
        ttk.Label(frame, text="Frames").grid(row=0, column=0, sticky="e", padx=4, pady=2)
        ttk.Entry(frame, textvariable=state["frames"], width=6).grid(row=0, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(frame, text="Tiles/Frame").grid(row=0, column=2, sticky="e", padx=4, pady=2)
        ttk.Entry(frame, textvariable=state["tiles"], width=6).grid(row=0, column=3, sticky="w", padx=4, pady=2)
        ttk.Label(frame, text="FPS").grid(row=0, column=4, sticky="e", padx=4, pady=2)
        ttk.Entry(frame, textvariable=state["fps"], width=6).grid(row=0, column=5, sticky="w", padx=4, pady=2)
        ttk.Checkbutton(frame, text="Verbose", variable=verbose).grid(row=0, column=6, padx=4, pady=2)
    elif mode == "upscale":
        ttk.Label(frame, text="Width").grid(row=0, column=0, sticky="e", padx=4, pady=2)
        ttk.Entry(frame, textvariable=state["width"], width=8).grid(row=0, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(frame, text="Height").grid(row=0, column=2, sticky="e", padx=4, pady=2)
        ttk.Entry(frame, textvariable=state["height"], width=8).grid(row=0, column=3, sticky="w", padx=4, pady=2)
        ttk.Label(frame, text="Scale").grid(row=0, column=4, sticky="e", padx=4, pady=2)
        ttk.Entry(frame, textvariable=state["scale"], width=8).grid(row=0, column=5, sticky="w", padx=4, pady=2)
        ttk.Label(frame, text="Mode").grid(row=0, column=6, sticky="e", padx=4, pady=2)
        ttk.OptionMenu(frame, state["mode"], state["mode"].get(), *UPSCALE_MODES).grid(row=0, column=7, sticky="w", padx=4, pady=2)
        ttk.Label(frame, text="Filter").grid(row=0, column=8, sticky="e", padx=4, pady=2)
        ttk.OptionMenu(frame, state["filter"], state["filter"].get(), *RESAMPLE_CHOICES).grid(row=0, column=9, sticky="w", padx=4, pady=2)
        ttk.Label(frame, text="Background").grid(row=0, column=10, sticky="e", padx=4, pady=2)
        ttk.Entry(frame, textvariable=state["background"], width=10).grid(row=0, column=11, sticky="w", padx=4, pady=2)
    else:
        ttk.Label(frame, text="No extra options for single mode.").grid(row=0, column=0, padx=4, pady=2, sticky="w")


def main():
    root = tk.Tk()
    root.title("Tiler GUI")

    state: dict[str, tk.StringVar] = {
        "input": tk.StringVar(),
        "output": tk.StringVar(),
        "tile_size": tk.StringVar(value="0.25"),
        "tile_width": tk.StringVar(),
        "tile_height": tk.StringVar(),
        "min_scale": tk.StringVar(value="1.2"),
        "max_scale": tk.StringVar(value="1.6"),
        "background": tk.StringVar(),
        "tile_filter": tk.StringVar(value="lanczos"),
        "seed": tk.StringVar(),
        "input_scale": tk.StringVar(),
        "input_width": tk.StringVar(),
        "input_height": tk.StringVar(),
        "input_filter": tk.StringVar(value="lanczos"),
        "count": tk.StringVar(value="5"),
        "frames": tk.StringVar(value="12"),
        "tiles": tk.StringVar(value="6"),
        "fps": tk.StringVar(value="6"),
        "width": tk.StringVar(),
        "height": tk.StringVar(),
        "scale": tk.StringVar(),
        "mode": tk.StringVar(value="fit"),
        "filter": tk.StringVar(value="lanczos"),
    }
    verbose = tk.BooleanVar(value=False)
    mode_var = tk.StringVar(value="single")

    top_frame = ttk.Frame(root)
    top_frame.pack(fill="x", padx=8, pady=6)

    ttk.Label(top_frame, text="Mode").grid(row=0, column=0, padx=4, pady=2)
    ttk.OptionMenu(top_frame, mode_var, mode_var.get(), "single", "layers", "gif", "upscale").grid(row=0, column=1, padx=4, pady=2)

    paths = ttk.Frame(root)
    paths.pack(fill="x", padx=8, pady=4)
    _build_shared_inputs(paths, state)

    pre_scale = ttk.LabelFrame(root, text="Pre-scale input (single/layers/gif)")
    pre_scale.pack(fill="x", padx=8, pady=4)
    _build_pre_scale(pre_scale, state)

    tile_settings = ttk.LabelFrame(root, text="Tile settings (single/layers/gif)")
    tile_settings.pack(fill="x", padx=8, pady=4)
    _build_tile_settings(tile_settings, state)

    mode_frame = ttk.LabelFrame(root, text="Mode options")
    mode_frame.pack(fill="x", padx=8, pady=4)

    def update_defaults(*_args):
        mode = mode_var.get()
        if mode in {"layers", "gif"}:
            state["tile_size"].set("0.2")
        else:
            state["tile_size"].set("0.25")
        _build_mode_specific(mode_frame, mode, state, verbose)

    mode_var.trace_add("write", update_defaults)
    update_defaults()

    run_btn = ttk.Button(
        root,
        text="Run",
        command=lambda: _run_tiler(mode_var.get(), state, verbose),
    )
    run_btn.pack(pady=8)

    root.mainloop()


if __name__ == "__main__":
    main()
