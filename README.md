# Trimap Editor

A Gradio custom HTML component for drawing **trimap masks** on images, built for image-matting workflows.

Built on top of [`gr.HTML`](https://www.gradio.app/docs/gradio/html) using HTML/CSS/JavaScript for rendering, with no frontend build step required.

A trimap is a 3-class mask used in alpha matting:

| Value | Meaning |
|-------|---------|
| `0` | Background |
| `128` | Unknown (transition region) |
| `255` | Foreground |

The editor enforces the constraint that **foreground is always a subset of unknown**. Anything outside the unknown region is automatically background.

## Features

- **Two-layer drawing** with automatic subset enforcement (fg paint also paints unknown; erasing unknown also erases fg)
- **Brush, eraser & flood fill tools** with independent size sliders for brush and eraser
- **Zoom & pan** — scroll wheel to zoom at cursor, right/middle-drag or Space+drag to pan, double-click to fit
- **Maximize mode** — full-viewport editing for fine-grained work
- **Undo / redo** — `Ctrl+Z` / `Ctrl+Shift+Z` with a 30-step history stack
- **Adjustable overlay opacity & color** — 9-color palette and independent alpha sliders for each layer
- **Per-layer visibility toggles** — eye icons to show/hide each overlay independently
- **Image layer toggle** — hide the base image to inspect masks alone
- **Trimap view** — real-time grayscale preview showing the 3-value trimap (black/gray/white)
- **Cutout preview** — visualize the foreground mask on a checkerboard, with invert toggle
- **Keyboard shortcuts** for every action (press `?` for help)
- **Auto-commit** — trimap data is sent to Python automatically after each stroke, fill, undo/redo, or clear
- **`gr.Examples` support** — load images (and optionally pre-drawn trimaps) from an examples gallery
- **Clean 3-value export** — alpha thresholding eliminates brush antialiasing artifacts
- **No external JS dependencies** — pure Canvas API, ~1600 lines

## Installation

```bash
pip install trimap-editor
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add trimap-editor
```

### Requirements

- Python >= 3.12
- Gradio >= 6.8.0
- Pillow >= 12.1.1

## Quick Start

```python
import json
import base64
from io import BytesIO

import gradio as gr
from PIL import Image
from trimap_editor import TrimapEditor


def on_run(value: str | None):
    if not value:
        return gr.skip(), gr.skip()
    d = json.loads(value)
    if "trimapBase64" not in d:
        return gr.skip(), gr.skip()

    b64 = d["trimapBase64"]
    if "," in b64:
        b64 = b64.split(",", 1)[1]

    image = Image.open(d["image"]).convert("RGB")
    trimap = Image.open(BytesIO(base64.b64decode(b64)))
    return image, trimap


with gr.Blocks(title="Trimap Editor") as demo:
    editor = TrimapEditor(label="Draw Trimap")

    with gr.Row():
        orig_out = gr.Image(label="Original Image")
        trimap_out = gr.Image(label="Trimap")

    run_btn = gr.Button("Run", variant="primary")
    run_btn.click(fn=on_run, inputs=editor, outputs=[orig_out, trimap_out])

if __name__ == "__main__":
    demo.launch()
```

The component auto-commits the trimap as a base64-encoded PNG in the component value. The Python handler parses the JSON, checks for the `trimapBase64` key, and decodes it.

## Usage

### Loading images

Upload an image by clicking the canvas area or dragging a file onto it. You can also load images programmatically via `gr.Examples`:

```python
gr.Examples(
    examples=[["examples/photo.jpg"]],
    inputs=[editor],
)
```

To load both an image and a pre-drawn trimap:

```python
gr.Examples(
    examples=[[["examples/photo.jpg", "examples/photo_trimap.png"]]],
    inputs=[editor],
)
```

### Drawing

1. Select a **layer** (Foreground or Unknown) and a **tool** (Brush, Eraser, or Fill).
2. Left-click and drag on the canvas to paint. Single-click with Fill to flood-fill connected regions.
3. Adjust brush/eraser size with their respective sliders or `[` / `]` keys.
4. Adjust overlay opacity with the alpha sliders. Click the color swatch to pick from a 9-color palette.
5. Toggle layer visibility with the eye icons (`1` / `2` keys) or hide the base image with the Image button (`I` key).

### Viewing modes

- **Normal**: image with colored overlays (default)
- **Trimap** (`V`): grayscale preview — black (background), gray (unknown), white (foreground)
- **Cutout** (`C`): foreground region composited on a checkerboard background. Press `N` to invert.

### Data format

The component value is a JSON string. After drawing, it contains:

```json
{
  "image": "/tmp/.../image.webp",
  "width": 1920,
  "height": 1080,
  "trimapBase64": "data:image/png;base64,..."
}
```

The `trimapBase64` key is present only after the user has drawn on the canvas. Check for its presence before processing.

### Keyboard Shortcuts

Press `?` while the editor is focused to see all shortcuts.

| Key | Action |
|-----|--------|
| `F` / `U` | Switch to Foreground / Unknown layer |
| `1` / `2` | Toggle Foreground / Unknown visibility |
| `B` / `E` / `G` | Brush / Eraser / Fill tool |
| `P` | Pan tool (toggle) |
| `[` / `]` | Decrease / increase brush size |
| `I` | Toggle image layer |
| `V` | Trimap view |
| `C` | Cutout preview |
| `N` | Invert cutout |
| `+` / `-` | Zoom in / out |
| `0` | Reset zoom (fit to view) |
| `M` | Toggle maximize |
| `Space` (hold) | Temporary pan mode |
| `Ctrl+Z` | Undo |
| `Ctrl+Shift+Z` | Redo |
| `X` | Remove image |
| `Escape` | Exit maximize |
| `?` | Show help dialog |

## Development

```bash
git clone https://github.com/hysts/trimap-editor.git
cd trimap-editor
uv sync --group dev
```

### Run the demos

```bash
cd demo/showcase
uv sync
uv run python app.py
```

The ViTMatte demo requires extra dependencies (torch, transformers, spaces):

```bash
cd demo/vitmatte
uv sync
uv run python app.py
```

### Run tests

```bash
uv run playwright install chromium  # first time only
uv run pytest
```

### Lint & format

```bash
uv run ruff format .
uv run ruff check . --fix
```

## License

[MIT](LICENSE)
