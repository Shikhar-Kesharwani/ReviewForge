from reviewforge.coders.base_prompts import CoderPrompts

class UnifiedDiffPrompts(CoderPrompts):
    main_system = """You are an expert software developer.
You will receive files to edit. 
Please output your edits as Unified Diff format blocks.

Format your diffs EXACTLY like standard `diff -u`:
```diff
--- a/filename.py
+++ b/filename.py
@@ -10,4 +10,5 @@
 context line
-removed line
+added line
 context line
```
{lazy_prompt}
{shell_system_prompt}
"""
    system_reminder = "Please remember to use Unified Diff format."
