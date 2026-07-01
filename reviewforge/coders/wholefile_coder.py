import re
from reviewforge.coders.base_coder import Coder
from reviewforge.coders.wholefile_prompts import WholeFilePrompts
from reviewforge.coders.search_replace import find_filename

class WholeFileCoder(Coder):
    edit_format = 'whole'
    gpt_prompts = WholeFilePrompts()

    def get_edits(self, mode='update'):
        content = self.partial_response_content
        edits = []
        
        # Regex to find a filename line followed by a code fence containing the entire file
        pattern = re.compile(
            r'([^\n]+)\n```[a-zA-Z0-9-]*\n(.*?)```',
            re.DOTALL | re.MULTILINE
        )
        
        for match in pattern.finditer(content):
            preceding_line = match.group(1).strip()
            new_content = match.group(2)
            
            fname = find_filename([preceding_line], [f for f in self.abs_fnames], match.group(0))
            if fname:
                edits.append((fname, None, new_content))
                
        return edits

    def apply_edits(self, edits):
        modified_fnames = set()
        for fname, _, new_content in edits:
            abs_fname = self.abs_root_path(fname)
            self.abs_fnames.add(abs_fname)
            
            if not self.dry_run:
                try:
                    with open(abs_fname, "w", encoding=self.encoding) as f:
                        f.write(new_content)
                except Exception as e:
                    self.io.tool_error(f"Error writing to {abs_fname}: {e}")
                    continue
                    
            modified_fnames.add(abs_fname)
            
        return modified_fnames
