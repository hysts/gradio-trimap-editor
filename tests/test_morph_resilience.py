"""DOM morph resilience tests.

These tests verify that toolbar elements, canvas dimensions, and CSS classes
survive Gradio's DOM-diffing cycle that runs after every props.value write
(commitValue triggers a DOM morph on every stroke).
"""

from __future__ import annotations

from _helpers import (
    EXAMPLES_DIR,
    RE_ACTIVE,
    get_editor_block,
    upload_and_draw,
    upload_image,
    wait_for_server_upload,
)
from playwright.sync_api import Page, expect


class TestToolbarSurvivesRoundTrip:
    def test_layer_buttons_present_after_commit(self, demo_app: Page):
        block = get_editor_block(demo_app)
        upload_and_draw(demo_app, block)

        # Toolbar buttons must still be present and visible after morph
        expect(block.locator("[data-layer='unknown']")).to_be_visible()
        expect(block.locator("[data-layer='foreground']")).to_be_visible()
        expect(block.locator("[data-tool='brush']")).to_be_visible()
        expect(block.locator("[data-tool='eraser']")).to_be_visible()

    def test_toolbar_buttons_still_clickable_after_commit(self, demo_app: Page):
        block = get_editor_block(demo_app)
        upload_and_draw(demo_app, block)

        # Should be able to switch layer after round-trip
        unknown_btn = block.locator("[data-layer='unknown']")
        unknown_btn.click()
        expect(unknown_btn).to_have_class(RE_ACTIVE)


class TestCanvasAfterRoundTrip:
    def test_canvas_visible_after_commit(self, demo_app: Page):
        block = get_editor_block(demo_app)
        upload_and_draw(demo_app, block)

        expect(block.locator(".te-canvas")).to_be_visible()
        # Canvas should have non-zero dimensions
        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        assert box["width"] > 0
        assert box["height"] > 0

    def test_has_image_class_reasserted_after_commit(self, demo_app: Page):
        block = get_editor_block(demo_app)
        upload_and_draw(demo_app, block)

        # te-has-image class must survive morph (re-asserted by MutationObserver)
        expect(block.locator(".te-canvas-wrapper.te-has-image")).to_be_visible()


class TestMultipleRoundTrips:
    def test_ui_consistent_after_multiple_commits(self, demo_app: Page):
        block = get_editor_block(demo_app)
        upload_and_draw(demo_app, block)

        for _ in range(2):
            # Draw more strokes (each triggers a commitValue → DOM morph)
            canvas = block.locator(".te-canvas")
            box = canvas.bounding_box()
            demo_app.mouse.move(box["x"] + 50, box["y"] + 50)
            demo_app.mouse.down()
            demo_app.mouse.move(box["x"] + 90, box["y"] + 70, steps=5)
            demo_app.mouse.up()
            demo_app.wait_for_timeout(500)

        # After multiple round-trips, toolbar still functional
        expect(block.locator("[data-layer='unknown']")).to_be_visible()
        expect(block.locator(".te-canvas")).to_be_visible()


class TestLayerButtonStateAfterMorph:
    """Regression tests for the layer-button active-state reset bug.

    Each stroke calls commitValue() which writes props.value asynchronously
    (toBlob → FileReader.onload → props.value = ...).  Gradio's DOM diff then
    resets every element's class attribute back to the template defaults
    (Foreground = active, Unknown = inactive).  syncUIState() in handleValue()
    must re-assert the correct state from state.layer / state.tool.
    """

    def test_unknown_layer_stays_active_after_stroke(self, demo_app: Page):
        """Switching to Unknown then drawing should not visually revert to Foreground."""
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)
        wait_for_server_upload(demo_app)

        # Switch to Unknown layer
        unknown_btn = block.locator("[data-layer='unknown']")
        fg_btn = block.locator("[data-layer='foreground']")
        unknown_btn.click()
        expect(unknown_btn).to_have_class(RE_ACTIVE)
        expect(fg_btn).not_to_have_class(RE_ACTIVE)

        # Draw a stroke — this triggers commitValue() → DOM morph
        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        demo_app.mouse.move(box["x"] + 60, box["y"] + 80)
        demo_app.mouse.down()
        demo_app.mouse.move(box["x"] + 130, box["y"] + 80, steps=8)
        demo_app.mouse.up()
        # Wait for the async toBlob → FileReader → props.value chain and morph
        demo_app.wait_for_timeout(600)

        # Unknown must still be active; Foreground must not be
        expect(unknown_btn).to_have_class(RE_ACTIVE)
        expect(fg_btn).not_to_have_class(RE_ACTIVE)

    def test_foreground_layer_stays_active_after_stroke(self, demo_app: Page):
        """Foreground layer (template default) stays active after a stroke morph."""
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)
        wait_for_server_upload(demo_app)

        # Foreground is the template default — it starts active
        fg_btn = block.locator("[data-layer='foreground']")
        expect(fg_btn).to_have_class(RE_ACTIVE)

        # Draw a stroke
        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        demo_app.mouse.move(box["x"] + 60, box["y"] + 80)
        demo_app.mouse.down()
        demo_app.mouse.move(box["x"] + 130, box["y"] + 80, steps=8)
        demo_app.mouse.up()
        demo_app.wait_for_timeout(600)

        # Foreground should still be active
        expect(fg_btn).to_have_class(RE_ACTIVE)

    def test_eraser_tool_stays_active_after_stroke(self, demo_app: Page):
        """Eraser tool selection persists through a commit morph."""
        block = get_editor_block(demo_app)
        example_img = next(EXAMPLES_DIR.glob("*.jpg"))
        upload_image(block, example_img)
        wait_for_server_upload(demo_app)

        # First draw something so there's something to erase
        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        demo_app.mouse.move(box["x"] + 60, box["y"] + 80)
        demo_app.mouse.down()
        demo_app.mouse.move(box["x"] + 130, box["y"] + 80, steps=8)
        demo_app.mouse.up()
        demo_app.wait_for_timeout(600)

        # Switch to Eraser
        eraser_btn = block.locator("[data-tool='eraser']")
        brush_btn = block.locator("[data-tool='brush']")
        eraser_btn.click()
        expect(eraser_btn).to_have_class(RE_ACTIVE)
        expect(brush_btn).not_to_have_class(RE_ACTIVE)

        # Draw an eraser stroke (triggers another morph)
        demo_app.mouse.move(box["x"] + 70, box["y"] + 80)
        demo_app.mouse.down()
        demo_app.mouse.move(box["x"] + 100, box["y"] + 80, steps=5)
        demo_app.mouse.up()
        demo_app.wait_for_timeout(600)

        # Eraser must still be selected
        expect(eraser_btn).to_have_class(RE_ACTIVE)
        expect(brush_btn).not_to_have_class(RE_ACTIVE)


