import os
import sys
from abc import ABC, abstractmethod
from typing import List, Optional, Set

from reviewforge.coders.base_prompts import CoderPrompts
from reviewforge.coders.chat_chunks import ChatChunks
from reviewforge.coders.shell import find_shell_cmds
from reviewforge.history import ChatSummary
from reviewforge.utils import format_messages

class UnknownEditFormat(Exception):
    pass

class SwitchCoder(Exception):
    def __init__(self, placeholder=None, **kwargs):
        self.kwargs = kwargs
        self.placeholder = placeholder

class Coder(ABC):
    abs_fnames: set
    abs_read_only_fnames: set
    repo: object
    main_model: object
    edit_format: str
    gpt_prompts: CoderPrompts

    @classmethod
    def create(cls, main_model, edit_format, io, **kwargs):
        # Local import to prevent circular dependencies
        from reviewforge.coders import (
            EditBlockCoder, EditBlockFencedCoder, WholeFileCoder,
            UnifiedDiffCoder, UnifiedDiffSimpleCoder, ArchitectCoder,
            AskCoder, HelpCoder, ContextCoder, EditorEditBlockCoder,
            EditorWholeFileCoder, EditorDiffFencedCoder
        )
        
        EDIT_FORMAT_TO_CODER = {
            'diff': EditBlockCoder,
            'diff-fenced': EditBlockFencedCoder,
            'whole': WholeFileCoder,
            'udiff': UnifiedDiffCoder,
            'udiff-simple': UnifiedDiffSimpleCoder,
            'architect': ArchitectCoder,
            'ask': AskCoder,
            'help': HelpCoder,
            'context': ContextCoder,
            'editor-diff': EditorEditBlockCoder,
            'editor-whole': EditorWholeFileCoder,
            'editor-diff-fenced': EditorDiffFencedCoder,
        }

        if edit_format not in EDIT_FORMAT_TO_CODER:
            raise UnknownEditFormat(f"Unknown edit format: {edit_format}")
            
        coder_class = EDIT_FORMAT_TO_CODER[edit_format]
        return coder_class(main_model=main_model, io=io, edit_format=edit_format, **kwargs)

    def __init__(self, main_model, io, edit_format, fnames=None, read_only_fnames=None, 
                 repo=None, auto_commits=True, dirty_commits=True, auto_lint=False, 
                 auto_test=False, test_cmd=None, lint_cmds=None, stream=True, 
                 verbose=False, dry_run=False, map_tokens=1024, map_refresh='auto', 
                 restore_chat_history=False, max_chat_history_tokens=None, 
                 suggest_shell_commands=True, detect_urls=True, encoding='utf-8', **kwargs):
                 
        self.io = io
        self.main_model = main_model
        self.edit_format = edit_format
        self.repo = repo
        self.auto_commits = auto_commits
        self.dirty_commits = dirty_commits
        self.auto_lint = auto_lint
        self.auto_test = auto_test
        self.test_cmd = test_cmd
        self.lint_cmds = lint_cmds
        self.stream = stream
        self.verbose = verbose
        self.dry_run = dry_run
        self.map_tokens = map_tokens
        self.map_refresh = map_refresh
        self.suggest_shell_commands = suggest_shell_commands
        self.detect_urls = detect_urls
        self.encoding = encoding
        
        self.root = self.repo.root if self.repo else os.getcwd()
        
        self.abs_fnames = set(os.path.abspath(f) for f in (fnames or []))
        self.abs_read_only_fnames = set(os.path.abspath(f) for f in (read_only_fnames or []))
        
        self.done_messages = []
        self.cur_messages = []
        self.aider_commit_hashes = set()
        
        if max_chat_history_tokens is None:
            max_chat_history_tokens = self.main_model.max_context_tokens // 4
        self.summarizer = ChatSummary(self.main_model.commit_message_models(), max_chat_history_tokens)
        
        self.repo_map = None
        if self.repo and self.map_tokens > 0:
            try:
                from reviewforge.repomap import RepoMap
                self.repo_map = RepoMap(map_tokens=self.map_tokens, root=self.root, 
                                      main_model=self.main_model, io=self.io,
                                      repo_content_prefix=self.gpt_prompts.repo_content_prefix)
            except ImportError:
                pass
                
        # self.linter will be set up lazily when needed
        self.linter = None
        
        # Local import to prevent circular dependency
        from reviewforge.commands import Commands
        self.commands = Commands(self.io, self)

    def run(self, with_message=None):
        while True:
            try:
                if with_message:
                    inp = with_message
                    with_message = None
                else:
                    inp = self.io.get_input(
                        self.root, self.get_rel_fnames(), 
                        self.get_addable_rel_fnames(), self.commands,
                        self.abs_read_only_fnames, self.edit_format
                    )
                    
                if not inp:
                    continue
                    
                if inp.strip().startswith('/'):
                    self.commands.run(inp)
                else:
                    self.send_message(inp)
            except SwitchCoder as switch:
                raise
            except KeyboardInterrupt:
                self.io.tool_warning('Interrupted.')
                break
            except EOFError:
                break

    def send_message(self, inp):
        self.cur_messages.append({"role": "user", "content": inp})
        self.summarize_start()
        
        retries = 0
        max_retries = 3 if (self.auto_lint or self.auto_test) else 0
        
        while retries <= max_retries:
            messages = self.format_messages()
            
            try:
                response = self.main_model.send_with_retries(messages, stream=self.stream)
                
                content = ""
                if self.stream:
                    for chunk in response:
                        if chunk.choices and chunk.choices[0].delta.content:
                            text = chunk.choices[0].delta.content
                            content += text
                            self.io.render_incremental_response(content, final=False)
                    self.io.render_incremental_response(content, final=True)
                else:
                    content = response.choices[0].message.content
                    self.io.assistant_output(content)
                    
                self.cur_messages.append({"role": "assistant", "content": content})
                
                # Check for edits
                self.partial_response_content = content
                edits = self.get_edits()
                if edits:
                    modified_fnames = self.apply_edits(edits)
                    if modified_fnames:
                        for fname in modified_fnames:
                            self.io.tool_output(f"Applied edit to {fname}")
                            
                        # Lint and Test reflection loop
                        errors = ""
                        if self.auto_lint:
                            from reviewforge.linter import Linter
                            if not self.linter:
                                self.linter = Linter(root=self.root)
                            for fname in modified_fnames:
                                err = self.linter.lint(self.abs_root_path(fname))
                                if err:
                                    errors += f"Lint error in {fname}:\n{err}\n"
                        
                        if errors:
                            self.io.tool_error(errors)
                            self.cur_messages.append({"role": "user", "content": f"Please fix these errors:\n{errors}"})
                            retries += 1
                            continue
                            
                        if self.repo and self.auto_commits:
                            self.repo.commit(fnames=modified_fnames, context=inp, coder=self, aider_edits=True)
                
                if self.suggest_shell_commands:
                    cmds = find_shell_cmds(content)
                    if cmds:
                        self.io.tool_output("Suggested shell commands:")
                        for cmd in cmds:
                            self.io.tool_output(f"  {cmd}")
                            
                break # Success, break retry loop
                
            except Exception as e:
                self.io.tool_error(f"Error communicating with LLM: {e}")
                import traceback
                traceback.print_exc()
                break

    def format_messages(self):
        chunks = ChatChunks()
        chunks.system.append({"role": "system", "content": self.get_system_prompt()})
        
        if hasattr(self.gpt_prompts, 'example_messages'):
            chunks.examples = list(self.gpt_prompts.example_messages)
            
        chunks.done = list(self.done_messages)
        
        repo_map = self.get_repo_map()
        if repo_map:
            chunks.repo.append({"role": "user", "content": repo_map})
            
        readonly_content = self.get_read_only_content()
        if readonly_content:
            chunks.readonly.append({"role": "user", "content": readonly_content})
            
        files_content = self.get_files_content()
        if files_content:
            chunks.files.append({"role": "user", "content": files_content})
            chunks.files.append({"role": "assistant", "content": self.gpt_prompts.files_content_assistant_reply})
        else:
            chunks.files.append({"role": "user", "content": self.gpt_prompts.files_no_full_files})
            
        chunks.cur = list(self.cur_messages)
        if chunks.cur and chunks.cur[-1]["role"] == "user":
            chunks.cur[-1]["content"] += f"\n\n{self.gpt_prompts.system_reminder}"
            
        return chunks.get_llm_messages()

    @abstractmethod
    def get_edits(self, mode='update'):
        pass

    @abstractmethod
    def apply_edits(self, edits):
        pass

    def get_system_prompt(self):
        prompt = self.gpt_prompts.main_system
        prompt = prompt.replace('{lazy_prompt}', self.gpt_prompts.lazy_prompt)
        prompt = prompt.replace('{shell_system_prompt}', self.gpt_prompts.shell_system_prompt if self.suggest_shell_commands else '')
        return prompt

    def get_repo_map(self):
        if not self.repo_map:
            return ""
        return self.repo_map.get_repo_map(self.abs_fnames, self.abs_read_only_fnames)

    def get_files_content(self, fnames=None):
        if fnames is None:
            fnames = self.abs_fnames
        if not fnames:
            return ""
            
        content = self.gpt_prompts.files_content_prefix + "\n"
        for fname in fnames:
            try:
                with open(fname, "r", encoding=self.encoding) as f:
                    file_content = f.read()
                rel_fname = os.path.relpath(fname, self.root)
                content += f"```\n{rel_fname}\n{file_content}\n```\n"
            except Exception as e:
                self.io.tool_warning(f"Could not read {fname}: {e}")
        return content

    def get_read_only_content(self):
        if not self.abs_read_only_fnames:
            return ""
        content = self.gpt_prompts.read_only_files_prefix + "\n"
        for fname in self.abs_read_only_fnames:
            try:
                with open(fname, "r", encoding=self.encoding) as f:
                    file_content = f.read()
                rel_fname = os.path.relpath(fname, self.root)
                content += f"```\n{rel_fname}\n{file_content}\n```\n"
            except Exception:
                pass
        return content

    def abs_root_path(self, path):
        return os.path.abspath(os.path.join(self.root, path))

    def get_rel_fnames(self):
        return sorted([os.path.relpath(f, self.root) for f in self.abs_fnames])
        
    def get_inchat_relative_files(self):
        return self.get_rel_fnames()

    def get_addable_rel_fnames(self):
        if not self.repo:
            return []
        tracked = self.repo.get_tracked_files()
        in_chat = set(self.get_rel_fnames())
        return sorted(list(tracked - in_chat))

    def add_rel_fname(self, rel_fname):
        abs_fname = self.abs_root_path(rel_fname)
        self.abs_fnames.add(abs_fname)

    def drop_rel_fname(self, rel_fname):
        abs_fname = self.abs_root_path(rel_fname)
        if abs_fname in self.abs_fnames:
            self.abs_fnames.remove(abs_fname)

    def allowed_to_edit(self, path):
        return os.path.abspath(path) in self.abs_fnames

    def get_context_from_history(self, messages):
        return "\n".join(m["content"] for m in messages if isinstance(m, dict) and "content" in m)

    def summarize_start(self):
        if self.summarizer.too_big(self.done_messages):
            self.done_messages = self.summarizer.summarize(self.done_messages)

    def move_back_cur_messages(self, message):
        self.done_messages.extend(self.cur_messages)
        self.cur_messages = []
        if message:
            self.done_messages.append({"role": "assistant", "content": message})

    def get_announcements(self):
        anns = []
        anns.append(f"Model: {self.main_model.name} with {self.edit_format} format")
        if self.repo:
            anns.append(f"Git repo: {self.root}")
        return anns

    def clone(self, **kwargs):
        new_kwargs = {
            'main_model': self.main_model,
            'io': self.io,
            'edit_format': self.edit_format,
            'fnames': list(self.abs_fnames),
            'read_only_fnames': list(self.abs_read_only_fnames),
            'repo': self.repo,
        }
        new_kwargs.update(kwargs)
        return Coder.create(**new_kwargs)

    def check_for_urls(self, content):
        if not self.detect_urls:
            return
        pass # URL extraction and scraping could be added here
