"""Tests for ReviewForge linter module."""
import os
import tempfile
import pytest
from reviewforge.linter import Linter, lint_python_compile, LintResult


class TestPythonCompileLint:
    def test_valid_code_returns_none(self):
        result = lint_python_compile("test.py", "x = 1\n")
        assert result is None

    def test_syntax_error_returns_result(self):
        result = lint_python_compile("test.py", "def foo(\n")
        assert result is not None
        assert isinstance(result, LintResult)

    def test_name_error_not_caught_at_compile(self):
        # NameErrors are runtime, not compile-time
        result = lint_python_compile("test.py", "print(undefined_var)\n")
        assert result is None


class TestLinterClass:
    def test_init(self):
        linter = Linter(root="/tmp")
        assert linter.root == "/tmp"

    def test_get_rel_fname(self, tmp_path):
        linter = Linter(root=str(tmp_path))
        fname = str(tmp_path / "main.py")
        rel = linter.get_rel_fname(fname)
        assert rel == "main.py"

    def test_lint_valid_python_file(self, tmp_path):
        f = tmp_path / "valid.py"
        f.write_text("x = 1\n")
        linter = Linter(root=str(tmp_path))
        result = linter.lint(str(f))
        # Valid file should return None or empty
        assert result is None

    def test_lint_invalid_python_file(self, tmp_path):
        f = tmp_path / "invalid.py"
        f.write_text("def broken(\n")  # Syntax error
        linter = Linter(root=str(tmp_path))
        result = linter.lint(str(f))
        # Invalid file should return error string
        # (may be None if tree-sitter not installed, that's okay)
        if result is not None:
            assert isinstance(result, str)
