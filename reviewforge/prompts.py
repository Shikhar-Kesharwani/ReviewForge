"""
reviewforge/prompts.py

Shared prompt string constants used throughout ReviewForge when communicating
with LLMs.  Centralising them here makes it easy to tweak wording in one place
without hunting through the codebase.
"""

# ---------------------------------------------------------------------------
# Conversation summarisation
# ---------------------------------------------------------------------------

#: System prompt sent to the LLM when we ask it to summarise a conversation.
summarize: str = (
    "You are a helpful assistant. Summarize the following conversation, "
    "keeping all the important technical details, file names, code changes, "
    "and decisions made. Be concise but complete."
)

#: Prefix inserted at the top of every generated summary block so it is easy
#: to detect and parse later.
summary_prefix: str = "<summary>\nI spoke with the user and made these changes:\n"

# ---------------------------------------------------------------------------
# System prompt helpers
# ---------------------------------------------------------------------------

#: Short reminder appended to the end of system prompts so the model stays
#: on-format even after long conversations.
system_reminder: str = (
    "IMPORTANT: Follow the format instructions exactly. "
    "Only return code in the specified format."
)

# ---------------------------------------------------------------------------
# Repository / file context blocks
# ---------------------------------------------------------------------------

#: Header printed before the repo-map section that is injected into the
#: system prompt.
repo_content_prefix: str = "Here is a map of the repository:\n"

#: Header printed before the block of editable file contents.
files_content_prefix: str = "Here are the contents of the files you can edit:\n"

#: Placeholder used when ReviewForge has *not* yet shared any file contents
#: with the model (e.g. at the very start of a session).
files_no_full_files: str = "I am not sharing any file contents yet."

#: Assistant-role acknowledgement message inserted after the file-contents
#: block so the conversation history looks natural to the model.
files_content_assistant_reply: str = (
    "Ok, I will use that context to help with your request."
)

#: Header printed before any read-only reference files that the model should
#: use for context but must not attempt to edit.
read_only_files_prefix: str = (
    "Here are some read-only files for context (do NOT edit these):\n"
)

# ---------------------------------------------------------------------------
# Shell command prompts
# ---------------------------------------------------------------------------

#: Prompt displayed to the user when the LLM suggests a shell command and we
#: want to ask whether to run it.
shell_cmd_prompt: str = (
    "The assistant suggested the following shell command.\n"
    "Do you want ReviewForge to run it?  [y/N] "
)

#: Reminder embedded in the system prompt so the model uses the correct format
#: when suggesting shell commands.
shell_cmd_reminder: str = (
    "When you want to suggest a shell command for the user to run, wrap it in "
    "a fenced code block tagged with the language 'sh', for example:\n"
    "```sh\n"
    "your command here\n"
    "```\n"
    "Only suggest one command at a time."
)
