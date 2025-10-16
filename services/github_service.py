"""GitHub service for repository management and GitHub Pages deployment."""
import os
import time
from typing import Dict, List, Optional
from github import Github, GithubException
from github.Repository import Repository
import base64


class GitHubService:
    """Service for interacting with GitHub API."""
    
    def __init__(self, token: str, username: str):
        """
        Initialize GitHub service.
        
        Args:
            token: GitHub Personal Access Token
            username: GitHub username
        """
        self.github = Github(token)
        self.username = username
        self.user = self.github.get_user()
    
    def repo_exists(self, repo_name: str) -> bool:
        """Check if repository exists."""
        try:
            self.user.get_repo(repo_name)
            return True
        except GithubException:
            return False
    
    def delete_repo(self, repo_name: str):
        """Delete a repository."""
        try:
            repo = self.user.get_repo(repo_name)
            repo.delete()
            # Wait a bit for deletion to complete
            time.sleep(2)
        except GithubException as e:
            if e.status != 404:
                raise
    
    def create_repo(self, repo_name: str, description: str = "Auto-generated project") -> Repository:
        """
        Create a new repository.
        
        Args:
            repo_name: Name of the repository
            description: Repository description
        
        Returns:
            Created repository object
        """
        repo = self.user.create_repo(
            name=repo_name,
            description=description,
            private=False,  # Always create public repos for evaluation
            auto_init=False
        )
        print(f"Created public repository: {repo_name}")
        return repo
    
    def get_repo(self, repo_name: str) -> Repository:
        """Get existing repository."""
        return self.user.get_repo(repo_name)
    
    def commit_files(
        self, 
        repo: Repository, 
        files: Dict[str, str], 
        message: str = "Auto-generated commit",
        branch: str = "main"
    ) -> str:
        """
        Commit multiple files to repository.
        
        Args:
            repo: Repository object
            files: Dictionary mapping filename to content
            message: Commit message
            branch: Branch name
        
        Returns:
            Commit SHA
        """
        # Check if repo is empty (no commits yet)
        try:
            repo.get_branch(branch)
            repo_empty = False
        except GithubException:
            repo_empty = True
        
        if repo_empty:
            # For empty repo, use create_file for the first file to initialize
            # then update the rest in a single commit
            from github import InputGitTreeElement
            
            # Create first file to initialize the repo
            first_filepath = list(files.keys())[0]
            first_content = files[first_filepath]
            
            if isinstance(first_content, bytes):
                first_content = first_content.decode('utf-8', errors='ignore')
            
            result = repo.create_file(
                first_filepath,
                message,
                first_content,
                branch=branch
            )
            
            # If there's only one file, return early
            if len(files) == 1:
                return result['commit'].sha
            
            # Now add remaining files to the repo
            ref = repo.get_git_ref(f"heads/{branch}")
            latest_commit = repo.get_git_commit(ref.object.sha)
            base_tree = latest_commit.tree
            
            elements = []
            for filepath, content in list(files.items())[1:]:
                if isinstance(content, bytes):
                    content = content.decode('utf-8', errors='ignore')
                
                element = InputGitTreeElement(
                    path=filepath,
                    mode='100644',
                    type='blob',
                    content=content
                )
                elements.append(element)
            
            new_tree = repo.create_git_tree(elements, base_tree)
            new_commit = repo.create_git_commit(message, new_tree, [latest_commit])
            ref.edit(new_commit.sha)
            
            return new_commit.sha
        else:
            # Update existing files or add new ones
            from github import InputGitTreeElement
            
            ref = repo.get_git_ref(f"heads/{branch}")
            latest_commit = repo.get_git_commit(ref.object.sha)
            base_tree = latest_commit.tree
            
            elements = []
            for filepath, content in files.items():
                if isinstance(content, bytes):
                    content = content.decode('utf-8', errors='ignore')
                
                element = InputGitTreeElement(
                    path=filepath,
                    mode='100644',
                    type='blob',
                    content=content
                )
                elements.append(element)
            
            new_tree = repo.create_git_tree(elements, base_tree)
            new_commit = repo.create_git_commit(message, new_tree, [latest_commit])
            
            ref.edit(new_commit.sha)
            
            return new_commit.sha
    
    def enable_github_pages(self, repo: Repository, branch: str = "main"):
        """
        Enable GitHub Pages for repository.
        
        Args:
            repo: Repository object
            branch: Branch to deploy from
        """
        try:
            # Try to get existing Pages configuration
            try:
                pages = repo.get_pages_build()
            except:
                pass
            
            # Enable Pages using the API
            # Note: PyGithub doesn't have direct Pages support, so we use the underlying requester
            headers = {"Accept": "application/vnd.github.v3+json"}
            data = {
                "source": {
                    "branch": branch,
                    "path": "/"
                }
            }
            
            # Try to create/update Pages
            repo._requester.requestJsonAndCheck(
                "POST",
                f"{repo.url}/pages",
                headers=headers,
                input=data
            )
            
            # Wait for Pages to be ready
            time.sleep(5)
            
        except GithubException as e:
            # If Pages already exists, that's fine
            if e.status == 409:
                pass
            else:
                # Try PUT method for updating
                try:
                    repo._requester.requestJsonAndCheck(
                        "PUT",
                        f"{repo.url}/pages",
                        headers=headers,
                        input=data
                    )
                except:
                    pass
    
    def get_pages_url(self, repo_name: str) -> str:
        """
        Get GitHub Pages URL for repository.
        
        Args:
            repo_name: Repository name
        
        Returns:
            GitHub Pages URL
        """
        return f"https://{self.username}.github.io/{repo_name}/"
    
    def get_repo_url(self, repo_name: str) -> str:
        """Get repository URL."""
        return f"https://github.com/{self.username}/{repo_name}"
    
    def get_existing_files(self, repo: Repository, branch: str = "main") -> Dict[str, str]:
        """
        Get all files from repository.
        
        Args:
            repo: Repository object
            branch: Branch name
        
        Returns:
            Dictionary mapping filename to content
        """
        files = {}
        try:
            contents = repo.get_contents("", ref=branch)
            while contents:
                file_content = contents.pop(0)
                if file_content.type == "dir":
                    contents.extend(repo.get_contents(file_content.path, ref=branch))
                else:
                    try:
                        # Only get text files
                        if file_content.encoding == "base64":
                            content = base64.b64decode(file_content.content).decode('utf-8')
                            files[file_content.path] = content
                    except:
                        # Skip binary files or files that can't be decoded
                        pass
        except GithubException:
            pass
        
        return files

