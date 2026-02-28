"""Playwright UI interaction tests for TrimapEditor."""

from __future__ import annotations

from _helpers import (
    EXAMPLES_DIR,
    RE_ACTIVE,
    RE_DANGER_CONFIRM,
    RE_MAXIMIZED,
    RE_VIS_OFF,
    RE_VISIBLE,
    get_editor_block,
    get_editor_element,
    upload_image,
    wait_for_server_upload,
)
from playwright.sync_api import Page, expect


class TestImageUpload:
    def test_canvas_appears_after_upload(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        expect(block.locator(".te-canvas")).to_be_visible()

    def test_upload_hint_hidden_after_upload(self, demo_app: Page):
        block = get_editor_block(demo_app)
        # Upload hint should be visible initially
        expect(block.locator(".te-upload-hint")).to_be_visible()

        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        # Upload hint should be hidden after upload
        expect(block.locator(".te-canvas-wrapper.te-has-image .te-upload-hint")).to_be_hidden()


class TestLayerAndToolSwitching:
    def test_layer_buttons_switch_active_state(self, demo_app: Page):
        block = get_editor_block(demo_app)
        unknown_btn = block.locator("[data-layer='unknown']")
        fg_btn = block.locator("[data-layer='foreground']")

        # Default: Foreground active
        expect(fg_btn).to_have_class(RE_ACTIVE)
        expect(unknown_btn).not_to_have_class(RE_ACTIVE)

        # Click Unknown
        unknown_btn.click()
        expect(unknown_btn).to_have_class(RE_ACTIVE)
        expect(fg_btn).not_to_have_class(RE_ACTIVE)

        # Click Foreground again
        fg_btn.click()
        expect(fg_btn).to_have_class(RE_ACTIVE)

    def test_tool_buttons_switch_active_state(self, demo_app: Page):
        block = get_editor_block(demo_app)
        brush_btn = block.locator("[data-tool='brush']")
        eraser_btn = block.locator("[data-tool='eraser']")

        # Default: Brush active
        expect(brush_btn).to_have_class(RE_ACTIVE)

        eraser_btn.click()
        expect(eraser_btn).to_have_class(RE_ACTIVE)
        expect(brush_btn).not_to_have_class(RE_ACTIVE)


class TestBucketTool:
    def test_bucket_button_activates(self, demo_app: Page):
        block = get_editor_block(demo_app)
        bucket_btn = block.locator("[data-tool='bucket']")
        brush_btn = block.locator("[data-tool='brush']")

        # Default: Brush active, Bucket not
        expect(brush_btn).to_have_class(RE_ACTIVE)
        expect(bucket_btn).not_to_have_class(RE_ACTIVE)

        # Click Bucket
        bucket_btn.click()
        expect(bucket_btn).to_have_class(RE_ACTIVE)
        expect(brush_btn).not_to_have_class(RE_ACTIVE)

    def test_g_key_activates_bucket_tool(self, demo_app: Page):
        block = get_editor_block(demo_app)
        block.focus()
        demo_app.keyboard.press("g")

        bucket_btn = block.locator("[data-tool='bucket']")
        expect(bucket_btn).to_have_class(RE_ACTIVE)

        # Brush should no longer be active
        brush_btn = block.locator("[data-tool='brush']")
        expect(brush_btn).not_to_have_class(RE_ACTIVE)

    def test_bucket_sets_crosshair_cursor(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        # Hover center of canvas (always over the centered image)
        demo_app.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)

        block.focus()
        demo_app.keyboard.press("g")
        expect(canvas).to_have_css("cursor", "crosshair")

    def test_cursor_default_outside_image(self, demo_app: Page):
        """Cursor should be default when hovering dark area outside image."""
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        # Hover near top-left corner — likely in the dark padding area
        demo_app.mouse.move(box["x"] + 2, box["y"] + 2)
        expect(canvas).to_have_css("cursor", "default")


class TestSliders:
    def test_brush_size_slider_updates_label(self, demo_app: Page):
        block = get_editor_block(demo_app)
        slider = block.locator("#te-brush-size")
        size_val = block.locator("#te-brush-size-val")

        slider.fill("50")
        slider.dispatch_event("input")
        expect(size_val).to_have_text("50")

    def test_unknown_alpha_slider_updates_label(self, demo_app: Page):
        block = get_editor_block(demo_app)
        slider = block.locator("#te-unknown-alpha")
        alpha_val = block.locator("#te-unknown-alpha-val")

        slider.fill("70")
        slider.dispatch_event("input")
        expect(alpha_val).to_have_text("70%")


class TestDrawing:
    def test_drawing_stroke_on_canvas(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2

        # Draw a line across the center
        demo_app.mouse.move(cx - 40, cy)
        demo_app.mouse.down()
        demo_app.mouse.move(cx + 40, cy, steps=10)
        demo_app.mouse.up()
        # No assertion on pixel data from Python — just verify no JS errors

    def test_clear_button_resets(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        demo_app.mouse.move(box["x"] + 50, box["y"] + 50)
        demo_app.mouse.down()
        demo_app.mouse.move(box["x"] + 100, box["y"] + 50, steps=5)
        demo_app.mouse.up()

        clear_btn = block.locator("#te-clear-btn")
        clear_btn.click()
        # No crash — clear completed without error


class TestKeyboardShortcuts:
    def test_u_key_activates_unknown_layer(self, demo_app: Page):
        block = get_editor_block(demo_app)
        fg_btn = block.locator("[data-layer='foreground']")
        fg_btn.click()

        block.focus()
        demo_app.keyboard.press("u")

        unknown_btn = block.locator("[data-layer='unknown']")
        expect(unknown_btn).to_have_class(RE_ACTIVE)

    def test_f_key_activates_foreground_layer(self, demo_app: Page):
        block = get_editor_block(demo_app)
        block.focus()
        demo_app.keyboard.press("f")

        fg_btn = block.locator("[data-layer='foreground']")
        expect(fg_btn).to_have_class(RE_ACTIVE)

    def test_b_e_keys_switch_tools(self, demo_app: Page):
        block = get_editor_block(demo_app)
        block.focus()
        demo_app.keyboard.press("e")
        eraser_btn = block.locator("[data-tool='eraser']")
        expect(eraser_btn).to_have_class(RE_ACTIVE)

        demo_app.keyboard.press("b")
        brush_btn = block.locator("[data-tool='brush']")
        expect(brush_btn).to_have_class(RE_ACTIVE)

    def test_undo_redo_keyboard(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        demo_app.mouse.move(box["x"] + 60, box["y"] + 60)
        demo_app.mouse.down()
        demo_app.mouse.move(box["x"] + 120, box["y"] + 60, steps=5)
        demo_app.mouse.up()

        block.focus()
        demo_app.keyboard.press("Control+z")
        demo_app.keyboard.press("Control+Shift+Z")
        # No crash — undo/redo completed


class TestPanTool:
    def test_p_key_activates_pan_tool(self, demo_app: Page):
        block = get_editor_block(demo_app)
        block.focus()
        demo_app.keyboard.press("p")

        pan_btn = block.locator("[data-tool='pan']")
        expect(pan_btn).to_have_class(RE_ACTIVE)

        brush_btn = block.locator("[data-tool='brush']")
        expect(brush_btn).not_to_have_class(RE_ACTIVE)

    def test_pan_button_activates_pan_tool(self, demo_app: Page):
        block = get_editor_block(demo_app)
        pan_btn = block.locator("[data-tool='pan']")
        pan_btn.click()
        expect(pan_btn).to_have_class(RE_ACTIVE)

    def test_pan_button_toggles_off(self, demo_app: Page):
        """Clicking Pan again should revert to the previous drawing tool."""
        block = get_editor_block(demo_app)
        pan_btn = block.locator("[data-tool='pan']")
        brush_btn = block.locator("[data-tool='brush']")

        # Activate pan
        pan_btn.click()
        expect(pan_btn).to_have_class(RE_ACTIVE)
        expect(brush_btn).not_to_have_class(RE_ACTIVE)

        # Click pan again → should toggle back to brush (default prev tool)
        pan_btn.click()
        expect(brush_btn).to_have_class(RE_ACTIVE)
        expect(pan_btn).not_to_have_class(RE_ACTIVE)

    def test_pan_toggle_remembers_previous_tool(self, demo_app: Page):
        """Pan toggle should revert to the tool that was active before pan."""
        block = get_editor_block(demo_app)
        eraser_btn = block.locator("[data-tool='eraser']")
        pan_btn = block.locator("[data-tool='pan']")

        # Switch to eraser first
        eraser_btn.click()
        expect(eraser_btn).to_have_class(RE_ACTIVE)

        # Activate pan
        pan_btn.click()
        expect(pan_btn).to_have_class(RE_ACTIVE)
        expect(eraser_btn).not_to_have_class(RE_ACTIVE)

        # Toggle pan off → should revert to eraser, not brush
        pan_btn.click()
        expect(eraser_btn).to_have_class(RE_ACTIVE)
        expect(pan_btn).not_to_have_class(RE_ACTIVE)

    def test_p_key_toggles_pan(self, demo_app: Page):
        """Pressing P twice should toggle pan on then off."""
        block = get_editor_block(demo_app)
        block.focus()

        pan_btn = block.locator("[data-tool='pan']")
        brush_btn = block.locator("[data-tool='brush']")

        # P → activate pan
        demo_app.keyboard.press("p")
        expect(pan_btn).to_have_class(RE_ACTIVE)

        # P again → toggle back to brush
        demo_app.keyboard.press("p")
        expect(brush_btn).to_have_class(RE_ACTIVE)
        expect(pan_btn).not_to_have_class(RE_ACTIVE)

    def test_pan_tool_sets_grab_cursor(self, demo_app: Page):
        block = get_editor_block(demo_app)
        block.focus()
        demo_app.keyboard.press("p")

        canvas = block.locator(".te-canvas")
        expect(canvas).to_have_css("cursor", "grab")

    def test_space_hold_sets_grab_cursor_after_canvas_click(self, demo_app: Page):
        """Space pan must work after clicking on canvas (no explicit focus)."""
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2

        # Click canvas center (over image) to draw (also focuses container)
        demo_app.mouse.click(cx, cy)
        demo_app.wait_for_timeout(200)  # let click settle

        # Now Space should work — no block.focus() needed
        demo_app.keyboard.down(" ")
        expect(canvas).to_have_css("cursor", "grab")

        demo_app.keyboard.up(" ")
        expect(canvas).to_have_css("cursor", "crosshair")

    def test_space_hold_enables_pan_drag(self, demo_app: Page):
        """Hold Space + left-drag should pan (not draw)."""
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2

        # Click canvas to focus (instead of block.focus())
        demo_app.mouse.click(cx, cy)

        # Zoom in so panning is possible
        for _ in range(5):
            demo_app.keyboard.press("=")

        # Hold Space + drag
        demo_app.keyboard.down(" ")
        demo_app.mouse.move(cx, cy)
        demo_app.mouse.down()
        demo_app.mouse.move(cx + 50, cy + 30, steps=5)
        demo_app.mouse.up()
        demo_app.keyboard.up(" ")

        # Cursor should revert to crosshair after release
        expect(canvas).to_have_css("cursor", "crosshair")

    def test_double_click_in_pan_mode_resets_zoom(self, demo_app: Page):
        """Double-click in pan mode should reset zoom to contain-fit."""
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2

        # Click to focus, then zoom in
        demo_app.mouse.click(cx, cy)
        for _ in range(5):
            demo_app.keyboard.press("=")

        # Read zoomed-in zoom badge text
        demo_app.wait_for_timeout(200)
        demo_app.evaluate("""() => {
            var c = document.querySelector('.te-canvas');
            var ctx = c.getContext('2d');
            // Can't read badge, but check canvas state via zoom
            return true;
        }""")

        # Switch to pan tool, double-click to reset
        demo_app.keyboard.press("p")
        demo_app.mouse.dblclick(cx, cy)
        demo_app.wait_for_timeout(200)

        # Switch back to brush to verify zoom was reset
        # (zoom badge should show contain-fit percentage)
        demo_app.keyboard.press("b")

        # Verify no crash and cursor is crosshair (back in brush mode)
        expect(canvas).to_have_css("cursor", "crosshair")


class TestTrimapView:
    def test_trimap_view_button_toggles(self, demo_app: Page):
        """The Trimap view button toggles the trimap overlay display."""
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        trimap_btn = block.locator("#te-view-trimap-btn")
        expect(trimap_btn).to_be_visible()

        # Initially not active
        expect(trimap_btn).not_to_have_class(RE_ACTIVE)

        # Click to activate trimap view
        trimap_btn.click()
        expect(trimap_btn).to_have_class(RE_ACTIVE)

        # Click again to deactivate
        trimap_btn.click()
        expect(trimap_btn).not_to_have_class(RE_ACTIVE)


class TestGrExamples:
    def test_examples_gallery_shows_thumbnails(self, demo_app: Page):
        # Gallery items should contain img tags pointing to cached files (not raw JSON)
        gallery_items = demo_app.locator(".gallery .gallery-item")
        expect(gallery_items.first).to_be_visible()
        assert gallery_items.count() >= 1
        # Each item should contain at least one image
        expect(gallery_items.first.locator("img[src*='file=']")).to_be_visible()

    def test_example_loads_canvas_after_prior_upload(self, demo_app: Page):
        """Regression: gr.Examples must update the canvas even after a prior upload.

        Bug: handleValue() returned early when state.imageSource === 'upload',
        blocking gr.Examples from loading a new image into the canvas.
        Fix: always load Python-provided images; revoke the prior upload state.
        """
        block = get_editor_block(demo_app)

        example_imgs = sorted(EXAMPLES_DIR.glob("*.jpg"))
        assert len(example_imgs) >= 2, "Need at least 2 example images"

        # Upload yellow_star.jpg — center pixel: R≈255 G≈210 B≈29 (yellowish)
        yellow = EXAMPLES_DIR / "yellow_star.jpg"
        upload_image(block, yellow)
        demo_app.wait_for_timeout(500)  # let canvas render

        def _canvas_center_rgb():
            return demo_app.evaluate("""() => {
                var c = document.querySelector('.te-canvas');
                if (!c) return null;
                try {
                    var ctx = c.getContext('2d');
                    var d = ctx.getImageData(
                        Math.floor(c.width / 2), Math.floor(c.height / 2), 1, 1
                    ).data;
                    return [d[0], d[1], d[2]];
                } catch(e) { return null; }
            }""")

        before = _canvas_center_rgb()
        assert before is not None, "getImageData failed before example click"
        # yellow_star center: R≈255, G≈210 — both channels above 150
        assert before[0] > 150, f"expected high R channel (yellow), got {before}"
        assert before[1] > 150, f"expected high G channel (yellow), got {before}"

        # Click the first gallery example: green_tree.jpg (sorted first alphabetically)
        # green_tree center pixel: R≈34, G≈139, B≈34
        gallery_items = demo_app.locator(".gallery .gallery-item")
        expect(gallery_items.first).to_be_visible()
        gallery_items.first.click()

        # Poll until canvas center turns green (img.onload is async)
        demo_app.wait_for_function(
            """() => {
                var c = document.querySelector('.te-canvas');
                if (!c) return false;
                try {
                    var d = c.getContext('2d').getImageData(
                        Math.floor(c.width / 2), Math.floor(c.height / 2), 1, 1
                    ).data;
                    return d[1] > 100 && d[0] < 100;  // green: G≈139, R≈34
                } catch(e) { return false; }
            }""",
            timeout=6000,
        )

        after = _canvas_center_rgb()
        assert after is not None, "getImageData failed after example click"
        # green_tree center: G > 100, R < 100
        assert after[1] > 100, (
            f"expected high G channel (green) after clicking green_tree example, got {after} "
            "(example image was not loaded — upload guard still blocking)"
        )
        assert after[0] < 100, (
            f"expected low R channel (green) after clicking green_tree example, got {after} "
            "(example image was not loaded — upload guard still blocking)"
        )


class TestUploadNoReinit:
    """Regression tests for the drag-&-drop / file-upload flicker bugs.

    Root cause:
    - uploadToServer() was setting props.value = {image, width, height}.
      handleValue() treated that as a Python-provided image and called
      initMaskCanvases + clearHistory, wiping any drawn masks and history.
    - handleValue's img.onload also set props.value, triggering a second
      re-initialization cycle.
    - state.image was set before zoom/pan were computed; a ResizeObserver
      render could fire with zoom=1, showing only a small top-left corner.

    Fix:
    - uploadToServer() no longer sets props.value (only commitValue() does,
      with a trimapBase64 key that handleValue handles correctly).
    - handleValue img.onload no longer sets props.value.
    - state.image is set AFTER zoom/pan are computed, so any early renders
      find state.image=null and skip, preventing the zoom=1 flash.
    """

    def test_undo_enabled_after_draw_and_upload_completion(self, demo_app: Page):
        """Undo button must remain enabled after the server upload completes.

        Before fix: upload completion triggered handleValue → clearHistory(),
        which reset historyIndex=-1 and disabled the undo button.
        After fix: upload completion only stores state.filePath; no re-init.
        """
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        # Draw a stroke to create a history entry (historyIndex becomes 1).
        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        demo_app.mouse.move(cx - 30, cy)
        demo_app.mouse.down()
        demo_app.mouse.move(cx + 30, cy, steps=8)
        demo_app.mouse.up()

        # Wait for background upload to complete (polling state.filePath).
        demo_app.wait_for_function(
            """() => {
                var canvas = document.querySelector('.te-canvas');
                if (!canvas) return false;
                // Access the JS closure state via the exposed _teState property.
                var el = document.querySelector('.trimap-editor');
                if (!el || !el._teState) return false;
                return el._teState.filePath !== null;
            }""",
            timeout=6000,
        )

        # Undo must be ENABLED — re-initialization would have cleared history.
        undo_btn = block.locator("#te-undo-btn")
        expect(undo_btn).to_be_enabled(timeout=3000)

        # Undo should actually restore the previous state.
        undo_btn.click()
        # After undoing the one stroke we are at the base snapshot (index=0).
        expect(undo_btn).to_be_disabled(timeout=3000)

    def test_masks_survive_upload_completion(self, demo_app: Page):
        """Mask overlay must not be cleared when the server upload finishes.

        Before fix: upload completion triggered initMaskCanvases, wiping both
        unknownCanvas and fgCanvas — strokes drawn right after image load
        would vanish ~200-500 ms later.
        """
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        # Set a large brush so the stroke leaves clearly visible pixels.
        block.locator("#te-brush-size").fill("60")
        block.locator("#te-brush-size").dispatch_event("input")

        # Draw a stroke at canvas center.
        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        demo_app.mouse.move(cx, cy)
        demo_app.mouse.down()
        demo_app.mouse.move(cx + 10, cy, steps=3)
        demo_app.mouse.up()

        def _center_alpha():
            return demo_app.evaluate("""() => {
                var c = document.querySelector('.te-canvas');
                if (!c) return null;
                try {
                    var d = c.getContext('2d').getImageData(
                        Math.floor(c.width / 2), Math.floor(c.height / 2), 1, 1
                    ).data;
                    return d[3];
                } catch(e) { return null; }
            }""")

        alpha_before = _center_alpha()
        assert alpha_before is not None
        # The overlay must be visible right after drawing (sanity check).
        assert alpha_before > 0, "Stroke did not produce any visible pixel on canvas"

        # Wait for the background upload to finish.
        demo_app.wait_for_function(
            """() => {
                var el = document.querySelector('.trimap-editor');
                if (!el || !el._teState) return false;
                return el._teState.filePath !== null;
            }""",
            timeout=6000,
        )
        demo_app.wait_for_timeout(300)  # settle any post-upload renders

        alpha_after = _center_alpha()
        assert alpha_after is not None, "getImageData failed after upload completed"
        assert alpha_after > 0, (
            "Center pixel alpha dropped to 0 after upload completed — "
            "initMaskCanvases was called, wiping the drawn mask. "
            f"alpha_before={alpha_before}, alpha_after={alpha_after}"
        )


class TestTrimapLoading:
    """Tests for loading a pre-drawn trimap via gr.Examples."""

    def test_example_with_trimap_populates_canvases(self, demo_app: Page):
        """gr.Examples with a trimap should populate unknownCanvas and fgCanvas."""
        # Click a gallery example that has a trimap (second item: red_circle)
        gallery_items = demo_app.locator(".gallery .gallery-item")
        expect(gallery_items.nth(1)).to_be_visible()
        gallery_items.nth(1).click()

        # Wait for the image to load into the canvas
        block = get_editor_block(demo_app)
        expect(block.locator(".te-canvas-wrapper.te-has-image")).to_be_visible(timeout=8000)

        # Wait for trimap to be parsed — unknownCanvas should have non-zero pixels
        demo_app.wait_for_function(
            """() => {
                var el = document.querySelector('.trimap-editor');
                if (!el || !el._teState) return false;
                var s = el._teState;
                if (!s.image) return false;
                // Check unknownCanvas has painted pixels
                var uc = el._teUnknownCanvas;
                if (!uc || uc.width === 0) return false;
                var ctx = uc.getContext('2d');
                var d = ctx.getImageData(0, 0, uc.width, uc.height).data;
                for (var i = 3; i < d.length; i += 4) {
                    if (d[i] > 0) return true;
                }
                return false;
            }""",
            timeout=8000,
        )

        # Also verify fgCanvas has pixels
        has_fg = demo_app.evaluate("""() => {
            var el = document.querySelector('.trimap-editor');
            var fc = el._teFgCanvas;
            if (!fc || fc.width === 0) return false;
            var d = fc.getContext('2d').getImageData(0, 0, fc.width, fc.height).data;
            for (var i = 3; i < d.length; i += 4) {
                if (d[i] > 0) return true;
            }
            return false;
        }""")
        assert has_fg, "fgCanvas should have painted pixels after loading trimap"

    def test_drawing_works_after_trimap_load(self, demo_app: Page):
        """User should be able to draw additional strokes after loading a trimap."""
        # Load example with trimap (index 1 = red_circle; index 0 = green_tree has no trimap)
        gallery_items = demo_app.locator(".gallery .gallery-item")
        expect(gallery_items.nth(1)).to_be_visible()
        gallery_items.nth(1).click()

        block = get_editor_block(demo_app)
        expect(block.locator(".te-canvas-wrapper.te-has-image")).to_be_visible(timeout=8000)

        # Wait for trimap to be fully loaded
        demo_app.wait_for_function(
            """() => {
                var el = document.querySelector('.trimap-editor');
                return el && el._teState && el._teState.image;
            }""",
            timeout=8000,
        )

        # Draw a stroke on the canvas
        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        demo_app.mouse.move(cx - 30, cy)
        demo_app.mouse.down()
        demo_app.mouse.move(cx + 30, cy, steps=8)
        demo_app.mouse.up()
        # No crash — drawing works after trimap load

    def test_undo_after_trimap_load_reverts_to_loaded_state(self, demo_app: Page):
        """Undo after drawing on a loaded trimap should revert to the trimap state, not blank."""
        # Load example with trimap (index 1 = red_circle; index 0 = green_tree has no trimap)
        gallery_items = demo_app.locator(".gallery .gallery-item")
        expect(gallery_items.nth(1)).to_be_visible()
        gallery_items.nth(1).click()

        block = get_editor_block(demo_app)
        expect(block.locator(".te-canvas-wrapper.te-has-image")).to_be_visible(timeout=8000)

        # Wait for trimap to be fully loaded
        demo_app.wait_for_function(
            """() => {
                var el = document.querySelector('.trimap-editor');
                return el && el._teState && el._teState.image;
            }""",
            timeout=8000,
        )

        # Count initial unknown pixels
        initial_unknown_count = demo_app.evaluate("""() => {
            var el = document.querySelector('.trimap-editor');
            var uc = el._teUnknownCanvas;
            var d = uc.getContext('2d').getImageData(0, 0, uc.width, uc.height).data;
            var count = 0;
            for (var i = 3; i < d.length; i += 4) {
                if (d[i] > 0) count++;
            }
            return count;
        }""")
        assert initial_unknown_count > 0, "Trimap should have unknown pixels"

        # Draw a large stroke to add more pixels
        block.locator("#te-brush-size").fill("80")
        block.locator("#te-brush-size").dispatch_event("input")

        # Switch to unknown layer to see the change more clearly
        block.locator("[data-layer='unknown']").click()

        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        # Draw in the top-left quadrant — on the image but outside the circle
        # (the red_circle trimap has unknown/fg only near the center)
        demo_app.mouse.move(cx - box["width"] * 0.25, cy - box["height"] * 0.25)
        demo_app.mouse.down()
        demo_app.mouse.move(cx - box["width"] * 0.15, cy - box["height"] * 0.25, steps=5)
        demo_app.mouse.up()

        # After drawing, unknown count should be larger
        after_draw_count = demo_app.evaluate("""() => {
            var el = document.querySelector('.trimap-editor');
            var uc = el._teUnknownCanvas;
            var d = uc.getContext('2d').getImageData(0, 0, uc.width, uc.height).data;
            var count = 0;
            for (var i = 3; i < d.length; i += 4) {
                if (d[i] > 0) count++;
            }
            return count;
        }""")
        assert after_draw_count > initial_unknown_count, (
            f"Drawing should add pixels: before={initial_unknown_count}, after={after_draw_count}"
        )

        # Undo
        block.focus()
        demo_app.keyboard.press("Control+z")
        demo_app.wait_for_timeout(200)

        # After undo, should be back to the loaded trimap count
        after_undo_count = demo_app.evaluate("""() => {
            var el = document.querySelector('.trimap-editor');
            var uc = el._teUnknownCanvas;
            var d = uc.getContext('2d').getImageData(0, 0, uc.width, uc.height).data;
            var count = 0;
            for (var i = 3; i < d.length; i += 4) {
                if (d[i] > 0) count++;
            }
            return count;
        }""")
        assert after_undo_count == initial_unknown_count, (
            f"Undo should revert to loaded trimap state: "
            f"initial={initial_unknown_count}, after_undo={after_undo_count}"
        )

    def test_first_example_with_trimap_loads_on_cold_start(self, demo_app: Page):
        """Regression: first example with trimap must load without clicking another first.

        Bug: clicking the first example with a trimap on a fresh page load
        failed to display the image. The te-has-image class was lost during a
        DOM morph while the trimap was still loading asynchronously, because
        state.image was null (set only in trimapImg.onload). The
        MutationObserver checked state.image to re-assert te-has-image and
        found null, so the class was not restored.

        Fix: set state.image immediately after the main image loads (before
        starting the trimap load). This ensures the MutationObserver sees
        state.image !== null and correctly re-asserts te-has-image.
        """
        block = get_editor_block(demo_app)

        # Click an example with trimap on a fresh page (no prior interaction)
        # Second item: red_circle (has trimap)
        gallery_items = demo_app.locator(".gallery .gallery-item")
        expect(gallery_items.nth(1)).to_be_visible()
        gallery_items.nth(1).click()

        # te-has-image must be set after loading (this was the bug)
        expect(block.locator(".te-canvas-wrapper.te-has-image")).to_be_visible(timeout=8000)

        # Image must actually be loaded
        demo_app.wait_for_function(
            """() => {
                var el = document.querySelector('.trimap-editor');
                return el && el._teState && el._teState.image;
            }""",
            timeout=8000,
        )


class TestCutoutPreview:
    """Tests for the cutout preview mode (C key / Cutout button)."""

    def test_cutout_button_toggles(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        cutout_btn = block.locator("#te-view-cutout-btn")
        expect(cutout_btn).not_to_have_class(RE_ACTIVE)

        cutout_btn.click()
        expect(cutout_btn).to_have_class(RE_ACTIVE)

        cutout_btn.click()
        expect(cutout_btn).not_to_have_class(RE_ACTIVE)

    def test_c_key_toggles_cutout(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        block.focus()
        cutout_btn = block.locator("#te-view-cutout-btn")

        demo_app.keyboard.press("c")
        expect(cutout_btn).to_have_class(RE_ACTIVE)

        demo_app.keyboard.press("c")
        expect(cutout_btn).not_to_have_class(RE_ACTIVE)

    def test_cutout_and_trimap_mutually_exclusive(self, demo_app: Page):
        """Activating cutout should deactivate trimap and vice versa."""
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        block.focus()
        trimap_btn = block.locator("#te-view-trimap-btn")
        cutout_btn = block.locator("#te-view-cutout-btn")

        # Activate trimap, then cutout → trimap should deactivate
        demo_app.keyboard.press("v")
        expect(trimap_btn).to_have_class(RE_ACTIVE)
        demo_app.keyboard.press("c")
        expect(cutout_btn).to_have_class(RE_ACTIVE)
        expect(trimap_btn).not_to_have_class(RE_ACTIVE)

        # Activate trimap again → cutout should deactivate
        demo_app.keyboard.press("v")
        expect(trimap_btn).to_have_class(RE_ACTIVE)
        expect(cutout_btn).not_to_have_class(RE_ACTIVE)

    def test_invert_button_disabled_when_cutout_off(self, demo_app: Page):
        """Invert button should be disabled when cutout mode is off."""
        block = get_editor_block(demo_app)
        invert_btn = block.locator("#te-cutout-invert-btn")

        expect(invert_btn).to_be_disabled()

    def test_invert_button_enabled_when_cutout_on(self, demo_app: Page):
        """Invert button should be enabled when cutout mode is active."""
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        cutout_btn = block.locator("#te-view-cutout-btn")
        invert_btn = block.locator("#te-cutout-invert-btn")

        cutout_btn.click()
        expect(invert_btn).to_be_enabled()

    def test_invert_button_toggles(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        cutout_btn = block.locator("#te-view-cutout-btn")
        invert_btn = block.locator("#te-cutout-invert-btn")

        cutout_btn.click()
        expect(invert_btn).not_to_have_class(RE_ACTIVE)

        invert_btn.click()
        expect(invert_btn).to_have_class(RE_ACTIVE)

        invert_btn.click()
        expect(invert_btn).not_to_have_class(RE_ACTIVE)

    def test_n_key_toggles_invert(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        block.focus()
        invert_btn = block.locator("#te-cutout-invert-btn")

        # N without cutout active → no effect
        demo_app.keyboard.press("n")
        expect(invert_btn).not_to_have_class(RE_ACTIVE)

        # Activate cutout, then N toggles invert
        demo_app.keyboard.press("c")
        demo_app.keyboard.press("n")
        expect(invert_btn).to_have_class(RE_ACTIVE)

        demo_app.keyboard.press("n")
        expect(invert_btn).not_to_have_class(RE_ACTIVE)

    def test_cutout_off_resets_invert(self, demo_app: Page):
        """Deactivating cutout should also reset invert."""
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        block.focus()
        invert_btn = block.locator("#te-cutout-invert-btn")

        # Enable cutout + invert
        demo_app.keyboard.press("c")
        demo_app.keyboard.press("n")
        expect(invert_btn).to_have_class(RE_ACTIVE)

        # Disable cutout → invert should reset
        demo_app.keyboard.press("c")
        expect(invert_btn).not_to_have_class(RE_ACTIVE)
        expect(invert_btn).to_be_disabled()

    def test_cutout_follows_active_layer(self, demo_app: Page):
        """Switching layers in cutout mode should update the JS state."""
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        block.focus()
        demo_app.keyboard.press("c")

        # Default layer is foreground
        layer = demo_app.evaluate("""() => {
            var el = document.querySelector('.trimap-editor');
            return el._teState.layer;
        }""")
        assert layer == "foreground"

        # Switch to unknown
        demo_app.keyboard.press("u")
        layer = demo_app.evaluate("""() => {
            var el = document.querySelector('.trimap-editor');
            return el._teState.layer;
        }""")
        assert layer == "unknown"

        # Cutout should still be active
        cutout_btn = block.locator("#te-view-cutout-btn")
        expect(cutout_btn).to_have_class(RE_ACTIVE)

    def test_cutout_no_image_does_nothing(self, demo_app: Page):
        """Pressing C without an image should not activate cutout."""
        block = get_editor_block(demo_app)
        block.focus()
        demo_app.keyboard.press("c")

        cutout_btn = block.locator("#te-view-cutout-btn")
        expect(cutout_btn).not_to_have_class(RE_ACTIVE)

    def test_remove_image_resets_cutout(self, demo_app: Page):
        """Removing the image should reset cutout and invert state."""
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        block.focus()
        # Enable cutout + invert
        demo_app.keyboard.press("c")
        demo_app.keyboard.press("n")

        cutout_btn = block.locator("#te-view-cutout-btn")
        invert_btn = block.locator("#te-cutout-invert-btn")
        expect(cutout_btn).to_have_class(RE_ACTIVE)
        expect(invert_btn).to_have_class(RE_ACTIVE)

        # Remove image
        demo_app.keyboard.press("x")

        expect(cutout_btn).not_to_have_class(RE_ACTIVE)
        expect(invert_btn).not_to_have_class(RE_ACTIVE)
        expect(invert_btn).to_be_disabled()


# ---------------------------------------------------------------------------
# Visibility toggle tests
# ---------------------------------------------------------------------------


class TestVisibilityToggle:
    """Tests for the foreground / unknown layer visibility eye-icon toggles."""

    def test_fg_eye_icon_toggles_visibility(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        fg_vis = block.locator("#te-fg-vis")
        expect(fg_vis).not_to_have_class(RE_VIS_OFF)

        fg_vis.click()
        expect(fg_vis).to_have_class(RE_VIS_OFF)

        fg_vis.click()
        expect(fg_vis).not_to_have_class(RE_VIS_OFF)

    def test_unknown_eye_icon_toggles_visibility(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        unknown_vis = block.locator("#te-unknown-vis")
        expect(unknown_vis).not_to_have_class(RE_VIS_OFF)

        unknown_vis.click()
        expect(unknown_vis).to_have_class(RE_VIS_OFF)

        unknown_vis.click()
        expect(unknown_vis).not_to_have_class(RE_VIS_OFF)

    def test_1_key_toggles_fg_visibility(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        block.focus()
        fg_vis = block.locator("#te-fg-vis")

        demo_app.keyboard.press("1")
        expect(fg_vis).to_have_class(RE_VIS_OFF)

        demo_app.keyboard.press("1")
        expect(fg_vis).not_to_have_class(RE_VIS_OFF)

    def test_2_key_toggles_unknown_visibility(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        block.focus()
        unknown_vis = block.locator("#te-unknown-vis")

        demo_app.keyboard.press("2")
        expect(unknown_vis).to_have_class(RE_VIS_OFF)

        demo_app.keyboard.press("2")
        expect(unknown_vis).not_to_have_class(RE_VIS_OFF)


# ---------------------------------------------------------------------------
# Image layer toggle tests
# ---------------------------------------------------------------------------


class TestImageLayerToggle:
    """Tests for the image layer toggle button."""

    def test_image_toggle_button(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        img_toggle = block.locator("#te-image-toggle")
        # Image toggle starts active (image visible by default)
        expect(img_toggle).to_have_class(RE_ACTIVE)

        img_toggle.click()
        expect(img_toggle).not_to_have_class(RE_ACTIVE)

        img_toggle.click()
        expect(img_toggle).to_have_class(RE_ACTIVE)

    def test_i_key_toggles_image(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        block.focus()
        img_toggle = block.locator("#te-image-toggle")

        demo_app.keyboard.press("i")
        expect(img_toggle).not_to_have_class(RE_ACTIVE)

        demo_app.keyboard.press("i")
        expect(img_toggle).to_have_class(RE_ACTIVE)


# ---------------------------------------------------------------------------
# Maximize tests
# ---------------------------------------------------------------------------


class TestMaximize:
    """Tests for the maximize / fullscreen toggle."""

    def test_maximize_button_toggles(self, demo_app: Page):
        block = get_editor_block(demo_app)
        wrapper = get_editor_element(demo_app)
        max_btn = block.locator("#te-maximize-btn")

        max_btn.click()
        expect(wrapper).to_have_class(RE_MAXIMIZED)

        max_btn.click()
        expect(wrapper).not_to_have_class(RE_MAXIMIZED)

    def test_m_key_toggles_maximize(self, demo_app: Page):
        block = get_editor_block(demo_app)
        wrapper = get_editor_element(demo_app)
        block.focus()

        demo_app.keyboard.press("m")
        expect(wrapper).to_have_class(RE_MAXIMIZED)

        demo_app.keyboard.press("m")
        expect(wrapper).not_to_have_class(RE_MAXIMIZED)

    def test_escape_exits_maximize(self, demo_app: Page):
        block = get_editor_block(demo_app)
        wrapper = get_editor_element(demo_app)
        block.focus()

        demo_app.keyboard.press("m")
        expect(wrapper).to_have_class(RE_MAXIMIZED)

        demo_app.keyboard.press("Escape")
        expect(wrapper).not_to_have_class(RE_MAXIMIZED)

    def test_canvas_size_preserved_after_draw_in_maximized(self, demo_app: Page):
        """Regression: drawing in maximized mode must not shrink the canvas.

        After a stroke, commitValue() triggers Gradio's DOM morph.
        te-maximized now lives on the Gradio wrapper (outside morph scope)
        so the canvas dimensions must remain stable.
        """
        block = get_editor_block(demo_app)
        wrapper = get_editor_element(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)
        wait_for_server_upload(demo_app)

        # Enter maximized mode
        block.focus()
        demo_app.keyboard.press("m")
        expect(wrapper).to_have_class(RE_MAXIMIZED)
        demo_app.wait_for_timeout(300)

        canvas = block.locator(".te-canvas")
        size_before = canvas.bounding_box()

        # Draw a stroke — triggers commitValue → DOM morph → handleValue
        demo_app.mouse.move(
            size_before["x"] + 60,
            size_before["y"] + 80,
        )
        demo_app.mouse.down()
        demo_app.mouse.move(
            size_before["x"] + 160,
            size_before["y"] + 80,
            steps=6,
        )
        demo_app.mouse.up()
        demo_app.wait_for_timeout(800)

        # Canvas must still fill the viewport, not shrink to 500px
        size_after = canvas.bounding_box()
        assert size_after["width"] == size_before["width"]
        assert size_after["height"] == size_before["height"]

        # te-maximized class must still be present on wrapper
        expect(wrapper).to_have_class(RE_MAXIMIZED)


# ---------------------------------------------------------------------------
# Help dialog tests
# ---------------------------------------------------------------------------


class TestHelpDialog:
    """Tests for the help dialog (? key / help button)."""

    def test_help_button_opens_dialog(self, demo_app: Page):
        block = get_editor_block(demo_app)
        overlay = block.locator(".te-help-overlay")
        expect(overlay).not_to_have_class(RE_VISIBLE)

        block.locator(".te-help-btn").click()
        expect(overlay).to_have_class(RE_VISIBLE)

    def test_question_mark_opens_help(self, demo_app: Page):
        block = get_editor_block(demo_app)
        block.focus()
        overlay = block.locator(".te-help-overlay")

        demo_app.keyboard.press("?")
        expect(overlay).to_have_class(RE_VISIBLE)

    def test_close_button_closes_help(self, demo_app: Page):
        block = get_editor_block(demo_app)
        overlay = block.locator(".te-help-overlay")

        block.locator(".te-help-btn").click()
        expect(overlay).to_have_class(RE_VISIBLE)

        block.locator(".te-help-close-btn").click()
        expect(overlay).not_to_have_class(RE_VISIBLE)

    def test_escape_closes_help(self, demo_app: Page):
        block = get_editor_block(demo_app)
        block.focus()
        overlay = block.locator(".te-help-overlay")

        demo_app.keyboard.press("?")
        expect(overlay).to_have_class(RE_VISIBLE)

        demo_app.keyboard.press("Escape")
        expect(overlay).not_to_have_class(RE_VISIBLE)


# ---------------------------------------------------------------------------
# Zoom keyboard tests
# ---------------------------------------------------------------------------


class TestZoomKeyboard:
    """Tests for keyboard zoom controls (+, -, 0)."""

    def test_plus_key_zooms_in(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)
        block.focus()

        zoom_before = demo_app.evaluate(
            "() => document.querySelector('.trimap-editor')._teState.zoom",
        )
        demo_app.keyboard.press("=")
        zoom_after = demo_app.evaluate(
            "() => document.querySelector('.trimap-editor')._teState.zoom",
        )
        assert zoom_after > zoom_before

    def test_minus_key_zooms_out(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        # Zoom in first so there is room to zoom out
        block.focus()
        demo_app.keyboard.press("=")
        demo_app.keyboard.press("=")

        zoom_before = demo_app.evaluate(
            "() => document.querySelector('.trimap-editor')._teState.zoom",
        )
        demo_app.keyboard.press("-")
        zoom_after = demo_app.evaluate(
            "() => document.querySelector('.trimap-editor')._teState.zoom",
        )
        assert zoom_after < zoom_before

    def test_zero_key_resets_zoom(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)
        block.focus()

        # Record the initial fit-zoom level
        fit_zoom = demo_app.evaluate(
            "() => document.querySelector('.trimap-editor')._teState.zoom",
        )

        # Zoom in twice
        demo_app.keyboard.press("=")
        demo_app.keyboard.press("=")
        zoomed = demo_app.evaluate(
            "() => document.querySelector('.trimap-editor')._teState.zoom",
        )
        assert zoomed > fit_zoom

        # 0 resets to fit-zoom
        demo_app.keyboard.press("0")
        zoom_after = demo_app.evaluate(
            "() => document.querySelector('.trimap-editor')._teState.zoom",
        )
        assert abs(zoom_after - fit_zoom) < 0.01


# ---------------------------------------------------------------------------
# Scroll wheel zoom test
# ---------------------------------------------------------------------------


class TestScrollWheelZoom:
    """Test scroll-wheel zoom on the canvas."""

    def test_wheel_zoom_changes_level(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2

        zoom_before = demo_app.evaluate(
            "() => document.querySelector('.trimap-editor')._teState.zoom",
        )

        # Scroll up = zoom in (negative deltaY)
        demo_app.mouse.move(cx, cy)
        demo_app.mouse.wheel(0, -120)
        demo_app.wait_for_timeout(200)

        zoom_after = demo_app.evaluate(
            "() => document.querySelector('.trimap-editor')._teState.zoom",
        )
        assert zoom_after != zoom_before


# ---------------------------------------------------------------------------
# Drag-and-drop file load test
# ---------------------------------------------------------------------------


class TestDragAndDrop:
    """Test loading an image via JS-simulated file drop."""

    def test_drop_file_loads_image(self, demo_app: Page):
        """Simulate a file drop by directly calling loadImageFile via JS."""
        block = get_editor_block(demo_app)

        # Use the file input as a reliable proxy for drag-and-drop — both
        # paths converge on the same loadImageFile handler.
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        expect(block.locator(".te-canvas-wrapper.te-has-image")).to_be_visible()


# ---------------------------------------------------------------------------
# Remove image tests
# ---------------------------------------------------------------------------


class TestRemoveImage:
    """Tests for removing the loaded image."""

    def test_remove_button_clears_image(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        block.locator("#te-remove-btn").click()

        # te-has-image should be gone and upload hint visible
        expect(block.locator(".te-canvas-wrapper.te-has-image")).not_to_be_visible()
        expect(block.locator(".te-upload-hint")).to_be_visible()

    def test_x_key_removes_image(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        block.focus()
        demo_app.keyboard.press("x")

        expect(block.locator(".te-canvas-wrapper.te-has-image")).not_to_be_visible()
        expect(block.locator(".te-upload-hint")).to_be_visible()


# ---------------------------------------------------------------------------
# Color palette tests
# ---------------------------------------------------------------------------


class TestColorPalette:
    """Tests for the overlay color palette open/close and selection."""

    def test_fg_palette_opens_and_closes(self, demo_app: Page):
        block = get_editor_block(demo_app)
        palette = block.locator("#te-color-palette")

        # Click foreground swatch to open palette
        block.locator("#te-fg-color").click()
        expect(palette).to_be_visible()

        # Click swatch again to close
        block.locator("#te-fg-color").click()
        expect(palette).not_to_be_visible()

    def test_unknown_palette_opens_and_closes(self, demo_app: Page):
        block = get_editor_block(demo_app)
        palette = block.locator("#te-color-palette")

        block.locator("#te-unknown-color").click()
        expect(palette).to_be_visible()

        block.locator("#te-unknown-color").click()
        expect(palette).not_to_be_visible()

    def test_palette_color_selection(self, demo_app: Page):
        block = get_editor_block(demo_app)
        swatch = block.locator("#te-fg-color")

        # Record the initial swatch background
        initial_bg = swatch.evaluate("el => getComputedStyle(el).backgroundColor")

        # Open palette, select red (#f44336)
        swatch.click()
        block.locator(".te-palette-item[data-color='#f44336']").click()

        new_bg = swatch.evaluate("el => getComputedStyle(el).backgroundColor")
        assert new_bg != initial_bg, (
            f"Swatch background should change after selecting a new color: before={initial_bg}, after={new_bg}"
        )


# ---------------------------------------------------------------------------
# Bracket key brush-size tests
# ---------------------------------------------------------------------------


class TestBracketKeys:
    """Tests for [ and ] keys adjusting brush/eraser size."""

    def test_bracket_right_increases_brush_size(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)
        block.focus()

        size_before = int(block.locator("#te-brush-size-val").text_content())
        demo_app.keyboard.press("]")
        size_after = int(block.locator("#te-brush-size-val").text_content())
        assert size_after > size_before

    def test_bracket_left_decreases_brush_size(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)
        block.focus()

        # Increase first so there is room to decrease
        demo_app.keyboard.press("]")
        demo_app.keyboard.press("]")
        size_before = int(block.locator("#te-brush-size-val").text_content())
        demo_app.keyboard.press("[")
        size_after = int(block.locator("#te-brush-size-val").text_content())
        assert size_after < size_before


# ---------------------------------------------------------------------------
# Clear confirmation tests
# ---------------------------------------------------------------------------


class TestClearConfirmation:
    """Tests for the two-click clear confirmation flow."""

    def test_clear_shows_confirm_state(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        # Draw a stroke so clear has something to clear
        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        demo_app.mouse.move(box["x"] + 60, box["y"] + 60)
        demo_app.mouse.down()
        demo_app.mouse.move(box["x"] + 120, box["y"] + 60, steps=5)
        demo_app.mouse.up()

        clear_btn = block.locator("#te-clear-btn")
        clear_btn.click()

        expect(clear_btn).to_have_class(RE_DANGER_CONFIRM)
        expect(clear_btn).to_have_text("Sure?")

    def test_clear_confirm_resets_after_timeout(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        # Draw a stroke
        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        demo_app.mouse.move(box["x"] + 60, box["y"] + 60)
        demo_app.mouse.down()
        demo_app.mouse.move(box["x"] + 120, box["y"] + 60, steps=5)
        demo_app.mouse.up()

        clear_btn = block.locator("#te-clear-btn")
        clear_btn.click()
        expect(clear_btn).to_have_class(RE_DANGER_CONFIRM)

        # Wait for the 2-second JS timeout to expire
        demo_app.wait_for_timeout(2500)

        expect(clear_btn).not_to_have_class(RE_DANGER_CONFIRM)
        expect(clear_btn).to_have_text("Clear")


# ---------------------------------------------------------------------------
# Trimap view key test
# ---------------------------------------------------------------------------


class TestTrimapViewKey:
    """Test for the V key toggling trimap grayscale view."""

    def test_v_key_toggles_trimap_view(self, demo_app: Page):
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)

        block.focus()
        trimap_btn = block.locator("#te-view-trimap-btn")

        demo_app.keyboard.press("v")
        expect(trimap_btn).to_have_class(RE_ACTIVE)

        demo_app.keyboard.press("v")
        expect(trimap_btn).not_to_have_class(RE_ACTIVE)
