from reviewforge.coders.base_coder import Coder
from reviewforge.coders.architect_prompts import ArchitectPrompts

class ArchitectCoder(Coder):
    edit_format = 'architect'
    gpt_prompts = ArchitectPrompts()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Create the editor subcoder that will actually apply edits
        editor_format = self.main_model.editor_edit_format or 'editor-diff'
        editor_model = self.main_model.editor_model or self.main_model
        self.editor = self.clone(main_model=editor_model, edit_format=editor_format)

    def get_edits(self, mode='update'):
        return []

    def apply_edits(self, edits):
        return set()

    def send_message(self, inp):
        # Override send_message to run architect, then pass response to editor
        super().send_message(inp)
        
        architect_response = self.partial_response_content
        if not architect_response:
            return
            
        # Add the architect's output to the editor's context
        self.io.tool_output("Architect has designed the solution. Handing off to editor...")
        editor_prompt = f"Please implement the following changes:\n\n{architect_response}"
        
        # We need to manually sync file lists
        self.editor.abs_fnames = self.abs_fnames
        self.editor.abs_read_only_fnames = self.abs_read_only_fnames
        
        self.editor.send_message(editor_prompt)
        
        # Sync back the edited files
        self.abs_fnames = self.editor.abs_fnames
