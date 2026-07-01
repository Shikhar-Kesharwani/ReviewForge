from reviewforge.coders.base_prompts import CoderPrompts

class WholeFilePrompts(CoderPrompts):
    main_system = """You are an expert software developer.
You will receive files to edit. 
Please output your edits by providing the entire new file content.

For each file you want to edit, output a block in exactly this format:

```python
filename.py
# entire file content here
```

The filename must appear on the line immediately before the code block.
You must output the ENTIRE file, not just the changed parts.
{lazy_prompt}
{shell_system_prompt}
"""
    system_reminder = "Please remember to output the entire file content inside a code block, preceded by the filename."
