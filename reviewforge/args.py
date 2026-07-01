import os
import sys

def get_parser():
    import configargparse
    parser = configargparse.ArgumentParser(
        description="ReviewForge is AI pair programming in your terminal",
        add_config_file_help=True,
        default_config_files=[".reviewforge.conf.yml", os.path.expanduser("~/.reviewforge.conf.yml")],
        formatter_class=configargparse.ArgumentDefaultsHelpFormatter,
    )
    
    parser.add_argument("-c", "--config", is_config_file=True, help="Specify the config file")
    
    model_group = parser.add_argument_group("Model Settings")
    model_group.add_argument("--model", type=str, help="Specify the model to use for the main chat", default="gemini/gemini-2.0-flash")
    model_group.add_argument("--edit-format", type=str, help="Specify what edit format the LLM should use (default depends on model)")
    model_group.add_argument("--weak-model", type=str, help="Specify the model to use for commit messages and chat history summarization")
    model_group.add_argument("--editor-model", type=str, help="Specify the model to use for editor tasks")
    
    history_group = parser.add_argument_group("History Files")
    history_group.add_argument("--chat-history-file", type=str, default=".reviewforge.chat.history.md", help="Specify the chat history file to use")
    history_group.add_argument("--input-history-file", type=str, default=".reviewforge.input.history", help="Specify the input history file to use")
    history_group.add_argument("--llm-history-file", type=str, help="Log raw LLM messages to this file")
    history_group.add_argument("--restore-chat-history", action="store_true", default=False, help="Restore the previous chat history messages")
    
    output_group = parser.add_argument_group("Output Settings")
    output_group.add_argument("--dark-mode", action="store_true", help="Use colors suitable for a dark terminal background")
    output_group.add_argument("--light-mode", action="store_true", help="Use colors suitable for a light terminal background")
    output_group.add_argument("--pretty", action="store_true", default=True, help="Enable pretty, colorized output")
    output_group.add_argument("--no-pretty", action="store_false", dest="pretty", help="Disable pretty, colorized output")
    output_group.add_argument("--stream", action="store_true", default=True, help="Enable streaming responses")
    output_group.add_argument("--no-stream", action="store_false", dest="stream", help="Disable streaming responses")
    
    git_group = parser.add_argument_group("Git Settings")
    git_group.add_argument("--git", action="store_true", default=True, help="Enable git integration")
    git_group.add_argument("--no-git", action="store_false", dest="git", help="Disable git integration")
    git_group.add_argument("--auto-commits", action="store_true", default=True, help="Enable auto commit of LLM changes")
    git_group.add_argument("--no-auto-commits", action="store_false", dest="auto_commits", help="Disable auto commit of LLM changes")
    git_group.add_argument("--dirty-commits", action="store_true", default=True, help="Enable commits when repo is found dirty")
    git_group.add_argument("--no-dirty-commits", action="store_false", dest="dirty_commits", help="Disable commits when repo is found dirty")
    
    other_group = parser.add_argument_group("Other Settings")
    other_group.add_argument("--file", type=str, nargs="+", help="Files to add to the chat session")
    other_group.add_argument("--read", type=str, nargs="+", help="Files to add to the chat session as read-only")
    other_group.add_argument("--yes", "-y", action="store_true", help="Always say yes to every confirmation prompt")
    other_group.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    other_group.add_argument("--message", "-m", type=str, help="Specify a single message to send the LLM, print the response, then exit")
    
    return parser
