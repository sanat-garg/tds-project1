"""FastAPI application for automated code generation and GitHub deployment."""
import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

from services.llm_service import LLMService
from services.github_service import GitHubService
from services.utils import (
    decode_data_uri,
    get_task_info,
    update_task_info,
    get_mit_license
)

# Load environment variables
load_dotenv()

# Initialize FastAPI
app = FastAPI(title="TDS Auto-Deploy API")

# Configuration
API_SECRET = os.getenv("API_SECRET")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "sanat-garg")
AIPIPE_API_KEY = os.getenv("AIPIPE_API_KEY")
AIPIPE_BASE_URL = os.getenv("AIPIPE_BASE_URL", "https://aipipe.org/openrouter/v1")

# Initialize services
llm_service = LLMService(api_key=AIPIPE_API_KEY, base_url=AIPIPE_BASE_URL)
github_service = GitHubService(token=GITHUB_TOKEN, username=GITHUB_USERNAME)


class Attachment(BaseModel):
    """Attachment model."""
    name: str
    url: str


class TaskRequest(BaseModel):
    """Request model for task processing."""
    email: str
    secret: str
    task: str
    round: int
    nonce: str
    brief: str
    checks: List[str]
    evaluation_url: str
    attachments: Optional[List[Attachment]] = []


class TaskResponse(BaseModel):
    """Response model for task processing."""
    success: bool
    message: str
    repo_url: str
    commit_sha: str
    pages_url: str


@app.get("/")
async def root():
    """Root endpoint."""
    return {"status": "TDS Auto-Deploy API is running"}


