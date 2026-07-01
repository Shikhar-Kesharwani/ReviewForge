from reviewforge.coders.base_coder import Coder
from reviewforge.coders.ask_prompts import AskPrompts

class AskCoder(Coder):
    edit_format = 'ask'
    gpt_prompts = AskPrompts()

    def get_edits(self, mode='update'):
        return []

    def apply_edits(self, edits):
        return set()
