import os
from reviewforge.coders.base_coder import SwitchCoder
from reviewforge.utils import safe_abs_path

class Commands:
    def __init__(self, io, coder, voice_language=None, voice_input_device=None, voice_format='wav', 
                 verify_ssl=True, args=None, parser=None, verbose=False, editor=None, 
                 original_read_only_fnames=None):
        self.io = io
        self.coder = coder
        self.args = args
        self.parser = parser
        self.verbose = verbose
        self.editor = editor

    def get_commands(self):
        cmds = []
        for attr in dir(self):
            if attr.startswith("cmd_"):
                cmds.append(f"/{attr[4:]}")
        return cmds

    def run(self, inp):
        inp = inp.strip()
        if not inp:
            return
            
        if inp.startswith("!"):
            cmd_name = "run"
            args = inp[1:]
        else:
            parts = inp.split(maxsplit=1)
            cmd_name = parts[0][1:]
            args = parts[1] if len(parts) > 1 else ""
            
        method_name = f"cmd_{cmd_name}"
        if hasattr(self, method_name):
            try:
                getattr(self, method_name)(args)
            except Exception as e:
                if isinstance(e, SwitchCoder):
                    raise
                self.io.tool_error(f"Error running command: {e}")
                import traceback
                traceback.print_exc()
        else:
            self.io.tool_error(f"Unknown command: {cmd_name}")

    def cmd_add(self, args):
        if not args:
            self.io.tool_output("Added files:")
            for f in self.coder.get_rel_fnames():
                self.io.tool_output(f"  {f}")
            return
            
        import glob
        for pattern in args.split():
            matches = glob.glob(self.coder.abs_root_path(pattern), recursive=True)
            if not matches:
                self.io.tool_warning(f"No files matched '{pattern}'")
            for m in matches:
                if os.path.isfile(m):
                    self.coder.add_rel_fname(os.path.relpath(m, self.coder.root))
                    self.io.tool_output(f"Added {m} to the chat")

    def cmd_drop(self, args):
        if not args:
            self.coder.abs_fnames.clear()
            self.io.tool_output("Dropped all files from the chat")
            return
            
        for fname in args.split():
            self.coder.drop_rel_fname(fname)
            self.io.tool_output(f"Dropped {fname} from the chat")

    def cmd_ls(self, args):
        self.io.tool_output("Files in chat:")
        for f in self.coder.get_rel_fnames():
            self.io.tool_output(f"  {f}")
        
        self.io.tool_output("\nRead-only files:")
        for f in self.coder.abs_read_only_fnames:
            rel = os.path.relpath(f, self.coder.root)
            self.io.tool_output(f"  {rel}")

    def cmd_clear(self, args):
        self.coder.done_messages = []
        self.coder.cur_messages = []
        self.io.tool_output("Chat history cleared.")

    def cmd_reset(self, args):
        self.cmd_clear("")
        self.cmd_drop("")

    def cmd_commit(self, args):
        if not self.coder.repo:
            self.io.tool_error("No git repository found.")
            return
        
        msg = args if args else None
        res = self.coder.repo.commit(message=msg)
        if res:
            self.io.tool_output(f"Committed changes as {res[:7]}")
        else:
            self.io.tool_output("No changes to commit.")

    def cmd_undo(self, args):
        if not self.coder.repo:
            self.io.tool_error("No git repository found.")
            return
        
        if self.coder.repo.undo_last_commit():
            self.io.tool_output("Undid last commit.")

    def cmd_run(self, args):
        if not args:
            self.io.tool_error("Please provide a command to run.")
            return
            
        from reviewforge.run_cmd import run_cmd
        self.io.tool_output(f"Running: {args}")
        ret, out = run_cmd(args, cwd=self.coder.root, verbose=True)
        
        self.io.tool_output(f"Command exited with {ret}")
        
        msg = f"I ran this command:\n```bash\n{args}\n```\n"
        if out:
            msg += f"Output:\n```\n{out}\n```\n"
        else:
            msg += "Output: (no output)\n"
            
        if ret != 0:
            msg += f"Exit code: {ret}\n"
            
        self.coder.cur_messages.append({"role": "user", "content": msg})

    def cmd_exit(self, args):
        raise EOFError()
        
    def cmd_quit(self, args):
        self.cmd_exit(args)

    def cmd_model(self, args):
        if not args:
            self.io.tool_output(f"Current main model: {self.coder.main_model.name}")
            return
            
        from reviewforge.models import Model
        new_model = Model(args.strip())
        raise SwitchCoder(main_model=new_model)
        
    def cmd_chat_mode(self, args):
        if not args:
            self.io.tool_output(f"Current chat mode: {self.coder.edit_format}")
            return
        
        mode = args.strip()
        raise SwitchCoder(edit_format=mode)
