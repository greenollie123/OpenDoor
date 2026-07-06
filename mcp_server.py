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


# --- DYNAMIC TOOL LOADING ---
CORE_TOOLS_DIR = os.path.join(ROOT_DIR, "tools")
CUSTOM_TOOLS_DIR = os.path.join(AI_WORKSPACE_DIR, "custom-tools")

for search_dir in [CORE_TOOLS_DIR, CUSTOM_TOOLS_DIR]:
    if os.path.exists(search_dir):
        for filepath in glob.glob(os.path.join(search_dir, "*.py")):
            basename = os.path.basename(filepath)
            if basename.startswith("__"):
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
