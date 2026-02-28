"""Minimal Gradio app used exclusively by UI tests.

Mounts only what the test suite needs: a TrimapEditor and gr.Examples
with the same demo/examples/ images (tests rely on gallery item order:
0=green_tree, 1=red_circle with trimap, 2=yellow_star with trimap).
"""

from __future__ import annotations

from pathlib import Path

import gradio as gr

from trimap_editor import TrimapEditor

_EXAMPLES_DIR = Path(__file__).parent.parent / "demo" / "showcase" / "examples"

with gr.Blocks(title="Trimap Editor — Test") as demo:
    editor = TrimapEditor(label="Draw Trimap")

    # Build examples: pair each image with its trimap if one exists.
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
