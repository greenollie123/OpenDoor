import os
import sys
import json
import glob
import datetime
from datetime import datetime
import shutil
import requests
from pathlib import Path
import yaml
from openai import OpenAI
from mcp.server.fastmcp import FastMCP
from typing import Literal
import importlib.util

ROOT_DIR = Path(__file__).resolve().parent
CONFIG_FILE = os.path.join(ROOT_DIR, "config.yaml")

# Load config to get weather coordinates
try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
except Exception:
    config = {}

LATITUDE = float(config.get("LATITUDE", 0.0))
LONGITUDE = float(config.get("LONGITUDE", 0.0))

api_key = config.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

MASTER_DIR = os.path.join(ROOT_DIR, "master")
AI_WORKSPACE_DIR = os.path.join(MASTER_DIR, "working")
FILE_DIR = os.path.join(MASTER_DIR, "files")
RUBBISH_BIN_DIR = os.path.join(FILE_DIR, "rubbish_bin")
KEY_MEMORIES_FILE = os.path.join(AI_WORKSPACE_DIR, "KEY_MEMORIES.json")

mcp = FastMCP("Core Assistant Tools")

def get_embedding(text: str) -> list:
    if not client:
        return []
    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=[text]
        )
        return response.data[0].embedding
    except Exception:
        return []

def cosine_similarity(v1: list, v2: list) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_a = sum(a * a for a in v1) ** 0.5
    norm_b = sum(b * b for b in v2) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def ask_for_consent(title: str, description: str) -> str:
    """Ask the user for consent or approval before carrying out an action.
    
    Args:
        title: The title/summary of the action requiring approval.
        description: The detailed description or command to run.
        
    Returns:
        "approved" or "denied"
    """
    import inspect
    caller_tool_name = None
    for frame_info in inspect.stack():
        func_name = frame_info.function
        if frame_info.filename.endswith(".py") and "tools" in frame_info.filename:
            caller_tool_name = func_name
            break
            
    try:
        resp = requests.post(
            "http://127.0.0.1:5050/api/request_consent",
            json={
                "title": title,
                "description": description,
                "tool_name": caller_tool_name
            },
            timeout=300
        )
        if resp.status_code == 200:
            return resp.json().get("action", "denied")
    except Exception as e:
        print(f"[-] Error requesting consent: {e}")
    return "denied"


@mcp.tool(name="ask_for_consent")
def ask_for_consent_tool(title: str, description: str) -> str:
    """Ask the user for consent or approval before carrying out an action.
    
    Args:
        title: The title/summary of the action requiring approval.
        description: The detailed description or command to run.
    """
    return ask_for_consent(title, description)


@mcp.tool(name="restart_mcp_server")
def restart_mcp_server() -> str:
    """Restart the MCP server to reload all core and custom tools from disk. Call this tool after adding, modifying, or deleting tools."""
    import threading
    import time
    
    def self_destruct():
        time.sleep(0.5)
        import sys
        sys.stderr.write("Exiting MCP server for restart...\n")
        sys.stderr.flush()
        os._exit(0)
        
    threading.Thread(target=self_destruct, daemon=True).start()
    return "Restarting MCP server... Connection will reconnect automatically."



# --- DYNAMIC TOOL LOADING ---
CORE_TOOLS_DIR = os.path.join(ROOT_DIR, "tools")
CUSTOM_TOOLS_DIR = os.path.join(AI_WORKSPACE_DIR, "custom-tools")

for search_dir in [CORE_TOOLS_DIR, CUSTOM_TOOLS_DIR]:
    if os.path.exists(search_dir):
        for filepath in glob.glob(os.path.join(search_dir, "*.py")):
            basename = os.path.basename(filepath)
            if basename.startswith("__"):
                continue
                
            if basename == "weather.py" and config.get("DISABLE_WEATHER", False):
                print("Skipping weather.py because weather tool is disabled in config.")
                continue
                
            module_name = f"tools.{basename[:-3]}"
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                
                # Inject shared context for AI-generated scripts
                module.mcp = mcp
                module.AI_WORKSPACE_DIR = AI_WORKSPACE_DIR
                module.RUBBISH_BIN_DIR = RUBBISH_BIN_DIR
                module.LATITUDE = LATITUDE
                module.LONGITUDE = LONGITUDE
                module.get_embedding = get_embedding
                module.cosine_similarity = cosine_similarity
                module.ask_for_consent = ask_for_consent
                
                # Inject standard libraries commonly used
                module.os = os
                module.json = json
                module.requests = requests
                module.datetime = datetime
                module.shutil = shutil
                module.Literal = Literal
                
                try:
                    spec.loader.exec_module(module)
                    print(f"Successfully loaded tool script: {basename}")
                except Exception as e:
                    print(f"Error loading tool script {basename}: {e}")

if __name__ == "__main__":
    mcp.run()
