import re
from reviewforge.coders.base_coder import Coder
from reviewforge.coders.udiff_prompts import UnifiedDiffPrompts

class UnifiedDiffCoder(Coder):
    edit_format = 'udiff'
    gpt_prompts = UnifiedDiffPrompts()

    def get_edits(self, mode='update'):
        content = self.partial_response_content
        edits = []
        
        # Regex to find unified diff blocks
        pattern = re.compile(
            r'```diff\n--- a/(.*?)\n\+\+\+ [^\n]+\n(.*?)\n```',
            re.DOTALL | re.MULTILINE
        )
        
        for match in pattern.finditer(content):
            fname = match.group(1).strip()
            diff_content = match.group(0) # Keep the whole diff block
            edits.append((fname, None, diff_content))
            
        return edits

    def apply_edits(self, edits):
        modified_fnames = set()
        for fname, _, diff_content in edits:
            abs_fname = self.abs_root_path(fname)
            self.abs_fnames.add(abs_fname)
            
            if not self.dry_run:
                try:
                    # In a real unified diff applier, we'd use diff_match_patch
                    # or an external patch command.
                    # For ReviewForge from-scratch, we'll try to use the patch utility
                    # or fallback to Python diff parsing
                    import subprocess
                    from reviewforge.run_cmd import run_cmd
                    
                    # Create a temp file for the patch
                    import tempfile
                    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".patch") as f:
                        f.write(diff_content.replace('```diff\n', '').replace('\n```', ''))
                        patch_file = f.name
                        
                    # Apply using patch command
                    cmd = f'patch -p1 < "{patch_file}"'
                    ret, out = run_cmd(cmd, cwd=self.root)
                    
                    import os
                    os.unlink(patch_file)
                    
                    if ret != 0:
                        self.io.tool_error(f"Failed to apply patch to {fname}:\n{out}")
                        continue
                except Exception as e:
                    self.io.tool_error(f"Error applying unified diff to {abs_fname}: {e}")
                    continue
                    
            modified_fnames.add(abs_fname)
            
        return modified_fnames
