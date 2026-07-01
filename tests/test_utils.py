"""Tests for ReviewForge utilities and core helpers."""
import pytest
from reviewforge.utils import is_image_file, hash_text, safe_abs_path, format_content


class TestIsImageFile:
    def test_png_is_image(self):
        assert is_image_file("photo.png") is True

    def test_jpg_is_image(self):
        assert is_image_file("photo.jpg") is True

    def test_jpeg_is_image(self):
        assert is_image_file("photo.jpeg") is True

    def test_gif_is_image(self):
        assert is_image_file("photo.gif") is True

    def test_webp_is_image(self):
        assert is_image_file("photo.webp") is True

    def test_py_is_not_image(self):
        assert is_image_file("script.py") is False

    def test_txt_is_not_image(self):
        assert is_image_file("readme.txt") is False

    def test_case_insensitive(self):
        assert is_image_file("photo.PNG") is True


class TestHashText:
    def test_returns_string(self):
        result = hash_text("hello world")
        assert isinstance(result, str)

    def test_same_input_same_hash(self):
        assert hash_text("test") == hash_text("test")

    def test_different_input_different_hash(self):
        assert hash_text("foo") != hash_text("bar")

    def test_empty_string(self):
        result = hash_text("")
        assert isinstance(result, str)
        assert len(result) > 0


class TestSafeAbsPath:
    def test_returns_string(self, tmp_path):
        result = safe_abs_path(str(tmp_path))
        assert isinstance(result, str)

    def test_returns_absolute(self, tmp_path):
        import os
        result = safe_abs_path(str(tmp_path))
        assert os.path.isabs(result)


class TestFormatContent:
    def test_user_message(self):
        result = format_content("user", "hello")
        assert "user" in result.lower() or "hello" in result

    def test_assistant_message(self):
        result = format_content("assistant", "response")
        assert "assistant" in result.lower() or "response" in result