@app.post("/app", response_model=TaskResponse)
async def process_task(request: TaskRequest):
    """
    Process a task: generate code, deploy to GitHub, enable Pages, and notify.
    
    Args:
        request: Task request with all details
    
    Returns:
        Task response with repository information
    """
    # Step 1: Authentication
    if request.secret != API_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret")
    
    try:
        # Extract repo name from task
        repo_name = request.task
        
        # Step 2: Repository Management
        if request.round == 1:
            # Round 1: Create fresh repository
            if github_service.repo_exists(repo_name):
                github_service.delete_repo(repo_name)
            
            repo = github_service.create_repo(repo_name)
            existing_code = None
            existing_files = {}
        else:
            # Round > 1: Get existing repository
            task_info = get_task_info(request.task)
            if not task_info:
                raise HTTPException(
                    status_code=400, 
                    detail=f"No existing repository found for task {request.task}"
                )
            
            repo = github_service.get_repo(repo_name)
            # Get existing code for modification
            existing_files = github_service.get_existing_files(repo)
            existing_code = "\n\n".join(
                f"=== {filename} ===\n{content}" 
                for filename, content in existing_files.items()
            )
        
        # Step 3: Handle Attachments
        # Build attachments.js file with all attachments (accumulate across rounds)
        attachments_dict = {}
        
        # Always try to load existing attachments if they exist
        if "attachments.js" in existing_files:
            # Parse existing attachments.js to get previous attachments
            import re
            import json
            js_content = existing_files["attachments.js"]
            # Extract the JSON part from window.attachments = {...};
            match = re.search(r'window\.attachments\s*=\s*({.+})\s*;', js_content, re.DOTALL)
            if match:
                try:
                    attachments_dict = json.loads(match.group(1))
                    print(f"Loaded {len(attachments_dict)} existing attachments")
                except Exception as e:
                    print(f"Failed to parse existing attachments: {e}")
                    pass
        
        # Add new attachments to the dictionary (will append, or overwrite if same name)
        for attachment in request.attachments:
            # Store the full data URI (not decoded)
            attachments_dict[attachment.name] = attachment.url
            print(f"Added attachment: {attachment.name}")
        
        # Get ALL attachment names (old + new) for LLM
        attachment_names = list(attachments_dict.keys())
        print(f"Total attachments available: {attachment_names}")
        
        # Step 4: Generate attachments.js (API-generated, not LLM)
        attachments_js_content = None
        if attachments_dict:
            import json
            attachments_js_content = f"""// Auto-generated attachments file
// Access attachments via: window.attachments["filename.ext"]
window.attachments = {json.dumps(attachments_dict, indent=2)};
"""
        
        # Step 5: LLM Code Generation
        try:
            generated_files = llm_service.generate_code(
                brief=request.brief,
                checks=request.checks,
                attachment_names=attachment_names,
                existing_code=existing_code
            )
        except ValueError as e:
            # If JSON parsing fails, provide detailed error
            raise HTTPException(
                status_code=500,
                detail=f"LLM generated invalid response: {str(e)}"
            )
        except Exception as e:
            # Generic LLM error
            raise HTTPException(
                status_code=500,
                detail=f"LLM generation failed: {str(e)}"
            )
        
        # Step 6: Prepare all files for commit
        all_files = {}
        
        # For round 2+, start with existing files then update with new ones
        if request.round > 1:
            # Copy all existing files first (excluding attachments.js)
            for filename, content in existing_files.items():
                if filename != "attachments.js":  # We'll regenerate this
                    all_files[filename] = content
            print(f"Starting with {len(all_files)} existing files for round {request.round}")
        
        # Update/add generated files (this will overwrite existing files with same name)
        all_files.update(generated_files)
        print(f"After LLM generation: {len(all_files)} total files")
        
        # Validate that we have at least index.html
        if "index.html" not in all_files:
            raise HTTPException(
                status_code=500,
                detail="LLM did not generate required index.html file"
            )
        
        # Validate that HTML is complete (not truncated)
        html_content = all_files["index.html"]
        if not html_content.strip().endswith("</html>") and not html_content.strip().endswith("</HTML>"):
            print(f"WARNING: HTML appears truncated. Last 200 chars: {html_content[-200:]}")
            # Try to close the HTML properly
            if "<html" in html_content.lower() and "</html>" not in html_content.lower():
                html_content += "\n</body>\n</html>"
                all_files["index.html"] = html_content
                print("Auto-closed HTML tags")
        
        # Add attachments.js if we have attachments
        if attachments_js_content:
            all_files["attachments.js"] = attachments_js_content
        
        # Handle evaluation criteria requirements
        print(f"Evaluation criteria to satisfy: {request.checks}")
        
        # Check for MIT license requirement
        mit_license_required = any("mit license" in check.lower() for check in request.checks)
        if mit_license_required or "LICENSE" not in all_files:
            all_files["LICENSE"] = get_mit_license()
            print("Added MIT License file")
        
        # Ensure README.md exists (LLM should generate detailed one, but fallback if needed)
        if "README.md" not in all_files:
            # Create a basic README as fallback
            basic_readme = f"""# {repo_name}

## Overview
Auto-generated project based on: {request.brief}

## Features
- Please refer to the application for full functionality details

## Usage
1. Open `index.html` in a web browser
2. Follow any on-screen instructions

## Technical Details
- Built with vanilla HTML, CSS, and JavaScript
- No external dependencies required

## Evaluation Criteria
{chr(10).join(f"- {check}" for check in request.checks)}
"""
            all_files["README.md"] = basic_readme
            print("Created fallback README.md")
        else:
            print("Using LLM-generated README.md")
        
        # Step 7: Commit to GitHub
        commit_message = f"Round {request.round}: {request.brief}"
        commit_sha = github_service.commit_files(
            repo=repo,
            files=all_files,
            message=commit_message
        )
        
        # Step 8: Enable GitHub Pages and ensure repo is public
        github_service.enable_github_pages(repo)
        
        # Ensure repository is public (common evaluation requirement)
        public_repo_required = any("public" in check.lower() for check in request.checks)
        if public_repo_required:
            try:
                if repo.private:
                    print("Making repository public as required by evaluation criteria")
                    repo.edit(private=False)
            except Exception as e:
                print(f"Warning: Could not ensure repository is public: {e}")
        
        print("Repository configuration completed")
        
        # Get URLs
        repo_url = github_service.get_repo_url(repo_name)
        pages_url = github_service.get_pages_url(repo_name)
        
        # Step 9: Notify Evaluation URL
        notification_payload = {
            "email": request.email,
            "task": request.task,
            "round": request.round,
            "nonce": request.nonce,
            "repo_url": repo_url,
            "commit_sha": commit_sha,
            "pages_url": pages_url
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(request.evaluation_url, json=notification_payload)
        
        # Step 10: Update State
        update_task_info(request.task, {
            "repo_name": repo_name,
            "repo_url": repo_url,
            "commit_sha": commit_sha,
            "pages_url": pages_url,
            "last_round": request.round
        })
        
        # Step 11: Return Response
        return TaskResponse(
            success=True,
            message=f"Successfully processed round {request.round}",
            repo_url=repo_url,
            commit_sha=commit_sha,
            pages_url=pages_url
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

