from __future__ import annotations

import base64
import json
from io import BytesIO
from pathlib import Path

import gradio as gr
from PIL import Image
from trimap_editor import TrimapEditor

_EXAMPLES_DIR = Path(__file__).parent / "examples"


def on_run(value: str | None) -> tuple[Image.Image, Image.Image]:
    """Process a drawn trimap: return original image and trimap side-by-side."""
    if not value:
        return gr.skip(), gr.skip()
    try:
        d = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return gr.skip(), gr.skip()
    if "trimapBase64" not in d:
        # No trimap drawn yet
        return gr.skip(), gr.skip()
    image_path = d.get("image", "")
    if not image_path:
        return gr.skip(), gr.skip()
    b64 = d["trimapBase64"]
    if "," in b64:
        b64 = b64.split(",", 1)[1]  # strip "data:image/png;base64," prefix
    image = Image.open(image_path).convert("RGB")
    trimap = Image.open(BytesIO(base64.b64decode(b64)))
    return image, trimap


with gr.Blocks(title="Trimap Editor") as demo:
    gr.Markdown(
        "## Trimap Editor\nDraw foreground / unknown regions for image matting. Press **?** for keyboard shortcuts."
    )

    editor = TrimapEditor(label="Draw Trimap")

    with gr.Row():
        orig_out = gr.Image(label="Original Image")
        trimap_out = gr.Image(label="Trimap")

    run_btn = gr.Button("Run", variant="primary")
    run_btn.click(fn=on_run, inputs=editor, outputs=[orig_out, trimap_out])

    # Build examples: pair each image with its trimap if one exists.
    # Images with a trimap use (image, trimap) tuple input; without use image-only.
    examples_list = sorted(_EXAMPLES_DIR.glob("*.jpg"))
    examples_data = []
    for img_path in examples_list:
        trimap_path = _EXAMPLES_DIR / f"{img_path.stem}_trimap.png"
        if trimap_path.exists():
            examples_data.append([[str(img_path), str(trimap_path)]])
        else:
            examples_data.append([[str(img_path)]])
    if examples_data:
        gr.Examples(
            examples=examples_data,
            inputs=editor,
        )

if __name__ == "__main__":
    demo.launch()
