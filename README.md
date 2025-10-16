# TDS Auto-Deploy API

Automated code generation and GitHub deployment API using AI LLM.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file from `env.example`:
```bash
cp env.example .env
```

3. Configure environment variables in `.env`:
- `API_SECRET`: Secret for API authentication
- `GITHUB_TOKEN`: GitHub Personal Access Token (with repo and pages permissions)
- `GITHUB_USERNAME`: Your GitHub username (default: sanat-garg)
- `AIPIPE_API_KEY`: AIPipe API key
- `AIPIPE_BASE_URL`: AIPipe API endpoint (default: https://aipipe.org/openrouter/v1)

## Running

```bash
python main.py
```

API will be available at `http://localhost:8000`

## API Endpoint

**POST** `/app`

Request body:
```json
{
  "email": "student@example.com",
  "secret": "your-api-secret",
  "task": "task-name",
  "round": 1,
  "nonce": "unique-nonce",
  "brief": "Project description",
  "checks": ["Requirement 1", "Requirement 2"],
  "evaluation_url": "https://example.com/notify",
  "attachments": [
    {"name": "file.png", "url": "data:image/png;base64,iVBORw..."}
  ]
}
```

Response:
```json
{
  "success": true,
  "message": "Successfully processed round 1",
  "repo_url": "https://github.com/sanat-garg/task-name",
  "commit_sha": "abc123...",
  "pages_url": "https://sanat-garg.github.io/task-name/"
}
```

