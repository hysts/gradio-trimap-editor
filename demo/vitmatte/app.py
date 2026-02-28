"""ViTMatte demo using TrimapEditor for trimap input.

Extra dependencies (not in the trimap-editor package):
    spaces, torch, transformers
"""

from __future__ import annotations

import base64
import json
import os
from io import BytesIO
from pathlib import Path

import gradio as gr
import numpy as np
import PIL.Image
import spaces
import torch
from transformers import VitMatteForImageMatting, VitMatteImageProcessor
from trimap_editor import TrimapEditor

DESCRIPTION = """\
# [ViTMatte](https://github.com/hustvl/ViTMatte) with Trimap Editor

Image matting with Vision Transformers — accurately extract the foreground
from an image, even tricky areas like hair and fur!

1. **Upload** an image (or click an example below).
2. **Draw** foreground (green) and unknown (blue) regions. Press **?** for shortcuts.
3. Click **Run** to generate the alpha matte.
"""

_ASSETS_DIR = Path(__file__).parent / "assets"

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
MAX_IMAGE_SIZE = int(os.getenv("MAX_IMAGE_SIZE", "1500"))
MODEL_ID = os.getenv("MODEL_ID", "hustvl/vitmatte-small-distinctions-646")

processor = VitMatteImageProcessor.from_pretrained(MODEL_ID)
model = VitMatteForImageMatting.from_pretrained(MODEL_ID).to(device)


def _resize_on_upload(value: str | None) -> PIL.Image.Image:
    """Downscale the image on upload if it exceeds MAX_IMAGE_SIZE.

    Only fires for fresh uploads (no trimapBase64 yet).
    Returns gr.skip() when no resize is needed so the editor is untouched.
    """
    if not value:
        return gr.skip()
    d = json.loads(value)
    if "trimapBase64" in d:
        return gr.skip()
    w, h = d.get("width", 0), d.get("height", 0)
    if max(w, h) <= MAX_IMAGE_SIZE:
        return gr.skip()
    image_url = d.get("image", "")
    if not image_url:
        return gr.skip()
    # .change() receives raw postprocess() values which still have the
    # Gradio file-serving prefix (JS strips it only in commitValue()).
    image_path = image_url.removeprefix("/gradio_api/file=")
    image = PIL.Image.open(image_path).convert("RGB")
    scale = MAX_IMAGE_SIZE / max(w, h)
    new_w, new_h = int(w * scale), int(h * scale)
    gr.Info(f"Image resized from {w}x{h} to {new_w}x{new_h} (max {MAX_IMAGE_SIZE}px).")
    return image.resize((new_w, new_h))


def _parse_editor(value: str | None) -> tuple[PIL.Image.Image, PIL.Image.Image]:
    """Extract image and trimap from TrimapEditor JSON value."""
    if not value:
        raise gr.Error("Upload an image and draw a trimap first.")
    d = json.loads(value)

    # Image
    image_url = d.get("image", "")
    if not image_url:
        raise gr.Error("No image loaded.")
    image = PIL.Image.open(image_url).convert("RGB")

    # Trimap: prefer trimapBase64 (user-drawn), fall back to trimap URL (from example)
    if "trimapBase64" in d:
        b64 = d["trimapBase64"]
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        trimap = PIL.Image.open(BytesIO(base64.b64decode(b64))).convert("L")
    elif "trimap" in d:
        trimap = PIL.Image.open(d["trimap"]).convert("L")
    else:
        raise gr.Error("Draw a trimap first (mark foreground and unknown regions).")

    return image, trimap


def _adjust_background(bg: PIL.Image.Image, target_size: tuple[int, int]) -> PIL.Image.Image:
    """Crop-resize background to match target dimensions."""
    tw, th = target_size
    bw, bh = bg.size
    scale = max(tw / bw, th / bh)
    bg = bg.resize((int(bw * scale), int(bh * scale)))
    left = (bg.width - tw) // 2
    top = (bg.height - th) // 2
    return bg.crop((left, top, left + tw, top + th))


def _replace_background(
    image: PIL.Image.Image, alpha: np.ndarray, bg: PIL.Image.Image | None
) -> PIL.Image.Image | None:
    if bg is None:
        return None
    bg = _adjust_background(bg.convert("RGB"), image.size)
    fg = np.array(image).astype(float) / 255
    bg_arr = np.array(bg).astype(float) / 255
    result = fg * alpha[:, :, None] + bg_arr * (1 - alpha[:, :, None])
    return PIL.Image.fromarray((result * 255).astype(np.uint8))


@spaces.GPU
@torch.inference_mode()
def run(
    editor_value: str | None,
    apply_bg: bool,
    background_image: PIL.Image.Image | None,
) -> tuple:
    image, trimap = _parse_editor(editor_value)

    pixel_values = processor(images=image, trimaps=trimap, return_tensors="pt").to(device).pixel_values
    out = model(pixel_values=pixel_values)
    alpha = out.alphas[0, 0].to("cpu").numpy()

    w, h = image.size
    alpha = alpha[:h, :w]

    foreground = np.array(image).astype(float) / 255 * alpha[:, :, None] + (1 - alpha[:, :, None])
    foreground = PIL.Image.fromarray((foreground * 255).astype(np.uint8))

    res_bg = _replace_background(image, alpha, background_image) if apply_bg else None

    return (
        (image, alpha),
        (image, foreground),
        (image, res_bg) if res_bg is not None else None,
    )


with gr.Blocks() as demo:
    gr.Markdown(DESCRIPTION)

    with gr.Row():
        with gr.Column():
            editor = TrimapEditor(label="Image & Trimap")
            with gr.Group():
                apply_bg = gr.Checkbox(label="Replace background", value=False)
                bg_image = gr.Image(label="Background image", type="pil", visible=False)
            run_btn = gr.Button("Run", variant="primary")
        with gr.Column():
            out_alpha = gr.ImageSlider(label="Alpha")
            out_foreground = gr.ImageSlider(label="Foreground")
            out_bg = gr.ImageSlider(label="Background replacement", visible=False)

    inputs = [editor, apply_bg, bg_image]
    outputs = [out_alpha, out_foreground, out_bg]

    gr.Examples(
        examples=[
            [
                [str(_ASSETS_DIR / "retriever_rgb.png"), str(_ASSETS_DIR / "retriever_trimap.png")],
                False,
                None,
            ],
            [
                [str(_ASSETS_DIR / "bulb_rgb.png"), str(_ASSETS_DIR / "bulb_trimap.png")],
                True,
                str(_ASSETS_DIR / "new_bg.jpg"),
            ],
        ],
        inputs=inputs,
        outputs=outputs,
        fn=run,
        cache_examples=False,
    )

    editor.input(
        fn=_resize_on_upload,
        inputs=editor,
        outputs=editor,
        api_name=False,
    )
    apply_bg.change(
        fn=lambda checked: (gr.Image(visible=checked), gr.ImageSlider(visible=checked)),
        inputs=apply_bg,
        outputs=[bg_image, out_bg],
        api_name=False,
    )

    run_btn.click(fn=run, inputs=inputs, outputs=outputs)

if __name__ == "__main__":
    demo.launch()
