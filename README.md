# Tiler CLI

`tiler_cli.py` exposes the experimental tiler scripts behind a single command-line interface. Use it to remix images with magnified tiles, generate layered composites or GIF animations, and upscale results with different resize modes.

## Quick start

```bash
python tiler_cli.py <command> [options]
```

To launch a simple desktop UI for local experimentation, run:

```
python tiler_gui.py
Note: older example/test scripts and utilities have been moved to the `legacy/` folder.

```

### Requirements

- Python 3.9+.
- [Pillow](https://pillow.readthedocs.io/) for image processing. Install with `pip install pillow`.
- NumPy is **not** required; all operations rely solely on Pillow.

If you are working inside a virtual environment, install dependencies locally to avoid conflicts with system packages.

Every command accepts an input image path and an output path. Generated files and parent directories are created automatically.

## Commands and options

### `single`
Create a single magnified tile and place it back onto a blank canvas.

```
python tiler_cli.py single input.jpg out.png [options]
```

Positional arguments:
- `input`: Path to the source image.
- `output`: Destination path for the remixed image.

Options:
- `--tile-width <int>`: Tile width in pixels. Defaults to a fraction of the smaller image dimension.
- `--tile-height <int>`: Tile height in pixels. Defaults to a fraction of the smaller image dimension.
- `--tile-size <float>`: Fraction of the smaller image dimension used when `--tile-width`/`--tile-height` are omitted. Default: `0.25`.
- `--min-scale <float>`: Minimum random scale factor applied to the tile. Default: `1.2`.
- `--max-scale <float>`: Maximum random scale factor applied to the tile. Default: `1.6`.
- `--seed <int>`: Seed for deterministic randomness. Omit for non-deterministic runs.
- `--background <color>`: Background color; preserves the image alpha if omitted (e.g., `"#000000"`).
- `--tile-filter {nearest,bilinear,bicubic,lanczos}`: Resampling filter used when scaling cropped tiles. Default: `lanczos`.
- `--input-scale <float>`: Uniform scale factor applied to the input before tiling. Provide this **or** both `--input-width` and `--input-height`.
- `--input-width <int>`/`--input-height <int>`: Dimensions to rescale the input image before tiling.
- `--input-filter {nearest,bilinear,bicubic,lanczos}`: Resampling filter used for pre-scaling. Default: `lanczos`.

### `layers`
Create a shuffled layered composite of magnified tiles.

```
python tiler_cli.py layers input.jpg out.png [options]
```

Positional arguments:
- `input`: Path to the source image.
- `output`: Destination path for the layered composite.

Options:
- `--tile-width <int>`: Tile width in pixels. Defaults to a fraction of the smaller image dimension.
- `--tile-height <int>`: Tile height in pixels. Defaults to a fraction of the smaller image dimension.
- `--tile-size <float>`: Fraction of the smaller image dimension used when `--tile-width`/`--tile-height` are omitted. Default: `0.2`.
- `--min-scale <float>`: Minimum random scale factor applied to each tile. Default: `1.2`.
- `--max-scale <float>`: Maximum random scale factor applied to each tile. Default: `1.6`.
- `--count <int>`: Number of tiles to generate. Default: `5`.
- `--seed <int>`: Seed for deterministic randomness. Defaults to a new random seed when omitted.
- `--background <color>`: Background color; preserves the image alpha if omitted.
- `--tile-filter {nearest,bilinear,bicubic,lanczos}`: Resampling filter used when scaling cropped tiles. Default: `lanczos`.
- `--input-scale <float>`: Uniform scale factor applied to the input before tiling. Provide this **or** both `--input-width` and `--input-height`.
- `--input-width <int>`/`--input-height <int>`: Dimensions to rescale the input image before tiling.
- `--input-filter {nearest,bilinear,bicubic,lanczos}`: Resampling filter used for pre-scaling. Default: `lanczos`.
- `--verbose`: Print tile placement details as frames are assembled.

### `gif`
Build a GIF of layered tile frames.

```
python tiler_cli.py gif input.jpg out.gif [options]
```

Positional arguments:
- `input`: Path to the source image.
- `output`: Destination path for the GIF animation.

Options:
- `--tile-width <int>`: Tile width in pixels. Defaults to a fraction of the smaller image dimension.
- `--tile-height <int>`: Tile height in pixels. Defaults to a fraction of the smaller image dimension.
- `--tile-size <float>`: Fraction of the smaller image dimension used when `--tile-width`/`--tile-height` are omitted. Default: `0.2`.
- `--min-scale <float>`: Minimum random scale factor applied to each tile. Default: `1.2`.
- `--max-scale <float>`: Maximum random scale factor applied to each tile. Default: `1.6`.
- `--frames <int>`: Number of frames in the animation. Default: `12`.
- `--tiles <int>`: Tiles per frame. Default: `6`.
- `--fps <int>`: Frames per second when encoding the GIF. Default: `6`.
- `--seed <int>`: Seed for deterministic randomness across frames. Omit for non-deterministic runs.
- `--background <color>`: Background color; preserves the image alpha if omitted.
- `--tile-filter {nearest,bilinear,bicubic,lanczos}`: Resampling filter used when scaling cropped tiles. Default: `lanczos`.
- `--input-scale <float>`: Uniform scale factor applied to the input before tiling. Provide this **or** both `--input-width` and `--input-height`.
- `--input-width <int>`/`--input-height <int>`: Dimensions to rescale the input image before tiling.
- `--input-filter {nearest,bilinear,bicubic,lanczos}`: Resampling filter used for pre-scaling. Default: `lanczos`.
- `--verbose`: Print tile placement details per frame during generation.

### `upscale`
Upscale an image using `fit`, `fill`, or `stretch` modes.

```
python tiler_cli.py upscale input.jpg out.png [options]
```

Positional arguments:
- `input`: Path to the source image.
- `output`: Destination path for the upscaled image.

Options:
- `--width <int>`: Target width in pixels (requires `--height` unless `--scale` is provided).
- `--height <int>`: Target height in pixels (requires `--width` unless `--scale` is provided).
- `--scale <float>`: Uniform scale factor alternative to `--width`/`--height`.
- `--mode {fit,fill,stretch}`: Resize behavior. `fit` preserves aspect ratio with padding; `fill` preserves aspect ratio while cropping; `stretch` ignores aspect ratio. Default: `fit`.
- `--filter {nearest,bilinear,bicubic,lanczos}`: Resampling filter. Default: `lanczos`.
- `--background <color>`: Background color used when padding or filling. Default: `"#000000"`.

If `--scale` is not supplied, you must pass both `--width` and `--height`.

## GUI usage
`tiler_gui.py` provides a lightweight Tkinter interface for running the same workflows without typing command lines:

**Running in Codespaces:** If you're using GitHub Codespaces, see `CODESPACE_GUI.md` for instructions to run the GUI in a browser (noVNC/Xvfb setup and security notes).

1. Start the app with `python tiler_gui.py`.
2. Choose a mode (`single`, `layers`, `gif`, or `upscale`) from the dropdown.
3. Browse for an input image and pick an output path (include a file extension).
4. For `single`/`layers`/`gif`, you can optionally pre-scale the source image (scale or width + height with a chosen filter), adjust tile sizing (fractional tile size or explicit width/height), min/max tile scales, background color, tile filter, and seed.
5. Mode-specific controls appear automatically:
   - `layers`: tile count and an optional verbose toggle.
   - `gif`: number of frames, tiles per frame, FPS, and verbose toggle.
   - `upscale`: target width/height or uniform scale, resize mode (`fit`/`fill`/`stretch`), filter, and background color.
6. Click **Run** to generate the output; the app reports success or validation errors in dialogs.

## Examples
- Single tile remix using a 25% tile size:
  ```bash
  python tiler_cli.py single input.jpg out.png --tile-size 0.25
  ```
- Layered composite with eight tiles and a deterministic seed:
  ```bash
  python tiler_cli.py layers input.jpg out.png --count 8 --tile-size 0.2 --seed 42
  ```
- GIF animation with 16 frames at 8 fps:
  ```bash
  python tiler_cli.py gif input.jpg out.gif --frames 16 --tiles 6 --fps 8
  ```
- Upscale to 2× using Lanczos filter:
  ```bash
  python tiler_cli.py upscale input.jpg out.png --scale 2 --filter lanczos
  ```

## Notes
- Randomness can be controlled with `--seed`; omitting it yields a new random layout each run.
- Transparent backgrounds are preserved when `--background` is not provided.
- Output directories are created automatically.

