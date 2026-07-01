from reviewforge.coders.base_coder import Coder
from reviewforge.coders.editblock_prompts import EditBlockPrompts
from reviewforge.coders.search_replace import parse_edits, apply_edits

class EditBlockCoder(Coder):
    edit_format = 'diff'
    gpt_prompts = EditBlockPrompts()

    def get_edits(self, mode='update'):
        content = self.partial_response_content
        return parse_edits(content)

    def apply_edits(self, edits):
        # Resolve filenames to absolute paths if they are relative
        resolved_edits = []
        for fname, search, replace in edits:
            abs_fname = self.abs_root_path(fname)
            self.abs_fnames.add(abs_fname)
            resolved_edits.append((abs_fname, search, replace))
            
        return apply_edits(resolved_edits, self.io, dry_run=self.dry_run)
