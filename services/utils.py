"""Utility functions for the application."""
import base64
import json
import os
from typing import Dict, Optional


STATE_FILE = "state.json"


def decode_data_uri(data_uri: str) -> bytes:
    """
    Decode a data URI to bytes.
    
    Args:
        data_uri: Data URI string (e.g., "data:image/png;base64,iVBORw...")
    
    Returns:
        Decoded bytes
    """
    # Extract the base64 part after the comma
    if ',' in data_uri:
        base64_data = data_uri.split(',', 1)[1]
    else:
        base64_data = data_uri
    
    return base64.b64decode(base64_data)


def load_state() -> Dict:
    """Load state from JSON file."""
    if not os.path.exists(STATE_FILE):
        return {}
    
    with open(STATE_FILE, 'r') as f:
        return json.load(f)


def save_state(state: Dict):
    """Save state to JSON file."""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def get_task_info(task_id: str) -> Optional[Dict]:
    """Get task information from state."""
    state = load_state()
    return state.get(task_id)


def update_task_info(task_id: str, info: Dict):
    """Update task information in state."""
    state = load_state()
    state[task_id] = info
    save_state(state)


def get_mit_license() -> str:
    """Return MIT License text."""
    return """MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

