import os
from pathlib import Path
import pathspec
import git

ANY_GIT_ERROR = (git.GitCommandError, git.GitCommandNotFound, git.InvalidGitRepositoryError, git.NoSuchPathError)

class GitRepo:
    def __init__(self, io, fnames=None, git_dname=None, models=None, attribute_author=True, 
                 attribute_committer=True, attribute_commit_message=False, commit_prompt=None, 
                 subtree_only=False, git_commit_verify=False):
        self.io = io
        self.models = models
        self.repo = None
        self.root = None
        self.attribute_author = attribute_author
        self.attribute_committer = attribute_committer
        self.attribute_commit_message = attribute_commit_message
        self.commit_prompt = commit_prompt
        self.subtree_only = subtree_only
        self.git_commit_verify = git_commit_verify
        
        search_path = git_dname
        if not search_path and fnames:
            search_path = os.path.dirname(os.path.abspath(fnames[0]))
        if not search_path:
            search_path = os.getcwd()
            
        try:
            self.repo = git.Repo(search_path, search_parent_directories=True)
            self.root = self.repo.working_tree_dir
        except ANY_GIT_ERROR:
            pass

        self.ignore_spec = self.get_aiderignore_spec()
        if self.repo:
            self.check_gitignore(self.root, io)

    def get_tracked_files(self):
        if not self.repo:
            return set()
        try:
            tracked = self.repo.git.ls_files().splitlines()
            return {f for f in tracked if not self.ignored_file(f)}
        except ANY_GIT_ERROR:
            return set()

    def get_dirty_files(self):
        if not self.repo:
            return []
        try:
            dirty = [item.a_path for item in self.repo.index.diff(None)]
            untracked = self.repo.untracked_files
            staged = [item.a_path for item in self.repo.index.diff("HEAD")]
            all_dirty = set(dirty + untracked + staged)
            return [f for f in all_dirty if not self.ignored_file(f)]
        except ANY_GIT_ERROR:
            return []

    def is_dirty(self):
        return len(self.get_dirty_files()) > 0

    def get_commit_message(self, diffs, context, models=None):
        if not models:
            models = self.models
        if not models or not diffs:
            return "Update"
        
        prompt = f"Please write a short, concise commit message for these changes:\n\n{diffs}"
        if context:
            prompt += f"\n\nContext:\n{context}"
            
        try:
            from reviewforge.sendchat import simple_send_with_retries
            messages = [{"role": "user", "content": prompt}]
            model = models[0] # Use weak model if available
            response = model.simple_send_with_retries(messages)
            return response.strip() if response else "Update"
        except Exception as e:
            self.io.tool_error(f"Error generating commit message: {e}")
            return "Update"

    def commit(self, fnames=None, context=None, message=None, aider_edits=False, coder=None):
        if not self.repo:
            return None
        try:
            if fnames:
                for f in fnames:
                    self.repo.git.add(f)
            else:
                self.repo.git.add(update=True)
                
            if not self.repo.index.diff("HEAD"):
                return None
                
            if not message:
                diffs = self.repo.git.diff("HEAD", cached=True)
                message = self.get_commit_message(diffs, context)
                
            if aider_edits and self.attribute_commit_message:
                message = f"reviewforge: {message}"
                
            kwargs = {"skip_hooks": not self.git_commit_verify}
            if aider_edits and self.attribute_author:
                kwargs["author"] = "reviewforge <reviewforge@ai>"
            
            commit_obj = self.repo.index.commit(message, **kwargs)
            
            if aider_edits and coder:
                if not hasattr(coder, 'aider_commit_hashes'):
                    coder.aider_commit_hashes = set()
                coder.aider_commit_hashes.add(commit_obj.hexsha)
                
            return commit_obj.hexsha
        except ANY_GIT_ERROR as e:
            self.io.tool_error(f"Git commit failed: {e}")
            return None

    def get_rel_repo_dir(self):
        if not self.root:
            return None
        return ".git"

    def get_head_commit(self):
        if not self.repo:
            return None
        try:
            return self.repo.head.commit
        except (ValueError, ANY_GIT_ERROR):
            return None

    def get_head_commit_sha(self, short=True):
        commit = self.get_head_commit()
        if not commit:
            return None
        return commit.hexsha[:7] if short else commit.hexsha

    def undo_last_commit(self):
        if not self.repo:
            return False
        try:
            self.repo.git.reset("HEAD~1")
            return True
        except ANY_GIT_ERROR as e:
            self.io.tool_error(f"Failed to undo commit: {e}")
            return False

    def diff_commits(self, pretty, from_commit, to_commit):
        if not self.repo:
            return ""
        try:
            return self.repo.git.diff(from_commit, to_commit, color="always" if pretty else "never")
        except ANY_GIT_ERROR:
            return ""

    def diff_dirty(self):
        if not self.repo:
            return ""
        try:
            return self.repo.git.diff("HEAD")
        except ANY_GIT_ERROR:
            return ""

    def path_in_repo(self, path):
        if not self.root:
            return False
        try:
            abs_path = os.path.abspath(path)
            return abs_path.startswith(os.path.abspath(self.root))
        except Exception:
            return False

    def abs_root_path(self, path):
        if not self.root:
            return os.path.abspath(path)
        return os.path.join(self.root, path)

    def ignored_file(self, fname):
        if not self.ignore_spec:
            return False
        try:
            rel = os.path.relpath(fname, self.root)
            return self.ignore_spec.match_file(rel)
        except Exception:
            return False

    def get_aiderignore_spec(self):
        spec_lines = []
        if self.root:
            ignore_path = os.path.join(self.root, ".reviewforgeignore")
            if os.path.exists(ignore_path):
                with open(ignore_path, "r", encoding="utf-8") as f:
                    spec_lines = f.readlines()
        return pathspec.PathSpec.from_lines(pathspec.patterns.GitWildMatchPattern, spec_lines)

    def check_gitignore(self, root, io):
        gitignore_path = os.path.join(root, ".gitignore")
        lines = []
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        
        has_tags = any(".reviewforge.tags.cache" in line for line in lines)
        has_chat = any(".reviewforge.chat.history.md" in line for line in lines)
        
        if not has_tags or not has_chat:
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write("\n# ReviewForge\n")
                if not has_tags:
                    f.write(".reviewforge.tags.cache.v3\n")
                if not has_chat:
                    f.write(".reviewforge.chat.history.md\n")
                    f.write(".reviewforge.input.history\n")
