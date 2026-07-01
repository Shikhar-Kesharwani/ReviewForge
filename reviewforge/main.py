import os
import sys

from reviewforge.args import get_parser
from reviewforge.io import InputOutput
from reviewforge.models import Model
from reviewforge.repo import GitRepo
from reviewforge.coders.base_coder import Coder, SwitchCoder

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
        
    parser = get_parser()
    args = parser.parse_args(argv)
    
    io = InputOutput(
        pretty=args.pretty,
        yes=args.yes,
        chat_history_file=args.chat_history_file,
        input_history_file=args.input_history_file,
        llm_history_file=args.llm_history_file
    )
    
    # 1. Initialize Git Repo
    repo = None
    if args.git:
        fnames = args.file or []
        repo = GitRepo(io, fnames)
        
    # 2. Setup Models
    main_model = Model(args.model, weak_model=args.weak_model, editor_model=args.editor_model)
    
    # 3. Handle dirty repo
    if repo and repo.is_dirty() and args.dirty_commits:
        io.tool_output("Committing uncommitted changes before starting chat...")
        repo.commit(message="WIP: uncommitted changes before reviewforge chat")
        
    # 4. Initialize Coder
    kwargs = vars(args)
    kwargs['io'] = io
    kwargs['repo'] = repo
    kwargs['main_model'] = main_model
    kwargs['fnames'] = args.file or []
    kwargs['read_only_fnames'] = args.read or []
    
    # Resolve edit format
    if not args.edit_format:
        kwargs['edit_format'] = main_model.info.get('edit_format', 'diff')
        
    try:
        coder = Coder.create(**kwargs)
    except Exception as e:
        io.tool_error(f"Failed to initialize coder: {e}")
        return 1
        
    # Print announcements
    for msg in coder.get_announcements():
        io.tool_output(msg)
        
    if args.message:
        coder.run(with_message=args.message)
        return 0
        
    # Main chat loop with support for switching coders via commands (e.g. /architect)
    while True:
        try:
            coder.run()
            break # Normal exit
        except SwitchCoder as switch:
            # Recreate coder with new settings
            new_kwargs = kwargs.copy()
            new_kwargs.update(switch.kwargs)
            
            # Carry over state
            new_kwargs['fnames'] = list(coder.abs_fnames)
            new_kwargs['read_only_fnames'] = list(coder.abs_read_only_fnames)
            
            coder = Coder.create(**new_kwargs)
            io.tool_output(f"Switched to {coder.edit_format} mode.")
            if switch.placeholder:
                coder.run(with_message=switch.placeholder)

if __name__ == "__main__":
    sys.exit(main())