class TestCutoutStateAfterMorph:
    """Cutout and invert button states must survive DOM morph after commit."""

    def test_cutout_active_survives_stroke(self, demo_app: Page):
        """Cutout mode stays active after a drawing stroke triggers DOM morph."""
        block = get_editor_block(demo_app)
        upload_and_draw(demo_app, block)

        # Activate cutout
        cutout_btn = block.locator("#te-view-cutout-btn")
        cutout_btn.click()
        expect(cutout_btn).to_have_class(RE_ACTIVE)

        # Draw another stroke → triggers commitValue → DOM morph
        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        demo_app.mouse.move(box["x"] + 70, box["y"] + 60)
        demo_app.mouse.down()
        demo_app.mouse.move(box["x"] + 140, box["y"] + 60, steps=6)
        demo_app.mouse.up()
        demo_app.wait_for_timeout(600)

        # Cutout must still be active after morph
        expect(cutout_btn).to_have_class(RE_ACTIVE)

    def test_cutout_invert_survives_stroke(self, demo_app: Page):
        """Both cutout and invert states survive DOM morph."""
        block = get_editor_block(demo_app)
        upload_and_draw(demo_app, block)

        # Activate cutout + invert
        cutout_btn = block.locator("#te-view-cutout-btn")
        invert_btn = block.locator("#te-cutout-invert-btn")
        cutout_btn.click()
        invert_btn.click()
        expect(cutout_btn).to_have_class(RE_ACTIVE)
        expect(invert_btn).to_have_class(RE_ACTIVE)
        expect(invert_btn).to_be_enabled()

        # Draw → DOM morph
        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        demo_app.mouse.move(box["x"] + 70, box["y"] + 60)
        demo_app.mouse.down()
        demo_app.mouse.move(box["x"] + 140, box["y"] + 60, steps=6)
        demo_app.mouse.up()
        demo_app.wait_for_timeout(600)

        # Both must survive
        expect(cutout_btn).to_have_class(RE_ACTIVE)
        expect(invert_btn).to_have_class(RE_ACTIVE)
        expect(invert_btn).to_be_enabled()


