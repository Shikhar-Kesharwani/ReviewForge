"""Tests for ReviewForge Models module."""
import pytest
from reviewforge.models import Model, MODEL_ALIASES, DEFAULT_MODEL_NAME


class TestModelAliases:
    def test_flash_alias_resolves(self):
        m = Model("flash")
        assert "gemini" in m.name

    def test_gemini_alias_resolves(self):
        m = Model("gemini")
        assert "gemini" in m.name

    def test_unknown_model_keeps_name(self):
        m = Model("custom/my-model")
        assert m.name == "custom/my-model"

    def test_default_model_name_exists(self):
        assert DEFAULT_MODEL_NAME is not None
        assert len(DEFAULT_MODEL_NAME) > 0

    def test_model_aliases_not_empty(self):
        assert len(MODEL_ALIASES) > 0


class TestModelClass:
    def test_model_str(self):
        m = Model("gemini/gemini-2.0-flash")
        assert "gemini" in str(m)

    def test_model_repr(self):
        m = Model("gemini/gemini-2.0-flash")
        assert "gemini" in repr(m)

    def test_commit_message_models_returns_list(self):
        m = Model("gemini/gemini-2.0-flash")
        result = m.commit_message_models()
        assert isinstance(result, list)
        assert len(result) > 0
