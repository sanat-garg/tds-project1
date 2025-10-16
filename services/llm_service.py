"""LLM service for code generation using AIPipe (OpenRouter-compatible API)."""
import os
import json
from typing import List, Dict
import httpx


class LLMService:
    """Service for interacting with AIPipe LLM."""
    
    def __init__(self, api_key: str, base_url: str = "https://aipipe.org/openrouter/v1"):
        """
        Initialize LLM service.
        
        Args:
            api_key: AIPipe API key
            base_url: Base URL for AIPipe API
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def generate_code(
        self, 
        brief: str, 
        checks: List[str], 
        attachment_names: List[str],
        existing_code: str = None
    ) -> Dict[str, str]:
        """
        Generate code using LLM.
        
        Args:
            brief: Project brief/description
            checks: List of evaluation criteria
            attachment_names: List of attachment filenames
            existing_code: Existing code to modify (for round > 1)
        
        Returns:
            Dictionary mapping filename to file content
        """
        # Build prompt
        if existing_code:
            prompt = self._build_modification_prompt(brief, checks, attachment_names, existing_code)
        else:
            prompt = self._build_initial_prompt(brief, checks, attachment_names)
        
        # Call LLM API
        response = self._call_api(prompt)
        
        # Parse response to extract files
        files = self._parse_response(response)
        
        return files
    
    def _build_initial_prompt(self, brief: str, checks: List[str], attachment_names: List[str]) -> str:
        """Build prompt for initial code generation."""
        checks_text = "\n".join(f"- {check}" for check in checks)
        attachments_text = "\n".join(f"- {name}" for name in attachment_names) if attachment_names else "None"
        
        attachments_note = ""
        if attachment_names:
            attachments_note = f"""
**Available Attachments:**
{attachments_text}

**CRITICAL - How to access and use attachments:**
- All attachments are in `attachments.js` (already created, just import it)
- Import: `<script src="attachments.js"></script>`
- Access: `window.attachments["filename.ext"]` returns a data URI string
- **DATA FORMAT**: Each value is a base64-encoded data URI like "data:image/png;base64,iVBORw..." or "data:text/csv;base64,bmFtZS..."
- **IMPORTANT**: NEVER embed data URIs directly in HTML attributes! Use JavaScript instead:
  - ❌ WRONG: `<img src="data:image/png;base64,iVBORw...">`
  - ✅ CORRECT: `<img id="myImg"><script>document.getElementById('myImg').src = window.attachments['image.png'];</script>`
- **YOU MUST DECODE text data**: For CSV/JSON, use `atob(window.attachments['data.csv'].split(',')[1])`
- For images, use JavaScript to set src from window.attachments
- The brief will tell you exactly what to do with each attachment
- Follow the brief's instructions precisely
"""
        
        prompt = f"""Create a simple web application using only vanilla HTML, CSS, and JavaScript.

**Brief:** {brief}

**CRITICAL EVALUATION CRITERIA (MUST BE SATISFIED):**
{checks_text}

**README.md Requirements:**
- Create a detailed, professional README.md that explains:
  - What the application does
  - How to use it
  - Features and functionality
  - Any special instructions or requirements
  - Make it comprehensive and well-structured

{attachments_note}
**Technical Requirements:**
- Use ONLY vanilla HTML, CSS, JavaScript (no frameworks or libraries)
- Create code that satisfies ALL evaluation criteria above
- Main entry point must be index.html
- Ensure all functionality works as specified in the brief
- Pay special attention to any URL parameters, timing requirements, or specific behaviors mentioned in evaluation criteria

**Output Format:**
Return ONLY a valid JSON object. No explanations, no markdown, no extra text.

CRITICAL JSON REQUIREMENTS:
- Start with {{ and end with }}
- Use double quotes for keys and string values
- Properly escape special characters: \" for quotes, \\n for newlines, \\\\ for backslashes
- NO trailing commas before closing braces
- NO comments in JSON

Example structure:
{{
  "index.html": "<!DOCTYPE html>\\n<html>...</html>",
  "README.md": "# Title\\n\\nDescription",
  "style.css": "body {{ margin: 0; }}",
  "script.js": "console.log('hello');"
}}