class TestSliderStateAfterMorph:
    """Slider values and labels must survive DOM morph after commitValue."""

    def test_brush_size_survives_stroke(self, demo_app: Page):
        """Brush size slider and label persist through a commit morph."""
        block = get_editor_block(demo_app)
        upload_and_draw(demo_app, block)

        # Change brush size to 80
        demo_app.evaluate("""() => {
            var el = document.querySelector('.trimap-editor');
            var slider = el.querySelector('#te-brush-size');
            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            nativeInputValueSetter.call(slider, '80');
            slider.dispatchEvent(new Event('input', { bubbles: true }));
        }""")
        expect(block.locator("#te-brush-size-val")).to_have_text("80")

        # Draw a stroke → triggers commitValue → DOM morph
        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        demo_app.mouse.move(box["x"] + 50, box["y"] + 50)
        demo_app.mouse.down()
        demo_app.mouse.move(box["x"] + 120, box["y"] + 50, steps=6)
        demo_app.mouse.up()
        demo_app.wait_for_timeout(600)

        # Slider value and label must survive morph
        expect(block.locator("#te-brush-size")).to_have_value("80")
        expect(block.locator("#te-brush-size-val")).to_have_text("80")

    def test_eraser_size_survives_stroke(self, demo_app: Page):
        """Eraser size slider and label persist through a commit morph."""
        block = get_editor_block(demo_app)
        upload_and_draw(demo_app, block)

        # Switch to eraser and change size to 50
        block.locator("[data-tool='eraser']").click()
        demo_app.evaluate("""() => {
            var el = document.querySelector('.trimap-editor');
            var slider = el.querySelector('#te-eraser-size');
            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            nativeInputValueSetter.call(slider, '50');
            slider.dispatchEvent(new Event('input', { bubbles: true }));
        }""")
        expect(block.locator("#te-eraser-size-val")).to_have_text("50")

        # Draw → morph
        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        demo_app.mouse.move(box["x"] + 50, box["y"] + 50)
        demo_app.mouse.down()
        demo_app.mouse.move(box["x"] + 120, box["y"] + 50, steps=6)
        demo_app.mouse.up()
        demo_app.wait_for_timeout(600)

        # Must survive
        expect(block.locator("#te-eraser-size")).to_have_value("50")
        expect(block.locator("#te-eraser-size-val")).to_have_text("50")

    def test_alpha_survives_stroke(self, demo_app: Page):
        """Fg and unknown alpha sliders and labels persist through commit morph."""
        block = get_editor_block(demo_app)
        upload_and_draw(demo_app, block)

        # Change fg alpha to 30%, unknown alpha to 80%
        demo_app.evaluate("""() => {
            var el = document.querySelector('.trimap-editor');
            var setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            var fgSlider = el.querySelector('#te-fg-alpha');
            setter.call(fgSlider, '30');
            fgSlider.dispatchEvent(new Event('input', { bubbles: true }));
            var unSlider = el.querySelector('#te-unknown-alpha');
            setter.call(unSlider, '80');
            unSlider.dispatchEvent(new Event('input', { bubbles: true }));
        }""")
        expect(block.locator("#te-fg-alpha-val")).to_have_text("30%")
        expect(block.locator("#te-unknown-alpha-val")).to_have_text("80%")

        # Draw → morph
        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        demo_app.mouse.move(box["x"] + 50, box["y"] + 50)
        demo_app.mouse.down()
        demo_app.mouse.move(box["x"] + 120, box["y"] + 50, steps=6)
        demo_app.mouse.up()
        demo_app.wait_for_timeout(600)

        # Must survive
        expect(block.locator("#te-fg-alpha")).to_have_value("30")
        expect(block.locator("#te-fg-alpha-val")).to_have_text("30%")
        expect(block.locator("#te-unknown-alpha")).to_have_value("80")
        expect(block.locator("#te-unknown-alpha-val")).to_have_text("80%")


class TestColorSwatchAfterMorph:
    """Color swatch backgrounds must survive DOM morph after commitValue."""

    def test_fg_color_survives_stroke(self, demo_app: Page):
        """Foreground color swatch retains chosen color after commit morph."""
        block = get_editor_block(demo_app)
        upload_and_draw(demo_app, block)

        # Change fg color to red (#f44336) via palette
        block.locator("#te-fg-color").click()
        block.locator(".te-palette-item[data-color='#f44336']").click()
        # Verify swatch changed
        swatch = block.locator("#te-fg-color")
        color = swatch.evaluate("el => getComputedStyle(el).backgroundColor")
        assert "68" in color or "244" in color  # rgb(244, 67, 54) or similar

        # Draw → morph
        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        demo_app.mouse.move(box["x"] + 50, box["y"] + 50)
        demo_app.mouse.down()
        demo_app.mouse.move(box["x"] + 120, box["y"] + 50, steps=6)
        demo_app.mouse.up()
        demo_app.wait_for_timeout(600)

        # Swatch must still show red, not default green
        color_after = swatch.evaluate("el => getComputedStyle(el).backgroundColor")
        assert "244" in color_after  # rgb(244, 67, 54)

    def test_unknown_color_survives_stroke(self, demo_app: Page):
        """Unknown color swatch retains chosen color after commit morph."""
        block = get_editor_block(demo_app)
        upload_and_draw(demo_app, block)

        # Change unknown color to purple (#9c27b0) via palette
        block.locator("#te-unknown-color").click()
        block.locator(".te-palette-item[data-color='#9c27b0']").click()
        swatch = block.locator("#te-unknown-color")
        color = swatch.evaluate("el => getComputedStyle(el).backgroundColor")
        assert "156" in color  # rgb(156, 39, 176)

        # Draw → morph
        canvas = block.locator(".te-canvas")
        box = canvas.bounding_box()
        demo_app.mouse.move(box["x"] + 50, box["y"] + 50)
        demo_app.mouse.down()
        demo_app.mouse.move(box["x"] + 120, box["y"] + 50, steps=6)
        demo_app.mouse.up()
        demo_app.wait_for_timeout(600)

        # Must still show purple, not default blue
        color_after = swatch.evaluate("el => getComputedStyle(el).backgroundColor")
        assert "156" in color_after  # rgb(156, 39, 176)
