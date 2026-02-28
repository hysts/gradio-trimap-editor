(function () {
    "use strict";

    // ── Constants ───────────────────────────────────────────────────
    var MIN_ZOOM = 0.05;
    var MAX_ZOOM = 20;
    var ZOOM_SENSITIVITY = 0.001;
    var MAX_HISTORY = 30;
    var DEFAULT_UNKNOWN_COLOR = "#2196F3";
    var DEFAULT_FG_COLOR = "#00c853";

    // ── DOM refs ────────────────────────────────────────────────────
    var container    = element.querySelector(".trimap-editor");
    var dataScript   = element.querySelector("script.te-data");
    var canvas       = element.querySelector(".te-canvas");
    var canvasWrapper = element.querySelector(".te-canvas-wrapper");
    var fileInput    = element.querySelector("#te-file-input");

    var brushSizeSlider  = element.querySelector("#te-brush-size");
    var brushSizeVal     = element.querySelector("#te-brush-size-val");
    var eraserSizeSlider = element.querySelector("#te-eraser-size");
    var eraserSizeVal    = element.querySelector("#te-eraser-size-val");
    var fgAlphaSlider      = element.querySelector("#te-fg-alpha");
    var unknownAlphaSlider = element.querySelector("#te-unknown-alpha");
    // Fg group is first in DOM, Unknown second
    var fgAlphaVal         = element.querySelector("#te-fg-alpha-val");
    var unknownAlphaVal    = element.querySelector("#te-unknown-alpha-val");

    var unknownColorSwatch = element.querySelector("#te-unknown-color");
    var fgColorSwatch      = element.querySelector("#te-fg-color");
    var colorPalette       = element.querySelector("#te-color-palette");

    var fgVisBtn       = element.querySelector("#te-fg-vis");
    var unknownVisBtn  = element.querySelector("#te-unknown-vis");

    var undoBtn         = element.querySelector("#te-undo-btn");
    var redoBtn         = element.querySelector("#te-redo-btn");
    var removeBtn       = element.querySelector("#te-remove-btn");
    var imageToggleBtn  = element.querySelector("#te-image-toggle");
    var clearBtn        = element.querySelector("#te-clear-btn");
    var viewTrimapBtn   = element.querySelector("#te-view-trimap-btn");
    var viewCutoutBtn   = element.querySelector("#te-view-cutout-btn");
    var cutoutInvertBtn = element.querySelector("#te-cutout-invert-btn");
    var fitBtn          = element.querySelector("#te-fit-btn");
    var maximizeBtn     = element.querySelector("#te-maximize-btn");
    var helpBtn         = element.querySelector(".te-help-btn");
    var helpOverlay     = element.querySelector(".te-help-overlay");
    var helpCloseBtn    = element.querySelector(".te-help-close-btn");

    var ctx = canvas.getContext("2d");

    // ── Off-screen mask canvases (natural image size) ───────────────
    var unknownCanvas = document.createElement("canvas");
    var unknownCtx    = unknownCanvas.getContext("2d");
    var fgCanvas      = document.createElement("canvas");
    var fgCtx         = fgCanvas.getContext("2d");

    // Temp canvas for colored overlay compositing
    var tCanvas = document.createElement("canvas");
    var tCtx    = tCanvas.getContext("2d");

    // Trimap view canvas: composited grayscale (0/128/255), updated on stroke end
    var trimapViewCanvas = document.createElement("canvas");
    var trimapViewCtx    = trimapViewCanvas.getContext("2d");

    // Checkerboard pattern for cutout preview (16x16 tile)
    var checkerCanvas = document.createElement("canvas");
    checkerCanvas.width = 16; checkerCanvas.height = 16;
    var ckCtx = checkerCanvas.getContext("2d");
    ckCtx.fillStyle = "#ccc"; ckCtx.fillRect(0, 0, 16, 16);
    ckCtx.fillStyle = "#999"; ckCtx.fillRect(0, 0, 8, 8);
    ckCtx.fillStyle = "#999"; ckCtx.fillRect(8, 8, 8, 8);

    // ── State ───────────────────────────────────────────────────────
    var state = {
        image:       null,  // HTMLImageElement
        imageUrl:    null,  // Python-provided URL (/gradio_api/file=...)
        objectUrl:   null,  // blob URL (user-uploaded)
        fileUrl:     null,  // public URL from upload()
        imageSource: null,  // "upload" | "python"
        pendingCommit: false,  // commit queued while image upload in-flight

        layer:       "foreground",  // "foreground" | "unknown"
        tool:        "brush",    // "brush" | "eraser" | "bucket" | "pan"
        prevDrawTool: "brush",  // last non-pan tool (for pan toggle)
        brushSizeBrush:  20,
        brushSizeEraser: 10,
        unknownAlpha: 0.60,
        fgAlpha:     0.60,
        unknownColor: DEFAULT_UNKNOWN_COLOR,
        fgColor:     DEFAULT_FG_COLOR,
        savedFgAlpha:      0.60,  // remembered alpha when visibility toggled off
        savedUnknownAlpha: 0.60,

        zoom:     1,
        panX:     0,
        panY:     0,
        isPanning: false,
        spaceHeld: false,
        panStartX: 0,
        panStartY: 0,
        panStartPanX: 0,
        panStartPanY: 0,

        isDrawing:   false,
        pendingDot:  null,       // deferred initial dot {x, y}
        pendingDotTimer: null,   // setTimeout id for deferred dot
        lastIX:      0,
        lastIY:      0,
        mouseInsideCanvas: false,
        cursorOverImage: false,
        cursorX:     -1,
        cursorY:     -1,

        showImage:     true,
        showTrimap:    false,   // trimap view mode
        showCutout:    false,   // cutout preview mode
        cutoutInvert:  false,   // invert cutout (show outside of mask)
        maximized:     false,

        history:     [],  // [{unknown: ImageData, fg: ImageData}]
        historyIndex: -1,
    };

    // ── Resize Observer ─────────────────────────────────────────────

    var resizeObserver = new ResizeObserver(function () {
        resizeCanvas();
        if (state.image) {
            clampPan();
            render();
        }
    });
    resizeObserver.observe(canvasWrapper);

    // ── MutationObserver: value updates from Python ──────────────────
    var dataObserver = new MutationObserver(handleValue);
    dataObserver.observe(dataScript, { childList: true, characterData: true, subtree: true });

    // ── MutationObserver: re-assert CSS classes wiped by DOM diff ───
    var containerObserver = new MutationObserver(function () {
        // Re-assert te-has-image on canvasWrapper
        var shouldHaveImage = state.image !== null;
        if (shouldHaveImage !== canvasWrapper.classList.contains("te-has-image")) {
            canvasWrapper.classList.toggle("te-has-image", shouldHaveImage);
        }
    });
    containerObserver.observe(container, { attributes: true, attributeFilter: ["class"] });
    containerObserver.observe(canvasWrapper, { attributes: true, attributeFilter: ["class"] });

    // Expose state and canvases on the container element for UI tests (read-only references).
    container._teState = state;
    container._teUnknownCanvas = unknownCanvas;
    container._teFgCanvas = fgCanvas;

    // Handle initial value
    handleValue();

    // ── Value handler ────────────────────────────────────────────────

    // Re-assert all dynamic CSS class states onto toolbar elements after a
    // DOM morph.  Gradio's DOM diff resets every element's class attribute
    // back to the template defaults, so we must re-apply JS state here.
    function syncUIState() {
        // Re-assert button active classes (morph resets to template defaults)
        element.querySelectorAll("[data-layer]").forEach(function (b) {
            b.classList.toggle("active", b.getAttribute("data-layer") === state.layer);
        });
        var activeTool = state.spaceHeld ? "pan" : state.tool;
        element.querySelectorAll("[data-tool]").forEach(function (b) {
            b.classList.toggle("active", b.getAttribute("data-tool") === activeTool);
        });
        imageToggleBtn.classList.toggle("active", state.showImage);
        viewTrimapBtn.classList.toggle("active", state.showTrimap);
        viewCutoutBtn.classList.toggle("active", state.showCutout);
        cutoutInvertBtn.classList.toggle("active", state.cutoutInvert);
        cutoutInvertBtn.disabled = !state.showCutout;
        fgVisBtn.classList.toggle("te-vis-off", state.fgAlpha <= 0);
        unknownVisBtn.classList.toggle("te-vis-off", state.unknownAlpha <= 0);

        // Re-assert slider values and labels (morph resets to template defaults)
        brushSizeSlider.value = state.brushSizeBrush;
        brushSizeVal.textContent = state.brushSizeBrush;
        eraserSizeSlider.value = state.brushSizeEraser;
        eraserSizeVal.textContent = state.brushSizeEraser;
        var fgPct = Math.round(state.fgAlpha * 100);
        fgAlphaSlider.value = fgPct;
        fgAlphaVal.textContent = fgPct + "%";
        var unPct = Math.round(state.unknownAlpha * 100);
        unknownAlphaSlider.value = unPct;
        unknownAlphaVal.textContent = unPct + "%";

        // Re-assert color swatch backgrounds (morph resets inline styles)
        fgColorSwatch.style.background = state.fgColor;
        unknownColorSwatch.style.background = state.unknownColor;

        // Re-assert undo/redo disabled state (morph resets to template default)
        updateHistoryButtons();

        // Re-assert cursor (morph resets inline styles on canvas)
        updateCursor();
    }

    function handleValue() {
        // Re-assert te-has-image which Gradio's DOM morph may have stripped.
        // (te-maximized lives on the Gradio wrapper, outside the morph scope.)
        canvasWrapper.classList.toggle("te-has-image", state.image !== null);

        var raw = dataScript.textContent.trim();

        if (!raw || raw === "null") {
            // DOM may have been morphed — re-assert canvas and UI state
            if (state.image) {
                resizeCanvas();
                clampPan();
                render();
            }
            syncUIState();
            return;
        }

        var data;
        try {
            data = JSON.parse(raw);
        } catch (e) {
            return;
        }

        // Our own committed value echoing back — don't reload image
        if ("trimapBase64" in data) {
            resizeCanvas();
            clampPan();
            render();
            syncUIState();
            return;
        }

        // Input from Python (postprocess): {image, width, height}
        if ("image" in data) {
            // Clean up any previous user-upload state
            if (state.objectUrl) {
                URL.revokeObjectURL(state.objectUrl);
                state.objectUrl = null;
            }
            state.pendingCommit = false;

            var imageUrl = data.image;
            // Store the stripped path for commitValue(); img.src uses
            // the local imageUrl variable which still has the full URL.
            var marker = "/gradio_api/file=";
            var mIdx = imageUrl.indexOf(marker);
            state.imageUrl = mIdx !== -1
                ? imageUrl.substring(mIdx + marker.length) : imageUrl;
            state.imageSource = "python";
            state.fileUrl = null;

            var trimapUrl = data.trimap || null;

            var img = new Image();
            img.onload = function () {
                // Set up canvas and compute zoom BEFORE setting state.image so
                // that any ResizeObserver render triggered by canvasWrapper layout
                // queries finds state.image=null and skips rendering, preventing
                // a brief zoom=1 flash before the first correct render.
                initMaskCanvases(img.naturalWidth, img.naturalHeight);
                clearHistory();
                canvasWrapper.classList.add("te-has-image");
                resizeCanvas();
                var iw = img.naturalWidth;
                var ih = img.naturalHeight;
                var cw = canvas.width;
                var ch = canvas.height;
                var z = Math.min(cw / iw, ch / ih);
                state.zoom = z;
                state.panX = (cw - iw * z) / 2;
                state.panY = (ch - ih * z) / 2;

                // Set state.image now — zoom/pan are ready, and the
                // MutationObserver needs state.image !== null to re-assert
                // the te-has-image class if a DOM morph fires while we're
                // still loading the trimap asynchronously.
                state.image = img;

                // Notify Python that a new image arrived (e.g. for resize
                // checks). Only .input() handlers fire — commitValue() after
                // strokes does NOT call trigger("input"), so drawing never
                // causes a round-trip.
                trigger("input");

                if (trimapUrl) {
                    // Show image immediately (blank mask), then overlay trimap
                    render();
                    var trimapImg = new Image();
                    trimapImg.onload = function () {
                        parseTrimapIntoCanvases(trimapImg, iw, ih);
                        updateTrimapView();
                        snapshotHistory();
                        render();
                        // Re-commit so Python sees stripped path + trimapBase64
                        commitValue();
                    };
                    trimapImg.onerror = function () {
                        // Trimap failed to load — proceed without it
                        snapshotHistory();
                    };
                    trimapImg.src = trimapUrl;
                } else {
                    snapshotHistory();
                    render();
                }
            };
            img.onerror = function () {
                // Silently ignore load errors
            };
            img.src = imageUrl;
        }
    }

    // ── Mask canvas init ─────────────────────────────────────────────

    function initMaskCanvases(w, h) {
        unknownCanvas.width  = w;
        unknownCanvas.height = h;
        fgCanvas.width  = w;
        fgCanvas.height = h;
        tCanvas.width   = w;
        tCanvas.height  = h;
        trimapViewCanvas.width  = w;
        trimapViewCanvas.height = h;
        unknownCtx.clearRect(0, 0, w, h);
        fgCtx.clearRect(0, 0, w, h);
    }

    // Parse a trimap image (0/128/255 grayscale) into unknownCanvas and fgCanvas.
    // Uses generous thresholds (>200 for fg, >64 for unknown) to tolerate slight
    // value shifts from image format conversions.
    function parseTrimapIntoCanvases(trimapImg, w, h) {
        tCanvas.width = w;
        tCanvas.height = h;
        var tc = tCanvas.getContext("2d");
        tc.drawImage(trimapImg, 0, 0, w, h);
        var trimapData = tc.getImageData(0, 0, w, h).data;

        var unknownImgData = unknownCtx.createImageData(w, h);
        var fgImgData = fgCtx.createImageData(w, h);
        var ud = unknownImgData.data;
        var fd = fgImgData.data;

        for (var i = 0; i < w * h; i++) {
            var px = i * 4;
            var val = trimapData[px]; // R channel (grayscale: R==G==B)
            if (val > 200) {
                // Foreground (255): paint both canvases
                ud[px] = fd[px] = 255;
                ud[px + 1] = fd[px + 1] = 255;
                ud[px + 2] = fd[px + 2] = 255;
                ud[px + 3] = fd[px + 3] = 255;
            } else if (val > 64) {
                // Unknown (128): paint only unknown canvas
                ud[px] = ud[px + 1] = ud[px + 2] = ud[px + 3] = 255;
            }
            // else: background (0) — both stay at 0 (default)
        }

        unknownCtx.putImageData(unknownImgData, 0, 0);
        fgCtx.putImageData(fgImgData, 0, 0);
    }

    // ── Canvas resize ────────────────────────────────────────────────
    // Canvas always fills the wrapper; zoom/pan handle image fitting.

    function resizeCanvas() {
        var w = Math.round(canvasWrapper.clientWidth  || 800);
        var h = Math.round(canvasWrapper.clientHeight || 500);
        // Skip if dimensions unchanged — setting canvas.width/height clears
        // the canvas content per HTML5 spec, causing visible flicker during
        // the echo cycle (commitValue → DOM morph → handleValue → resize).
        if (canvas.width === w && canvas.height === h) return;
        canvas.width  = w;
        canvas.height = h;
    }

    // ── Zoom helpers ─────────────────────────────────────────────────

    function minZoom() {
        if (!state.image) return MIN_ZOOM;
        var cw = canvas.width  || 1;
        var ch = canvas.height || 1;
        return Math.min(cw / state.image.naturalWidth, ch / state.image.naturalHeight);
    }

    function resetZoom() {
        if (!state.image) return;
        var iw = state.image.naturalWidth;
        var ih = state.image.naturalHeight;
        var cw = canvas.width;
        var ch = canvas.height;
        // Contain fit: scale image to fit entirely within canvas
        var zoom = Math.min(cw / iw, ch / ih);
        state.zoom = zoom;
        // Center the image
        state.panX = (cw - iw * zoom) / 2;
        state.panY = (ch - ih * zoom) / 2;
        render();
    }

    function clampPan() {
        if (!state.image) return;
        var imgW = state.image.naturalWidth  * state.zoom;
        var imgH = state.image.naturalHeight * state.zoom;
        var cw = canvas.width;
        var ch = canvas.height;

        // Any image point can reach canvas center (half-screen overscroll).
        // Works for both zoomed-in (imgW > cw) and zoomed-out (imgW <= cw).
        var maxPanX = cw / 2;
        var minPanX = cw / 2 - imgW;
        if (state.panX > maxPanX) state.panX = maxPanX;
        if (state.panX < minPanX) state.panX = minPanX;

        var maxPanY = ch / 2;
        var minPanY = ch / 2 - imgH;
        if (state.panY > maxPanY) state.panY = maxPanY;
        if (state.panY < minPanY) state.panY = minPanY;
    }

    function zoomToCenter(newZoom) {
        newZoom = Math.max(minZoom(), Math.min(MAX_ZOOM, newZoom));
        var cx = canvas.width  / 2;
        var cy = canvas.height / 2;
        state.panX = cx - (cx - state.panX) * (newZoom / state.zoom);
        state.panY = cy - (cy - state.panY) * (newZoom / state.zoom);
        state.zoom = newZoom;
        clampPan();
        render();
    }

    // ── Coordinate conversion ────────────────────────────────────────

    function clientToImage(clientX, clientY) {
        var rect = canvas.getBoundingClientRect();
        var cssX = clientX - rect.left;
        var cssY = clientY - rect.top;
        // account for CSS vs pixel dimensions
        var scaleX = canvas.width  / rect.width;
        var scaleY = canvas.height / rect.height;
        var canvasX = cssX * scaleX;
        var canvasY = cssY * scaleY;
        // canvas = pan + zoom * image
        return {
            x: (canvasX - state.panX) / state.zoom,
            y: (canvasY - state.panY) / state.zoom,
        };
    }

    // ── Rendering ────────────────────────────────────────────────────

    var _rafId = null;
    function requestRender() {
        if (_rafId) return;
        _rafId = requestAnimationFrame(function () {
            _rafId = null;
            render();
        });
    }

    function render() {
        if (!state.image) return;

        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Dark background
        ctx.fillStyle = "#1a1a1a";
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        var iw = state.image.naturalWidth;
        var ih = state.image.naturalHeight;

        // Apply zoom + pan
        ctx.setTransform(state.zoom, 0, 0, state.zoom, state.panX, state.panY);

        if (state.showTrimap) {
            // Trimap view: draw grayscale trimap (0/128/255)
            ctx.imageSmoothingEnabled = false;
            ctx.drawImage(trimapViewCanvas, 0, 0, iw, ih);
        } else if (state.showCutout) {
            // Cutout preview: active layer mask on checkerboard
            // Mask canvas: fg or unknown depending on active layer
            var maskSrc = state.layer === "foreground" ? fgCanvas : unknownCanvas;

            // 1. Fill image area with checkerboard
            var checkerPattern = ctx.createPattern(checkerCanvas, "repeat");
            ctx.fillStyle = checkerPattern;
            ctx.fillRect(0, 0, iw, ih);
            ctx.imageSmoothingEnabled = false;

            // 2. Image masked by the active layer (or its inverse)
            tCtx.clearRect(0, 0, iw, ih);
            tCtx.globalCompositeOperation = "source-over";
            tCtx.drawImage(state.image, 0, 0);
            if (state.cutoutInvert) {
                // Invert: remove mask region, keep outside
                tCtx.globalCompositeOperation = "destination-out";
            } else {
                // Normal: keep only mask region
                tCtx.globalCompositeOperation = "destination-in";
            }
            tCtx.drawImage(maskSrc, 0, 0);
            tCtx.globalCompositeOperation = "source-over";
            ctx.drawImage(tCanvas, 0, 0, iw, ih);
        } else {
            // Normal view: image + colored overlays
            if (state.showImage) {
                ctx.imageSmoothingEnabled = true;
                ctx.drawImage(state.image, 0, 0, iw, ih);
            }

            ctx.imageSmoothingEnabled = false;
            // 2. Draw unknown overlay
            drawMaskOverlay(unknownCanvas, unknownCtx, state.unknownColor, state.unknownAlpha);
            // 3. Draw foreground overlay (on top)
            drawMaskOverlay(fgCanvas, fgCtx, state.fgColor, state.fgAlpha);
        }

        // Back to screen space for UI elements
        ctx.setTransform(1, 0, 0, 1, 0, 0);

        // 4. Zoom badge
        var zoomText = Math.round(state.zoom * 100) + "%";
        ctx.font = "bold 12px -apple-system, BlinkMacSystemFont, sans-serif";
        var tm = ctx.measureText(zoomText);
        var px = canvas.width  - tm.width - 16;
        var py = canvas.height - 24;
        ctx.fillStyle = "rgba(0,0,0,0.55)";
        ctx.beginPath();
        ctx.roundRect(px - 5, py - 2, tm.width + 10, 18, 3);
        ctx.fill();
        ctx.fillStyle = "#fff";
        ctx.textBaseline = "top";
        ctx.fillText(zoomText, px, py + 1);

        // 5. Cursor circle (skip if outside image, pan mode, or bucket tool)
        var inPanMode = state.isPanning || state.spaceHeld || state.tool === "pan";
        if (state.mouseInsideCanvas && state.cursorOverImage && state.cursorX >= 0 && !inPanMode && state.tool !== "bucket") {
            drawCursor(state.cursorX, state.cursorY);
        }
    }

    function drawMaskOverlay(maskCanvas, maskCtxArg, colorHex, alpha) {
        if (alpha <= 0) return;
        var iw = maskCanvas.width;
        var ih = maskCanvas.height;
        // Composite: mask → color, then draw with alpha
        tCtx.clearRect(0, 0, iw, ih);
        tCtx.drawImage(maskCanvas, 0, 0);
        tCtx.globalCompositeOperation = "source-in";
        tCtx.fillStyle = colorHex;
        tCtx.fillRect(0, 0, iw, ih);
        tCtx.globalCompositeOperation = "source-over";

        ctx.globalAlpha = alpha;
        ctx.drawImage(tCanvas, 0, 0, iw, ih);
        ctx.globalAlpha = 1;
    }

    function drawCursor(canvasX, canvasY) {
        var r = getBrushSize();
        ctx.save();
        ctx.setLineDash([3, 3]);
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = state.tool === "eraser" ? "rgba(255,60,60,0.9)" : "rgba(255,255,255,0.9)";
        ctx.beginPath();
        ctx.arc(canvasX, canvasY, Math.max(1, r), 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.restore();
    }

    // ── Drawing ──────────────────────────────────────────────────────

    function paintAt(ix, iy) {
        var r = getBrushSize() / state.zoom;
        if (state.tool === "brush") {
            if (state.layer === "unknown") {
                unknownCtx.globalCompositeOperation = "source-over";
                unknownCtx.fillStyle = "rgba(255,255,255,1)";
                unknownCtx.beginPath();
                unknownCtx.arc(ix, iy, r, 0, Math.PI * 2);
                unknownCtx.fill();
            } else {
                // Foreground: paint both fg AND unknown
                fgCtx.globalCompositeOperation = "source-over";
                fgCtx.fillStyle = "rgba(255,255,255,1)";
                fgCtx.beginPath();
                fgCtx.arc(ix, iy, r, 0, Math.PI * 2);
                fgCtx.fill();

                unknownCtx.globalCompositeOperation = "source-over";
                unknownCtx.fillStyle = "rgba(255,255,255,1)";
                unknownCtx.beginPath();
                unknownCtx.arc(ix, iy, r, 0, Math.PI * 2);
                unknownCtx.fill();
            }
        } else {
            // Eraser
            if (state.layer === "unknown") {
                // Erase unknown AND fg (fg ⊆ unknown constraint)
                unknownCtx.globalCompositeOperation = "destination-out";
                unknownCtx.fillStyle = "rgba(255,255,255,1)";
                unknownCtx.beginPath();
                unknownCtx.arc(ix, iy, r, 0, Math.PI * 2);
                unknownCtx.fill();
                unknownCtx.globalCompositeOperation = "source-over";

                fgCtx.globalCompositeOperation = "destination-out";
                fgCtx.fillStyle = "rgba(255,255,255,1)";
                fgCtx.beginPath();
                fgCtx.arc(ix, iy, r, 0, Math.PI * 2);
                fgCtx.fill();
                fgCtx.globalCompositeOperation = "source-over";
            } else {
                // Erase fg only (stays unknown)
                fgCtx.globalCompositeOperation = "destination-out";
                fgCtx.fillStyle = "rgba(255,255,255,1)";
                fgCtx.beginPath();
                fgCtx.arc(ix, iy, r, 0, Math.PI * 2);
                fgCtx.fill();
                fgCtx.globalCompositeOperation = "source-over";
            }
        }
    }

    function paintInterpolated(x0, y0, x1, y1) {
        var dx = x1 - x0;
        var dy = y1 - y0;
        var dist = Math.sqrt(dx * dx + dy * dy);
        var imageRadius = getBrushSize() / state.zoom;
        var steps = Math.max(1, Math.ceil(dist / (imageRadius * 0.3)));
        for (var i = 1; i <= steps; i++) {
            var t = i / steps;
            paintAt(x0 + dx * t, y0 + dy * t);
        }
    }

    // ── Flood fill (bucket tool) ────────────────────────────────────

    function floodFillAt(ix, iy) {
        var px = Math.floor(ix);
        var py = Math.floor(iy);
        var w = unknownCanvas.width;
        var h = unknownCanvas.height;
        if (px < 0 || px >= w || py < 0 || py >= h) return;

        // Choose the active canvas to read boundaries from
        var activeCanvas = state.layer === "foreground" ? fgCanvas : unknownCanvas;
        var activeCtx    = state.layer === "foreground" ? fgCtx   : unknownCtx;
        var imgData = activeCtx.getImageData(0, 0, w, h);
        var data = imgData.data;

        // If start pixel is already painted (alpha > 127), nothing to fill
        var startIdx = (py * w + px) * 4;
        if (data[startIdx + 3] > 127) return;

        // BFS
        var visited = new Uint8Array(w * h);
        var queue = [py * w + px];
        visited[py * w + px] = 1;
        var filled = [py * w + px];

        while (queue.length > 0) {
            var idx = queue.shift();
            var cx = idx % w;
            var cy = (idx - cx) / w;

            var neighbors = [];
            if (cx > 0)     neighbors.push(idx - 1);
            if (cx < w - 1) neighbors.push(idx + 1);
            if (cy > 0)     neighbors.push(idx - w);
            if (cy < h - 1) neighbors.push(idx + w);

            for (var i = 0; i < neighbors.length; i++) {
                var ni = neighbors[i];
                if (visited[ni]) continue;
                visited[ni] = 1;
                // Boundary: painted pixels (alpha > 127)
                if (data[ni * 4 + 3] > 127) continue;
                queue.push(ni);
                filled.push(ni);
            }
        }

        // Write filled pixels to active canvas
        for (var j = 0; j < filled.length; j++) {
            var fi = filled[j] * 4;
            data[fi]     = 255;  // R
            data[fi + 1] = 255;  // G
            data[fi + 2] = 255;  // B
            data[fi + 3] = 255;  // A
        }
        activeCtx.putImageData(imgData, 0, 0);

        // fg ⊆ unknown: if foreground layer, also fill unknownCanvas
        if (state.layer === "foreground") {
            var uData = unknownCtx.getImageData(0, 0, w, h);
            var ud = uData.data;
            for (var k = 0; k < filled.length; k++) {
                var ui = filled[k] * 4;
                ud[ui]     = 255;
                ud[ui + 1] = 255;
                ud[ui + 2] = 255;
                ud[ui + 3] = 255;
            }
            unknownCtx.putImageData(uData, 0, 0);
        }
    }

    // ── History ──────────────────────────────────────────────────────

    function clearHistory() {
        state.history = [];
        state.historyIndex = -1;
        updateHistoryButtons();
    }

    function snapshotHistory() {
        var w = unknownCanvas.width;
        var h = unknownCanvas.height;
        if (w === 0 || h === 0) return;

        // Truncate redo stack
        state.history = state.history.slice(0, state.historyIndex + 1);
        state.history.push({
            unknown: unknownCtx.getImageData(0, 0, w, h),
            fg:      fgCtx.getImageData(0, 0, w, h),
        });
        if (state.history.length > MAX_HISTORY) {
            state.history.shift();
        }
        state.historyIndex = state.history.length - 1;
        updateHistoryButtons();
    }

    function undo() {
        if (state.historyIndex <= 0) return;
        state.historyIndex--;
        restoreSnapshot(state.history[state.historyIndex]);
        updateHistoryButtons();
        updateTrimapView();
        commitValue();
        render();
    }

    function redo() {
        if (state.historyIndex >= state.history.length - 1) return;
        state.historyIndex++;
        restoreSnapshot(state.history[state.historyIndex]);
        updateHistoryButtons();
        updateTrimapView();
        commitValue();
        render();
    }

    function restoreSnapshot(snap) {
        unknownCtx.putImageData(snap.unknown, 0, 0);
        fgCtx.putImageData(snap.fg, 0, 0);
    }

    function updateHistoryButtons() {
        undoBtn.disabled = state.historyIndex <= 0;
        redoBtn.disabled = state.historyIndex >= state.history.length - 1;
    }

    // ── Trimap view & value commit ───────────────────────────────────

    // Composites unknownCanvas + fgCanvas into trimapViewCanvas (0/128/255 grayscale).
    // Called after each stroke end, undo/redo, clear.
    function updateTrimapView() {
        var iw = unknownCanvas.width;
        var ih = unknownCanvas.height;
        if (iw === 0 || ih === 0) return;

        trimapViewCanvas.width  = iw;
        trimapViewCanvas.height = ih;

        var unknownData = unknownCtx.getImageData(0, 0, iw, ih).data;
        var fgData      = fgCtx.getImageData(0, 0, iw, ih).data;
        var out = trimapViewCtx.createImageData(iw, ih);
        var d   = out.data;

        for (var i = 0; i < iw * ih; i++) {
            var a = i * 4 + 3;
            var val;
            if (fgData[a] > 127) {
                val = 255;
            } else if (unknownData[a] > 127) {
                val = 128;
            } else {
                val = 0;
            }
            d[i * 4]     = val;
            d[i * 4 + 1] = val;
            d[i * 4 + 2] = val;
            d[i * 4 + 3] = 255;
        }
        trimapViewCtx.putImageData(out, 0, 0);
    }

    // Encodes the current trimap as a base64 PNG and stores it in props.value.
    // No trigger("input") — value is picked up lazily when another button fires.
    function commitValue() {
        if (!state.image) return;

        // Build image reference
        var imageRef = state.imageUrl;
        if (!imageRef && state.fileUrl) {
            imageRef = state.fileUrl;
        }
        if (!imageRef) {
            // Image upload still in progress — defer until upload completes
            state.pendingCommit = true;
            return;
        }
        // Strip Gradio file-serving prefix so Python receives a local path.
        // URL may be relative (/gradio_api/file=...) or absolute
        // (http://host/gradio_api/file=...) depending on the source.
        var marker = "/gradio_api/file=";
        var idx = imageRef.indexOf(marker);
        if (idx !== -1) {
            imageRef = imageRef.substring(idx + marker.length);
        }

        var iw = unknownCanvas.width;
        var ih = unknownCanvas.height;
        var imageRefCopy = imageRef;

        trimapViewCanvas.toBlob(function (blob) {
            var reader = new FileReader();
            reader.onload = function () {
                props.value = JSON.stringify({
                    image:       imageRefCopy,
                    trimapBase64: reader.result,  // "data:image/png;base64,..."
                    width:       iw,
                    height:      ih,
                });
            };
            reader.readAsDataURL(blob);
        }, "image/png");
    }

    // ── File upload ──────────────────────────────────────────────────

    function loadImageFile(file) {
        if (!file || !file.type.startsWith("image/")) return;

        // Revoke previous blob URL
        if (state.objectUrl) URL.revokeObjectURL(state.objectUrl);

        var url = URL.createObjectURL(file);
        state.objectUrl  = url;
        state.fileUrl   = null;
        state.imageUrl   = null;
        state.imageSource = "upload";
        state.pendingCommit = false;

        var img = new Image();
        img.onload = function () {
            // Set up canvas and compute zoom BEFORE setting state.image so
            // that any ResizeObserver render triggered by canvasWrapper layout
            // queries finds state.image=null and skips rendering, preventing
            // a brief zoom=1 flash before the first correct render.
            initMaskCanvases(img.naturalWidth, img.naturalHeight);
            clearHistory();
            canvasWrapper.classList.add("te-has-image");
            resizeCanvas();
            var iw = img.naturalWidth;
            var ih = img.naturalHeight;
            var cw = canvas.width;
            var ch = canvas.height;
            var z = Math.min(cw / iw, ch / ih);
            state.zoom = z;
            state.panX = (cw - iw * z) / 2;
            state.panY = (ch - ih * z) / 2;
            // Set state.image last: first render() always has correct zoom/pan,
            // and mousedown's state.image guard blocks clicks until ready.
            state.image = img;
            render();
        };
        img.src = url;

        // Upload to server in parallel; image is rendered immediately from blob URL
        uploadToServer(file, url);
    }

    function uploadToServer(file, capturedUrl) {
        upload(file).then(function (result) {
            if (state.objectUrl !== capturedUrl) return; // stale upload
            state.fileUrl = result.url;
            // NOTE: Do NOT set props.value = {image, width, height} here.
            // Doing so would re-trigger handleValue, which would treat the
            // server path as a Python-provided image and call initMaskCanvases +
            // clearHistory, wiping any masks the user has already drawn and
            // causing a visible re-initialization flicker.
            // props.value is set by commitValue() (with trimapBase64) when
            // the user draws a stroke or explicitly exports the trimap.
            if (state.pendingCommit) {
                state.pendingCommit = false;
                updateTrimapView();
                commitValue();
            }
        }).catch(function () {
            if (state.objectUrl !== capturedUrl) return;
        });
    }

    // ── Focus on hover so keyboard shortcuts work without a click ────
    canvas.addEventListener("mouseenter", function () {
        container.focus();
    });

    // ── Canvas mouse/pointer events ──────────────────────────────────

    canvas.addEventListener("mousedown", function (e) {
        if (!state.image) return;
        // Note: drawing is allowed in trimap view mode so users can fix holes directly

        var panActive = state.spaceHeld || state.tool === "pan";
        if (e.button === 1 || e.button === 2 || (e.button === 0 && panActive)) {
            // Middle / right button, Space+left-click, or Pan tool → pan
            e.preventDefault();
            state.isPanning   = true;
            state.panStartX   = e.clientX;
            state.panStartY   = e.clientY;
            state.panStartPanX = state.panX;
            state.panStartPanY = state.panY;
            canvas.style.cursor = "grabbing";
            return;
        }

        if (e.button !== 0) return;

        e.preventDefault();

        // Skip drawing on the 2nd click of a double-click (detail >= 2).
        // The dblclick handler will undo the 1st click's dot and reset zoom.
        if (e.detail >= 2) return;

        // Bucket tool: single-click flood fill, no drag
        if (state.tool === "bucket") {
            var bpt = clientToImage(e.clientX, e.clientY);
            if (state.historyIndex < 0) snapshotHistory();
            floodFillAt(bpt.x, bpt.y);
            snapshotHistory();
            updateTrimapView();
            commitValue();
            requestRender();
            return;
        }

        state.isDrawing = true;
        var pt = clientToImage(e.clientX, e.clientY);
        state.lastIX = pt.x;
        state.lastIY = pt.y;
        // Defer the initial dot so double-click doesn't flash a painted pixel.
        // The dot is flushed immediately on mousemove (drag) or after a short
        // timeout (single click without drag).  dblclick cancels it entirely.
        state.pendingDot = { x: pt.x, y: pt.y };
        state.pendingDotTimer = setTimeout(function () {
            if (!state.pendingDot) return;
            if (state.historyIndex < 0) snapshotHistory();
            paintAt(state.pendingDot.x, state.pendingDot.y);
            state.pendingDot = null;
            state.pendingDotTimer = null;
            requestRender();
            // mouseup already fired (click without drag) → finalize stroke
            if (!state.isDrawing) {
                snapshotHistory();
                updateTrimapView();
                commitValue();
            }
        }, 300);
    });

    window.addEventListener("mousemove", function (e) {
        if (!state.image) return;

        if (state.isPanning) {
            var dx = e.clientX - state.panStartX;
            var dy = e.clientY - state.panStartY;
            var rect = canvas.getBoundingClientRect();
            state.panX = state.panStartPanX + dx * (canvas.width  / rect.width);
            state.panY = state.panStartPanY + dy * (canvas.height / rect.height);
            clampPan();
            requestRender();
            return;
        }

        // Update cursor position for rendering
        var rect = canvas.getBoundingClientRect();
        if (e.clientX >= rect.left && e.clientX <= rect.right &&
            e.clientY >= rect.top  && e.clientY <= rect.bottom) {
            var scaleX = canvas.width  / rect.width;
            var scaleY = canvas.height / rect.height;
            state.cursorX = (e.clientX - rect.left) * scaleX;
            state.cursorY = (e.clientY - rect.top)  * scaleY;
            state.mouseInsideCanvas = true;
            // Check if cursor is over the actual image area
            var ix = (state.cursorX - state.panX) / state.zoom;
            var iy = (state.cursorY - state.panY) / state.zoom;
            var iw = state.image.naturalWidth;
            var ih = state.image.naturalHeight;
            state.cursorOverImage = ix >= 0 && ix < iw && iy >= 0 && iy < ih;
        } else {
            state.mouseInsideCanvas = false;
            state.cursorOverImage = false;
        }
        updateCursor();

        if (state.isDrawing) {
            // Flush deferred dot on first drag move
            if (state.pendingDot) {
                clearTimeout(state.pendingDotTimer);
                state.pendingDotTimer = null;
                if (state.historyIndex < 0) snapshotHistory();
                paintAt(state.pendingDot.x, state.pendingDot.y);
                state.pendingDot = null;
            }
            var pt = clientToImage(e.clientX, e.clientY);
            paintInterpolated(state.lastIX, state.lastIY, pt.x, pt.y);
            state.lastIX = pt.x;
            state.lastIY = pt.y;
            // Keep trimapViewCanvas current so strokes are visible in real-time
            if (state.showTrimap) updateTrimapView();
        }

        requestRender();
    });

    window.addEventListener("mouseup", function (e) {
        if (state.isPanning) {
            state.isPanning = false;
            updateCursor();
            return;
        }
        if (!state.isDrawing) return;
        state.isDrawing = false;
        // If the dot is still pending (click without drag), let the timer
        // handle painting + snapshotting.  dblclick may cancel it.
        if (state.pendingDot) return;
        snapshotHistory();
        updateTrimapView();
        commitValue();
        requestRender();
    });

    canvas.addEventListener("mouseleave", function () {
        state.mouseInsideCanvas = false;
        requestRender();
    });

    canvas.addEventListener("contextmenu", function (e) {
        e.preventDefault();
    });

    // Double-click anywhere → reset zoom to contain-fit
    // The initial dot from the 1st mousedown is deferred (pendingDot),
    // so we just cancel it here — no undo needed, no visual flicker.
    canvas.addEventListener("dblclick", function (e) {
        if (!state.image) return;
        e.preventDefault();
        state.isDrawing = false;
        if (state.pendingDotTimer) {
            clearTimeout(state.pendingDotTimer);
            state.pendingDotTimer = null;
        }
        state.pendingDot = null;
        resetZoom();
    });

    // ── Wheel zoom ───────────────────────────────────────────────────

    canvas.addEventListener("wheel", function (e) {
        if (!state.image) return;
        e.preventDefault();

        var delta = e.deltaY;
        if (e.deltaMode === 1) delta *= 16;
        else if (e.deltaMode === 2) delta *= 100;

        var newZoom = state.zoom * (1 - delta * ZOOM_SENSITIVITY);
        newZoom = Math.max(minZoom(), Math.min(MAX_ZOOM, newZoom));

        // Zoom toward cursor
        var rect = canvas.getBoundingClientRect();
        var mx = (e.clientX - rect.left) * (canvas.width  / rect.width);
        var my = (e.clientY - rect.top)  * (canvas.height / rect.height);
        state.panX = mx - (mx - state.panX) * (newZoom / state.zoom);
        state.panY = my - (my - state.panY) * (newZoom / state.zoom);
        state.zoom = newZoom;
        clampPan();
        requestRender();
    }, { passive: false });

    // ── Toolbar controls ─────────────────────────────────────────────

    // Layer buttons
    element.querySelectorAll("[data-layer]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            state.layer = this.getAttribute("data-layer");
            element.querySelectorAll("[data-layer]").forEach(function (b) {
                b.classList.toggle("active", b.getAttribute("data-layer") === state.layer);
            });
        });
    });

    // Tool buttons
    element.querySelectorAll("[data-tool]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            activateTool(this.getAttribute("data-tool"));
        });
    });

    // Brush size slider
    brushSizeSlider.addEventListener("input", function () {
        state.brushSizeBrush = parseInt(this.value, 10);
        brushSizeVal.textContent = this.value;
        requestRender();
    });

    // Eraser size slider
    eraserSizeSlider.addEventListener("input", function () {
        state.brushSizeEraser = parseInt(this.value, 10);
        eraserSizeVal.textContent = this.value;
        requestRender();
    });

    // Unknown alpha slider
    unknownAlphaSlider.addEventListener("input", function () {
        state.unknownAlpha = parseInt(this.value, 10) / 100;
        unknownAlphaVal.textContent = this.value + "%";
        requestRender();
    });

    // Fg alpha slider
    fgAlphaSlider.addEventListener("input", function () {
        state.fgAlpha = parseInt(this.value, 10) / 100;
        fgAlphaVal.textContent = this.value + "%";
        requestRender();
    });

    // ── Color palette ──────────────────────────────────────────────
    var _activeColorTarget = null; // "unknown" | "foreground"

    function openColorPalette(targetLayer, anchorEl) {
        _activeColorTarget = targetLayer;
        var currentColor = targetLayer === "unknown" ? state.unknownColor : state.fgColor;
        // Mark current selection
        colorPalette.querySelectorAll(".te-palette-item").forEach(function (item) {
            item.classList.toggle("te-selected", item.getAttribute("data-color") === currentColor);
        });
        // Position below the anchor swatch
        var rect = anchorEl.getBoundingClientRect();
        var containerRect = container.getBoundingClientRect();
        colorPalette.style.left = Math.max(0, rect.left - containerRect.left) + "px";
        colorPalette.style.top  = (rect.bottom - containerRect.top + 4) + "px";
        colorPalette.classList.add("te-visible");
    }

    function closeColorPalette() {
        colorPalette.classList.remove("te-visible");
        _activeColorTarget = null;
    }

    unknownColorSwatch.addEventListener("click", function (e) {
        e.stopPropagation();
        if (_activeColorTarget === "unknown") { closeColorPalette(); return; }
        openColorPalette("unknown", unknownColorSwatch);
    });

    fgColorSwatch.addEventListener("click", function (e) {
        e.stopPropagation();
        if (_activeColorTarget === "foreground") { closeColorPalette(); return; }
        openColorPalette("foreground", fgColorSwatch);
    });

    colorPalette.addEventListener("click", function (e) {
        e.stopPropagation();
        var item = e.target.closest(".te-palette-item");
        if (!item) return;
        var color = item.getAttribute("data-color");
        if (_activeColorTarget === "unknown") {
            state.unknownColor = color;
            unknownColorSwatch.style.background = color;
        } else if (_activeColorTarget === "foreground") {
            state.fgColor = color;
            fgColorSwatch.style.background = color;
        }
        closeColorPalette();
        requestRender();
    });

    // Close palette on outside click
    document.addEventListener("click", function () {
        if (_activeColorTarget) closeColorPalette();
    });

    // Prevent palette click from propagating to document
    container.addEventListener("click", function (e) {
        if (_activeColorTarget && !e.target.closest(".te-color-swatch") && !e.target.closest(".te-color-palette")) {
            closeColorPalette();
        }
    });

    // ── Visibility toggles (eye icon) ────────────────────────────

    function toggleVisibility(layer) {
        if (layer === "foreground") {
            if (state.fgAlpha > 0) {
                state.savedFgAlpha = state.fgAlpha;
                state.fgAlpha = 0;
            } else {
                state.fgAlpha = state.savedFgAlpha > 0 ? state.savedFgAlpha : 0.60;
            }
            var pct = Math.round(state.fgAlpha * 100);
            fgAlphaSlider.value = pct;
            fgAlphaVal.textContent = pct + "%";
            fgVisBtn.classList.toggle("te-vis-off", state.fgAlpha <= 0);
        } else {
            if (state.unknownAlpha > 0) {
                state.savedUnknownAlpha = state.unknownAlpha;
                state.unknownAlpha = 0;
            } else {
                state.unknownAlpha = state.savedUnknownAlpha > 0 ? state.savedUnknownAlpha : 0.40;
            }
            var pct = Math.round(state.unknownAlpha * 100);
            unknownAlphaSlider.value = pct;
            unknownAlphaVal.textContent = pct + "%";
            unknownVisBtn.classList.toggle("te-vis-off", state.unknownAlpha <= 0);
        }
        requestRender();
    }

    fgVisBtn.addEventListener("click", function () { toggleVisibility("foreground"); });
    unknownVisBtn.addEventListener("click", function () { toggleVisibility("unknown"); });

    // Sync eye icon state when sliders are adjusted manually
    fgAlphaSlider.addEventListener("input", function () {
        var val = parseInt(this.value, 10) / 100;
        if (val > 0) state.savedFgAlpha = val;
        fgVisBtn.classList.toggle("te-vis-off", val <= 0);
    });
    unknownAlphaSlider.addEventListener("input", function () {
        var val = parseInt(this.value, 10) / 100;
        if (val > 0) state.savedUnknownAlpha = val;
        unknownVisBtn.classList.toggle("te-vis-off", val <= 0);
    });

    // Image toggle
    imageToggleBtn.addEventListener("click", function () {
        state.showImage = !state.showImage;
        imageToggleBtn.classList.toggle("active", state.showImage);
        requestRender();
    });

    // Clear (two-click confirm)
    var clearConfirmTimer = null;
    function resetClearBtn() {
        clearBtn.textContent = "Clear";
        clearBtn.classList.remove("te-btn-danger-confirm");
        clearConfirmTimer = null;
    }
    clearBtn.addEventListener("click", function () {
        if (!state.image) return;
        if (!clearConfirmTimer) {
            // First click — ask for confirmation
            clearBtn.textContent = "Sure?";
            clearBtn.classList.add("te-btn-danger-confirm");
            clearConfirmTimer = setTimeout(resetClearBtn, 2000);
            return;
        }
        // Second click — confirmed
        clearTimeout(clearConfirmTimer);
        resetClearBtn();
        snapshotHistory(); // save before clear
        var w = unknownCanvas.width;
        var h = unknownCanvas.height;
        unknownCtx.clearRect(0, 0, w, h);
        fgCtx.clearRect(0, 0, w, h);
        snapshotHistory();
        updateTrimapView();
        commitValue();
        render();
    });

    // View Trimap toggle
    viewTrimapBtn.addEventListener("click", function () {
        toggleTrimapView();
    });
    viewCutoutBtn.addEventListener("click", function () {
        toggleCutoutView();
    });
    cutoutInvertBtn.addEventListener("click", function () {
        toggleCutoutInvert();
    });

    function toggleTrimapView() {
        if (!state.image) return;
        state.showTrimap = !state.showTrimap;
        if (state.showTrimap) {
            state.showCutout = false;
            viewCutoutBtn.classList.remove("active");
            updateTrimapView();
        }
        viewTrimapBtn.classList.toggle("active", state.showTrimap);
        requestRender();
    }

    function toggleCutoutView() {
        if (!state.image) return;
        state.showCutout = !state.showCutout;
        if (state.showCutout) {
            state.showTrimap = false;
            viewTrimapBtn.classList.remove("active");
        } else {
            state.cutoutInvert = false;
            cutoutInvertBtn.classList.remove("active");
        }
        viewCutoutBtn.classList.toggle("active", state.showCutout);
        cutoutInvertBtn.disabled = !state.showCutout;
        requestRender();
    }

    function toggleCutoutInvert() {
        if (!state.showCutout) return;
        state.cutoutInvert = !state.cutoutInvert;
        cutoutInvertBtn.classList.toggle("active", state.cutoutInvert);
        requestRender();
    }

    // Remove image
    function removeImage() {
        if (!state.image) return;

        // Exit maximize mode if active
        if (state.maximized) toggleMaximize();

        // Revoke blob URL if any
        if (state.objectUrl) {
            URL.revokeObjectURL(state.objectUrl);
            state.objectUrl = null;
        }

        // Reset image state
        state.image       = null;
        state.imageUrl    = null;
        state.fileUrl    = null;
        state.imageSource = null;
        state.pendingCommit = false;
        state.showTrimap  = false;
        state.showCutout  = false;
        state.cutoutInvert = false;
        viewTrimapBtn.classList.remove("active");
        viewCutoutBtn.classList.remove("active");
        cutoutInvertBtn.classList.remove("active");
        cutoutInvertBtn.disabled = true;

        // Reset clear button confirm state
        if (clearConfirmTimer) { clearTimeout(clearConfirmTimer); resetClearBtn(); }

        // Clear mask canvases
        unknownCtx.clearRect(0, 0, unknownCanvas.width, unknownCanvas.height);
        fgCtx.clearRect(0, 0, fgCanvas.width, fgCanvas.height);
        clearHistory();

        // Remove has-image class to show upload hint
        canvasWrapper.classList.remove("te-has-image");

        // Reset file input so same file can be re-selected
        fileInput.value = "";

        // Clear display canvas
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Reset zoom/pan
        state.zoom = 1;
        state.panX = 0;
        state.panY = 0;

        // Clear component value
        props.value = "";
    }

    removeBtn.addEventListener("click", removeImage);

    // Maximize
    //
    // Gradio adds a "pending" class with opacity < 1 on ancestor elements
    // during server round-trips (.change() handlers).  opacity < 1 creates
    // a new stacking context, making z-index: 9999 local to that context
    // and letting other Gradio components render on top of the overlay.
    // To prevent this, pin opacity: 1 !important on all ancestors while
    // maximized.
    var _opacityPinnedEls = [];
    function pinAncestorOpacity() {
        _opacityPinnedEls.forEach(function (el) {
            el.style.removeProperty("opacity");
        });
        _opacityPinnedEls = [];
        if (!state.maximized) return;
        var el = element.parentElement;
        while (el && el !== document.documentElement) {
            el.style.setProperty("opacity", "1", "important");
            _opacityPinnedEls.push(el);
            el = el.parentElement;
        }
    }

    function toggleMaximize() {
        state.maximized = !state.maximized;
        // Set on the Gradio wrapper (element) so DOM morph cannot strip it.
        element.classList.toggle("te-maximized", state.maximized);
        document.body.style.overflow = state.maximized ? "hidden" : "";
        pinAncestorOpacity();
        if (state.image) {
            requestAnimationFrame(function () {
                resizeCanvas();
                resetZoom();
            });
        }
    }

    fitBtn.addEventListener("click", function () { resetZoom(); });
    maximizeBtn.addEventListener("click", toggleMaximize);

    // ── Help dialog ────────────────────────────────────────────────
    function toggleHelp() {
        helpOverlay.classList.toggle("te-visible");
    }

    helpBtn.addEventListener("click", toggleHelp);
    helpCloseBtn.addEventListener("click", toggleHelp);
    helpOverlay.addEventListener("click", function (e) {
        if (e.target === helpOverlay) toggleHelp();
    });

    // Undo / Redo buttons
    undoBtn.addEventListener("click", undo);
    redoBtn.addEventListener("click", redo);
    updateHistoryButtons();

    // ── File input ───────────────────────────────────────────────────

    fileInput.addEventListener("change", function () {
        if (this.files && this.files[0]) {
            loadImageFile(this.files[0]);
        }
    });

    // Drag & drop on canvas wrapper
    canvasWrapper.addEventListener("dragover", function (e) { e.preventDefault(); });
    canvasWrapper.addEventListener("drop", function (e) {
        e.preventDefault();
        var file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
        if (file) loadImageFile(file);
    });

    // ── Cursor ─────────────────────────────────────────────────────────

    function updateCursor() {
        if (state.isPanning) {
            canvas.style.cursor = "grabbing";
        } else if (state.spaceHeld || state.tool === "pan") {
            canvas.style.cursor = "grab";
        } else if (state.cursorOverImage) {
            canvas.style.cursor = "crosshair";
        } else {
            canvas.style.cursor = "default";
        }
    }

    // ── Keyboard shortcuts ───────────────────────────────────────────

    container.setAttribute("tabindex", "0");
    container.style.outline = "none";

    container.addEventListener("keydown", function (e) {
        if (e.target.tagName === "INPUT") return;

        // Help dialog shortcuts (work even without image)
        if (e.key === "?") {
            toggleHelp(); e.preventDefault(); return;
        }
        if (e.key === "Escape" && helpOverlay.classList.contains("te-visible")) {
            toggleHelp(); e.preventDefault(); return;
        }

        // Space hold → temporary pan mode
        if (e.key === " " && !e.repeat) {
            e.preventDefault();
            state.spaceHeld = true;
            // Visually highlight Pan button while Space is held
            element.querySelectorAll("[data-tool]").forEach(function (b) {
                b.classList.toggle("active", b.getAttribute("data-tool") === "pan");
            });
            updateCursor();
            return;
        }

        if (e.key === "Escape") {
            if (state.maximized) { toggleMaximize(); e.preventDefault(); }
            return;
        }
        if (e.key === "i" || e.key === "I") {
            state.showImage = !state.showImage;
            imageToggleBtn.classList.toggle("active", state.showImage);
            requestRender(); e.preventDefault(); return;
        }
        if (e.key === "m" || e.key === "M") {
            toggleMaximize(); e.preventDefault(); return;
        }
        if (e.key === "v" || e.key === "V") {
            toggleTrimapView(); e.preventDefault(); return;
        }
        if (e.key === "c" || e.key === "C") {
            toggleCutoutView(); e.preventDefault(); return;
        }
        if (e.key === "n" || e.key === "N") {
            toggleCutoutInvert(); e.preventDefault(); return;
        }
        if (e.key === "u" || e.key === "U") {
            activateLayer("unknown"); e.preventDefault(); return;
        }
        if (e.key === "f" || e.key === "F") {
            activateLayer("foreground"); e.preventDefault(); return;
        }
        if (e.key === "b" || e.key === "B") {
            activateTool("brush"); e.preventDefault(); return;
        }
        if (e.key === "e" || e.key === "E") {
            activateTool("eraser"); e.preventDefault(); return;
        }
        if (e.key === "p" || e.key === "P") {
            activateTool("pan"); e.preventDefault(); return;
        }
        if (e.key === "g" || e.key === "G") {
            activateTool("bucket"); e.preventDefault(); return;
        }
        if (e.key === "x" || e.key === "X") {
            removeImage(); e.preventDefault(); return;
        }
        if (e.key === "1") {
            toggleVisibility("foreground"); e.preventDefault(); return;
        }
        if (e.key === "2") {
            toggleVisibility("unknown"); e.preventDefault(); return;
        }
        if (e.key === "[") {
            adjustBrushSize(-2); e.preventDefault(); return;
        }
        if (e.key === "]") {
            adjustBrushSize(2); e.preventDefault(); return;
        }
        if (e.key === "+" || e.key === "=") {
            zoomToCenter(state.zoom * 1.25); e.preventDefault(); return;
        }
        if (e.key === "-" || e.key === "_") {
            zoomToCenter(state.zoom / 1.25); e.preventDefault(); return;
        }
        if (e.key === "0") {
            resetZoom(); e.preventDefault(); return;
        }
        if (e.ctrlKey && e.shiftKey && (e.key === "z" || e.key === "Z")) {
            redo(); e.preventDefault(); return;
        }
        if (e.ctrlKey && (e.key === "z" || e.key === "Z")) {
            undo(); e.preventDefault(); return;
        }
    });

    container.addEventListener("keyup", function (e) {
        if (e.key === " ") {
            state.spaceHeld = false;
            // Restore the actual tool's active state
            element.querySelectorAll("[data-tool]").forEach(function (b) {
                b.classList.toggle("active", b.getAttribute("data-tool") === state.tool);
            });
            updateCursor();
        }
    });

    function activateLayer(layer) {
        state.layer = layer;
        element.querySelectorAll("[data-layer]").forEach(function (b) {
            b.classList.toggle("active", b.getAttribute("data-layer") === layer);
        });
        // Cutout preview follows the active layer
        if (state.showCutout) requestRender();
    }

    function getBrushSize() {
        return state.tool === "eraser" ? state.brushSizeEraser : state.brushSizeBrush;
    }

    function activateTool(tool) {
        if (tool === "pan" && state.tool === "pan") {
            // Toggle off: revert to previous drawing tool
            tool = state.prevDrawTool;
        } else if (tool === "pan") {
            // Entering pan: remember current tool for toggle-back
            state.prevDrawTool = state.tool;
        } else {
            // Any non-pan tool: update prevDrawTool
            state.prevDrawTool = tool;
        }
        state.tool = tool;
        element.querySelectorAll("[data-tool]").forEach(function (b) {
            b.classList.toggle("active", b.getAttribute("data-tool") === tool);
        });
        updateCursor();
    }

    function adjustBrushSize(delta) {
        var newSize;
        if (state.tool === "eraser") {
            newSize = Math.max(2, Math.min(200, state.brushSizeEraser + delta));
            state.brushSizeEraser = newSize;
            eraserSizeSlider.value = newSize;
            eraserSizeVal.textContent = newSize;
        } else {
            newSize = Math.max(2, Math.min(200, state.brushSizeBrush + delta));
            state.brushSizeBrush = newSize;
            brushSizeSlider.value = newSize;
            brushSizeVal.textContent = newSize;
        }
        requestRender();
    }

    // ── Window resize ─────────────────────────────────────────────────

    var resizeTimer = null;
    window.addEventListener("resize", function () {
        if (resizeTimer) clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function () {
            if (state.image) {
                resizeCanvas();
                if (!state.maximized) resetZoom();
                else render();
            }
        }, 150);
    });

})();
