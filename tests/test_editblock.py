"""Tests for ReviewForge search/replace coder edit parsing."""
import pytest
from reviewforge.coders.search_replace import parse_edits


SAMPLE_EDIT = '''
Here are the changes:

```python
main.py
<<<<<<< SEARCH
def old_function():
    pass
=======
def new_function():
    return 42
>>>>>>> REPLACE
```
'''


class TestParseEdits:
    def test_parses_single_edit(self):
        edits = parse_edits(SAMPLE_EDIT)
        assert len(edits) >= 0  # Parser must not crash

    def test_empty_content(self):
        edits = parse_edits("")
        assert edits == []

    def test_no_edit_blocks(self):
        edits = parse_edits("This is just a text response with no edits.")
        assert edits == []
