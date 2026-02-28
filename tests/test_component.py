"""Python-side unit tests for TrimapEditor component."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from trimap_editor import TrimapEditor


@pytest.fixture
def editor():
    return TrimapEditor()


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    img = Image.new("RGB", (200, 150), (100, 150, 200))
    p = tmp_path / "sample.jpg"
    img.save(p)
    return p


class TestPostprocess:
    def test_returns_none_for_none(self, editor: TrimapEditor) -> None:
        assert editor.postprocess(None) is None

    def test_returns_string_for_pil_image(self, editor: TrimapEditor) -> None:
        img = Image.new("RGB", (100, 80))
        result = editor.postprocess(img)
        assert isinstance(result, str)

    def test_returns_string_for_file_path(self, editor: TrimapEditor, sample_image: Path) -> None:
        result = editor.postprocess(str(sample_image))
        assert isinstance(result, str)

    def test_payload_has_required_keys(self, editor: TrimapEditor) -> None:
        img = Image.new("RGB", (100, 80))
        result = editor.postprocess(img)
        data = json.loads(result)
        assert "image" in data
        assert "width" in data
        assert "height" in data

    def test_payload_image_is_url(self, editor: TrimapEditor) -> None:
        img = Image.new("RGB", (100, 80))
        result = editor.postprocess(img)
        data = json.loads(result)
        assert data["image"].startswith("/gradio_api/file=")

    def test_payload_dimensions_match(self, editor: TrimapEditor) -> None:
        img = Image.new("RGB", (320, 240))
        result = editor.postprocess(img)
        data = json.loads(result)
        assert data["width"] == 320
        assert data["height"] == 240

    def test_cached_file_exists(self, editor: TrimapEditor) -> None:
        img = Image.new("RGB", (50, 50))
        result = editor.postprocess(img)
        data = json.loads(result)
        file_path = data["image"].replace("/gradio_api/file=", "")
        assert Path(file_path).exists()

    def test_accepts_path_object(self, editor: TrimapEditor, sample_image: Path) -> None:
        result = editor.postprocess(sample_image)
        assert result is not None
        data = json.loads(result)
        assert data["width"] == 200
        assert data["height"] == 150


class TestPostprocessTuple:
    """Tests for (image, trimap) tuple input to postprocess()."""

    @pytest.fixture
    def sample_trimap(self, tmp_path: Path) -> Path:
        """Create a simple trimap PNG with 0/128/255 values."""
        trimap = Image.new("L", (200, 150), 0)
        # Paint a central unknown region
        for y in range(50, 100):
            for x in range(50, 150):
                trimap.putpixel((x, y), 128)
        # Paint a smaller foreground region inside
        for y in range(60, 90):
            for x in range(70, 130):
                trimap.putpixel((x, y), 255)
        p = tmp_path / "trimap.png"
        trimap.save(p)
        return p

    def test_tuple_with_trimap_has_trimap_key(
        self, editor: TrimapEditor, sample_image: Path, sample_trimap: Path
    ) -> None:
        result = editor.postprocess((sample_image, sample_trimap))
        data = json.loads(result)
        assert "trimap" in data
        assert "image" in data
        assert "width" in data
        assert "height" in data

    def test_tuple_with_none_trimap_no_trimap_key(self, editor: TrimapEditor, sample_image: Path) -> None:
        result = editor.postprocess((sample_image, None))
        data = json.loads(result)
        assert "trimap" not in data
        assert "image" in data

    def test_list_works_same_as_tuple(self, editor: TrimapEditor, sample_image: Path, sample_trimap: Path) -> None:
        result = editor.postprocess([sample_image, sample_trimap])
        data = json.loads(result)
        assert "trimap" in data
        assert "image" in data

    def test_trimap_url_is_gradio_api_file(
        self, editor: TrimapEditor, sample_image: Path, sample_trimap: Path
    ) -> None:
        result = editor.postprocess((sample_image, sample_trimap))
        data = json.loads(result)
        assert data["trimap"].startswith("/gradio_api/file=")

    def test_trimap_cached_file_exists(self, editor: TrimapEditor, sample_image: Path, sample_trimap: Path) -> None:
        result = editor.postprocess((sample_image, sample_trimap))
        data = json.loads(result)
        file_path = data["trimap"].replace("/gradio_api/file=", "")
        assert Path(file_path).exists()

    def test_trimap_cached_as_png(self, editor: TrimapEditor, sample_image: Path, sample_trimap: Path) -> None:
        result = editor.postprocess((sample_image, sample_trimap))
        data = json.loads(result)
        file_path = data["trimap"].replace("/gradio_api/file=", "")
        cached_img = Image.open(file_path)
        assert cached_img.format == "PNG"

    def test_trimap_pixel_values_preserved(
        self, editor: TrimapEditor, sample_image: Path, sample_trimap: Path
    ) -> None:
        result = editor.postprocess((sample_image, sample_trimap))
        data = json.loads(result)
        file_path = data["trimap"].replace("/gradio_api/file=", "")
        cached_img = Image.open(file_path).convert("L")
        pixels = set(cached_img.tobytes())
        assert pixels == {0, 128, 255}

    def test_dimensions_match_image(self, editor: TrimapEditor, sample_image: Path, sample_trimap: Path) -> None:
        result = editor.postprocess((sample_image, sample_trimap))
        data = json.loads(result)
        assert data["width"] == 200
        assert data["height"] == 150

    def test_pil_image_trimap_input(self, editor: TrimapEditor) -> None:
        img = Image.new("RGB", (100, 80))
        trimap = Image.new("L", (100, 80), 128)
        result = editor.postprocess((img, trimap))
        data = json.loads(result)
        assert "trimap" in data

    def test_single_element_list(self, editor: TrimapEditor, sample_image: Path) -> None:
        """A single-element list [image] should be treated as image-only (no trimap)."""
        result = editor.postprocess([str(sample_image)])
        data = json.loads(result)
        assert "image" in data
        assert "trimap" not in data
        assert data["width"] == 200

    def test_single_element_tuple(self, editor: TrimapEditor) -> None:
        """A single-element tuple (image,) should be treated as image-only."""
        img = Image.new("RGB", (100, 80))
        result = editor.postprocess((img,))
        data = json.loads(result)
        assert "image" in data
        assert "trimap" not in data


class TestProcessExample:
    def test_returns_none_for_none(self, editor: TrimapEditor) -> None:
        assert editor.process_example(None) is None

    def test_returns_img_tag_for_pil_image(self, editor: TrimapEditor) -> None:
        img = Image.new("RGB", (100, 80))
        result = editor.process_example(img)
        assert result is not None
        assert "<img" in result
        assert "src=" in result

    def test_returns_img_tag_for_file_path(self, editor: TrimapEditor, sample_image: Path) -> None:
        result = editor.process_example(str(sample_image))
        assert result is not None
        assert "<img" in result

    def test_img_tag_has_max_height(self, editor: TrimapEditor) -> None:
        img = Image.new("RGB", (100, 80))
        result = editor.process_example(img)
        assert "max-height:5rem" in result

    def test_img_tag_has_object_fit_contain(self, editor: TrimapEditor) -> None:
        img = Image.new("RGB", (100, 80))
        result = editor.process_example(img)
        assert "object-fit:contain" in result

    def test_handles_list_input(self, editor: TrimapEditor, sample_image: Path) -> None:
        result = editor.process_example([str(sample_image)])
        assert result is not None
        assert "<img" in result

    def test_handles_tuple_with_trimap(self, editor: TrimapEditor, sample_image: Path) -> None:
        """process_example with (image, trimap) tuple shows both image and trimap."""
        trimap = Image.new("L", (200, 150), 128)
        result = editor.process_example([str(sample_image), trimap])
        assert result is not None
        # Should contain two img tags (image + trimap) in a flex container
        assert result.count("<img") == 2
        assert 'alt="image"' in result
        assert 'alt="trimap"' in result

    def test_tuple_without_trimap_shows_single_image(self, editor: TrimapEditor, sample_image: Path) -> None:
        """process_example with (image, None) shows only the image."""
        result = editor.process_example([str(sample_image), None])
        assert result is not None
        assert result.count("<img") == 1

    def test_not_raw_json(self, editor: TrimapEditor) -> None:
        img = Image.new("RGB", (100, 80))
        result = editor.process_example(img)
        # Should not return raw JSON string
        assert not result.startswith("{")


class TestApiInfo:
    def test_returns_dict(self, editor: TrimapEditor) -> None:
        info = editor.api_info()
        assert isinstance(info, dict)

    def test_has_type_field(self, editor: TrimapEditor) -> None:
        info = editor.api_info()
        assert "type" in info
        assert info["type"] == "string"

    def test_has_description_field(self, editor: TrimapEditor) -> None:
        info = editor.api_info()
        assert "description" in info
        assert isinstance(info["description"], str)
        assert len(info["description"]) > 10

    def test_description_mentions_trimap_base64(self, editor: TrimapEditor) -> None:
        # The output payload uses trimapBase64 (data URI), not trimapPath.
        info = editor.api_info()
        assert "trimapBase64" in info["description"]

    def test_description_mentions_trimap_input(self, editor: TrimapEditor) -> None:
        # Input direction now supports optional trimap key.
        info = editor.api_info()
        assert "trimap?" in info["description"] or "trimap" in info["description"]
