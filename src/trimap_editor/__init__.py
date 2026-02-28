from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import gradio as gr
from gradio import processing_utils
from PIL import Image

_STATIC_DIR = Path(__file__).parent / "static"

__all__ = ["TrimapEditor"]


def _load_image(value: Any) -> Image.Image:
    if isinstance(value, Image.Image):
        return value.convert("RGB")
    if isinstance(value, str):
        return Image.open(value).convert("RGB")
    if isinstance(value, Path):
        return Image.open(value).convert("RGB")
    msg = f"Cannot load image from {type(value)}"
    raise TypeError(msg)


def _load_trimap(value: Any) -> Image.Image:
    """Load a trimap image as grayscale (mode 'L')."""
    if isinstance(value, Image.Image):
        return value.convert("L")
    if isinstance(value, (str, Path)):
        return Image.open(value).convert("L")
    msg = f"Cannot load trimap from {type(value)}"
    raise TypeError(msg)


def _save_image_to_cache(img: Image.Image, cache_dir: str, *, fmt: str = "webp") -> str:
    cached_path = processing_utils.save_pil_to_cache(img, cache_dir, format=fmt)
    return f"/gradio_api/file={cached_path}"


class TrimapEditor(gr.HTML):
    """Custom Gradio component for drawing trimap masks on images.

    A trimap is a 3-class mask:
      0   → background (definitely background)
      128 → unknown (transition region for matting)
      255 → foreground (definitely foreground)

    The foreground region is always kept as a subset of the unknown region.
    """

    def __init__(
        self,
        value: str | Image.Image | Path | None = None,
        *,
        label: str | None = None,
        **kwargs: Any,
    ) -> None:
        html_template = (_STATIC_DIR / "template.html").read_text(encoding="utf-8")
        css_template = (_STATIC_DIR / "style.css").read_text(encoding="utf-8")
        js_on_load = (_STATIC_DIR / "script.js").read_text(encoding="utf-8")

        super().__init__(
            value=value,
            label=label,
            show_label=label is not None,
            container=label is not None,
            html_template=html_template,
            css_template=css_template,
            js_on_load=js_on_load,
            apply_default_css=False,
            **kwargs,
        )

    def postprocess(self, value: Any) -> str | None:
        if value is None:
            return None

        # Tuple/list: (image, trimap) — load both
        if isinstance(value, (list, tuple)) and len(value) >= 2:  # noqa: PLR2004 — (image, trimap) pair
            img = _load_image(value[0])
            result: dict[str, Any] = {
                "image": _save_image_to_cache(img, self.GRADIO_CACHE),
                "width": img.width,
                "height": img.height,
            }
            if value[1] is not None:
                trimap_img = _load_trimap(value[1])
                result["trimap"] = _save_image_to_cache(trimap_img, self.GRADIO_CACHE, fmt="png")
            return json.dumps(result)

        # Single-element list/tuple: unwrap to get the image
        if isinstance(value, (list, tuple)):
            value = value[0]

        # Single image (existing behavior)
        img = _load_image(value)
        return json.dumps(
            {
                "image": _save_image_to_cache(img, self.GRADIO_CACHE),
                "width": img.width,
                "height": img.height,
            }
        )

    def process_example(self, value: Any) -> str | None:
        if value is None:
            return None
        image_source = value[0] if isinstance(value, (list, tuple)) else value
        try:
            img = _load_image(image_source)
        except Exception:  # noqa: BLE001
            return None
        url = _save_image_to_cache(img, self.GRADIO_CACHE)
        img_style = "max-height:5rem;object-fit:contain;border-radius:4px;"

        # Check for trimap in tuple/list input
        trimap_url = None
        if isinstance(value, (list, tuple)) and len(value) >= 2:  # noqa: PLR2004 — (image, trimap) pair
            try:
                trimap_img = _load_trimap(value[1])
                trimap_url = _save_image_to_cache(trimap_img, self.GRADIO_CACHE, fmt="png")
            except Exception:  # noqa: BLE001, S110 — trimap is optional; fall back to image-only thumbnail
                pass

        if trimap_url:
            esc_url = html.escape(url, quote=True)
            esc_trimap = html.escape(trimap_url, quote=True)
            return (
                f'<div style="display:flex;gap:4px;align-items:center;">'
                f'<img src="{esc_url}" alt="image" style="{img_style}">'
                f'<span style="color:#888;font-size:0.7rem;">+</span>'
                f'<img src="{esc_trimap}" alt="trimap" style="{img_style}">'
                f"</div>"
            )
        esc_url = html.escape(url, quote=True)
        return f'<img src="{esc_url}" alt="example" style="max-width:100%;{img_style}display:block;">'

    def api_info(self) -> dict[str, Any]:
        return {
            "type": "string",
            "description": (
                "JSON string. "
                "Input (Python→JS): {image: string (URL), width: int, height: int, "
                "trimap?: string (URL, optional pre-drawn trimap PNG)}. "
                "Pass a (image, trimap) tuple to postprocess() to include a trimap. "
                "Output (JS→Python): {image: string (URL), width: int, height: int, "
                "trimapBase64: string (data URI 'data:image/png;base64,...')}. "
                "trimapBase64 is absent when no trimap has been drawn yet."
            ),
        }