Only include files you're creating/modifying. Return ONLY the JSON, nothing else."""

        return prompt
    
    def _build_modification_prompt(
        self, 
        brief: str, 
        checks: List[str], 
        attachment_names: List[str],
        existing_code: str
    ) -> str:
        """Build prompt for code modification."""
        checks_text = "\n".join(f"- {check}" for check in checks)
        
        attachments_note = ""
        if attachment_names:
            attachments_text = "\n".join(f"- {name}" for name in attachment_names)
            attachments_note = f"""
**Available Attachments:**
{attachments_text}

**CRITICAL:** 
- Attachments are in `attachments.js` (auto-generated, do NOT modify or regenerate it)
- Access: `window.attachments["filename.ext"]` returns a base64-encoded data URI
- Import: `<script src="attachments.js"></script>`
- **NEVER embed data URIs directly in HTML!** Use JavaScript to set them:
  - ✅ CORRECT: `<img id="img1"><script>document.getElementById('img1').src = window.attachments['image.png'];</script>`
- **MUST DECODE text data**: For CSV/JSON, use: `atob(window.attachments['file.csv'].split(',')[1])`
- Follow the brief's instructions for processing these attachments
"""
        
        prompt = f"""You are modifying an EXISTING web application. Build upon the current code.

**New Requirements to ADD/MODIFY:** {brief}

**CRITICAL EVALUATION CRITERIA (MUST BE SATISFIED):**
{checks_text}

**README.md Requirements:**
- Update the README.md to reflect any new features or changes
- Ensure it remains detailed and professional
- Document any new functionality added in this round
- Keep it comprehensive and well-structured

**Current Code (DO NOT DISCARD, BUILD UPON THIS):**
{existing_code}
{attachments_note}
**CRITICAL Instructions:**
- **BUILD UPON** the existing code, don't start from scratch
- **ADD or MODIFY** features as requested in the new requirements
- **PRESERVE** existing functionality unless explicitly asked to remove it
- **EXTEND** the code, don't replace it entirely
- **SATISFY ALL EVALUATION CRITERIA** listed above
- Pay special attention to URL parameters, timing requirements, or specific behaviors
- Keep using vanilla HTML, CSS, JavaScript only
- Update README.md with new features and changes
- **NEVER include attachments.js in your output** (it's auto-generated by the system)

**Output Format:**
Return ONLY a valid JSON object. No explanations, no markdown, no extra text.

CRITICAL JSON REQUIREMENTS:
- Start with {{ and end with }}
- Use double quotes for keys and string values
- Properly escape: \" for quotes, \\n for newlines, \\\\ for backslashes
- NO trailing commas before closing braces
- NO comments in JSON

Example:
{{
  "index.html": "<!DOCTYPE html>\\n<html>...</html>",
  "README.md": "# Updated\\n\\nChanges made"
}}

Only include files you're modifying. Return ONLY the JSON, nothing else."""

        return prompt
    
    def _call_api(self, prompt: str) -> str:
        """Call the AIPipe API."""
        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a code generator that ONLY outputs valid JSON. Never include explanations or markdown. Follow instructions precisely. Always complete your JSON response fully."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 4000
        }
        
        with httpx.Client(timeout=180.0) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            # Check if response was truncated
            finish_reason = data["choices"][0].get("finish_reason")
            if finish_reason == "length":
                raise ValueError("LLM response was truncated due to max_tokens limit. Response may be incomplete.")
            
            return content
    
    def _parse_response(self, response: str) -> Dict[str, str]:
        """Parse LLM response to extract files with robust error handling."""
        import re
        
        # Clean the response
        response = response.strip()
        
        # Remove markdown code blocks
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        
        response = response.strip()
        
        # Try direct JSON parsing first
        try:
            files = json.loads(response)
            if isinstance(files, dict):
                return files
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON object using regex
        json_matches = re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
        for match in json_matches:
            try:
                files = json.loads(match.group())
                if isinstance(files, dict) and any(key.endswith('.html') for key in files.keys()):
                    return files
            except:
                continue
        
        # Try to find the largest JSON-like structure and fix common issues
        try:
            start = response.find('{')
            end = response.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_str = response[start:end+1]
                
                # Fix common JSON issues
                # Remove trailing commas before closing braces
                json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                
                files = json.loads(json_str)
                if isinstance(files, dict):
                    return files
        except:
            pass
        
        # Last resort: try to manually extract key-value pairs
        try:
            files = {}
            # Look for patterns like "filename.ext": "content"
            pattern = r'"([^"]+\.(html|css|js|md))"\s*:\s*"((?:[^"\\]|\\.)*)"'
            matches = re.findall(pattern, response, re.DOTALL)
            for filename, ext, content in matches:
                files[filename] = content.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
            
            if files:
                return files
        except:
            pass
        
        # If all else fails, create a basic structure
        raise ValueError(f"Failed to parse LLM response as valid JSON. Response preview: {response[:500]}")

