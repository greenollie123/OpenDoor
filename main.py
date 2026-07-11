import os
import sys
import json
import base64
import glob
import datetime
from datetime import datetime
from openai import OpenAI
import subprocess
import threading
import logging
import yaml
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from pathlib import Path
import shutil
import requests
import asyncio
import ast
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT_DIR = Path(__file__).resolve().parent
CONFIG_FILE = os.path.join(ROOT_DIR, "config.yaml")

# Global Configuration & State Management
config = {}
LATITUDE = 0.0
LONGITUDE = 0.0

chat_lock = threading.Lock()
ui_target = None

ui_updates = []
ui_updates_lock = threading.Lock()

pending_approvals = {}
pending_approvals_lock = threading.Lock()
active_tool_contexts = {}
active_tool_contexts_lock = threading.Lock()
tool_executions_log = {}
tool_executions_lock = threading.Lock()
request_context = threading.local()

def add_ui_update(update_type, channel, content, agent="Terry", **kwargs):
    with ui_updates_lock:
        upd = {
            "id": len(ui_updates),
            "type": update_type,
            "channel": channel,
            "content": content,
            "agent": agent
        }
        upd.update(kwargs)
        ui_updates.append(upd)


def load_session_into_updates(agent_name):
    history = load_chat_history(agent_name)
    with ui_updates_lock:
        ui_updates.append({
            "id": len(ui_updates),
            "type": "system",
            "channel": "System",
            "content": "CLEAR",
            "agent": agent_name
        })
        for msg in history:
            role = msg.get("role")
            if role == "user":
                content = msg.get("content", "")
                has_image = False
                if isinstance(content, list):
                    text_part = next((item["text"] for item in content if isinstance(item, dict) and item.get("type") == "text"), "")
                    has_image = any(isinstance(item, dict) and item.get("type") == "image_url" for item in content)
                    content = text_part
                
                channel = "External"
                if isinstance(content, str) and content.startswith("[") and " Channel]: " in content:
                    parts = content.split(" Channel]: ", 1)
                    channel = parts[0][1:]
                    content = parts[1]
                
                if has_image and channel != "Web":
                    content = f"🖼️ [Image Uploaded] {content}"
                
                ui_updates.append({
                    "id": len(ui_updates),
                    "type": "user",
                    "channel": channel,
                    "content": content,
                    "agent": agent_name
                })
            elif role == "assistant":
                content = msg.get("content", "")
                channel = msg.get("channel", "External")
                if content:
                    import re
                    import os
                    if channel == "Web":
                        def replace_file_tag(m):
                            fpath = m.group(1).replace("\\", "/")
                            name = os.path.basename(fpath)
                            import urllib.parse
                            url_path = urllib.parse.quote(fpath)
                            return f"📎 [{name}](/api/download?path={url_path})"
                        content = re.sub(r'\[SEND_FILE:\s*(.+?)\]', replace_file_tag, content)
                        
                    ui_updates.append({
                        "id": len(ui_updates),
                        "type": "agent",
                        "channel": channel,
                        "content": content,
                        "agent": agent_name
                    })

webhook_app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
subprocesses = []

client = None

mcp_loop = None
mcp_session = None
mcp_thread = None
mcp_client_context = None
mcp_restart_event = None

MAIN_DIR = Path(__file__).resolve().parent

MASTER_DIR = os.path.join(MAIN_DIR, r"master")
os.makedirs(MAIN_DIR, exist_ok=True)

AI_WORKSPACE_DIR = os.path.join(MASTER_DIR, r"working")
os.makedirs(AI_WORKSPACE_DIR, exist_ok=True)
FILE_DIR = os.path.join(MASTER_DIR, r"files")
os.makedirs(FILE_DIR, exist_ok=True)

RUBBISH_BIN_DIR = os.path.join(FILE_DIR, "rubbish_bin")
os.makedirs(RUBBISH_BIN_DIR, exist_ok=True)


SYSTEM_FILE = os.path.join(AI_WORKSPACE_DIR, r"SYSTEM.md")
SOUL_FILE = os.path.join(AI_WORKSPACE_DIR, r"SOUL.md")
KEY_MEMORIES_FILE = os.path.join(AI_WORKSPACE_DIR, r"KEY_MEMORIES.json") 

DEFAULT_SYSTEM_PROMPT = """# SYSTEM (SYSTEM.md)

## CONTEXT VS FILES:
- You can already see the current conversation history in your active context. If the user asks about things you said or did inside this active chat session, just answer directly from your memory. Do NOT call a tool.
- ONLY use 'read_file' if the user asks about a previous archived session or requires you to check a file.

## CRITICAL RULES:
1. If the user asks you to save or update something, you MUST explicitly call your writing/patching tools. Do not just talk about doing it.
2. Never claim an update was made unless you successfully executed a tool and saw the confirmation message.
3. When patching text using 'file_patch_text', preserve structural formatting or existing layout timestamps if present.
4. Do not use emojis.

## TOOLS:
- To create tools, read `custom-tools/CUSTOM_TOOLS_CREATION_TUTORIAL.md` first.

## MEMORY MANAGEMENT INSTRUCTIONS:
You have a persistent core memory. You MUST actively use the `add_memory` tool to record important user preferences, ongoing projects, requested defaults, or future events. 
- If a user states a preference or fact, save it permanently.
- If a user mentions a temporary event (e.g., "I'm travelling to Scotland next week"), save it with an appropriate `expiry_date`.
- If the user corrects a previous fact, use `remove_memory` on the old fact and `add_memory` for the new one.
Do not ask permission to save a memory—just do it seamlessly in the background.
"""

DEFAULT_SOUL_TEXT = """# SOUL (SOUL.md)
You are {agent_name}, a highly intelligent and capable AI assistant."""
LOAD_TO_PROMPT_ON_MESSAGE = []
SUBPROGRAMS_DIR = os.path.join(MAIN_DIR, r"sub-programs")

chat_history = []
tools = []
available_functions = {}


def load_config():
    if not os.path.exists(CONFIG_FILE):
        example_file = CONFIG_FILE + ".example"
        if os.path.exists(example_file):
            shutil.copy(example_file, CONFIG_FILE)
            print(f"'{CONFIG_FILE}' was not found. Automatically copied from '{os.path.basename(example_file)}'.")
        else:
            print(f"Error: '{CONFIG_FILE}' and its template '{os.path.basename(example_file)}' are both missing.")
            print("Please restore the config template or create config.yaml manually.")
            print("\nPress ENTER to close...")
            input()
            sys.exit(1)
            
        print("\n" + "="*60)
        print(f" ACTION REQUIRED: Please open and edit '{os.path.basename(CONFIG_FILE)}' now.")
        print(" Set your LATITUDE, LONGITUDE, and DEFAULT_MODEL.")
        print("="*60)
        print("\nPress ENTER when you are done editing to continue...")
        input()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            loaded_config = yaml.safe_load(f)
    except yaml.YAMLError:
        print(f"Error: '{CONFIG_FILE}' contains invalid YAML formatting. Please fix your config file or delete it to regenerate a fresh template.")
        print("\nPress ENTER to close...")
        input()
        sys.exit(0)

    required_keys = ["LATITUDE", "LONGITUDE", "DEFAULT_MODEL"]
    missing_keys = [key for key in required_keys if key not in loaded_config]

    if missing_keys:
        print("=" * 60)
        print(f" ERROR: Missing configuration settings in '{os.path.basename(CONFIG_FILE)}'")
        print(f" Missing fields: {', '.join(missing_keys)}")
        print(" Please fix your config file or delete it to regenerate a fresh template.")
        print("=" * 60)
        print("\nPress ENTER to close...")
        input()
        sys.exit(0)

    return loaded_config


@webhook_app.route('/api/upload', methods=['POST'])
def handle_upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    agent_name = request.form.get('agent', 'Terry')
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    filename = secure_filename(file.filename)
    if not filename:
        import time
        filename = f"file_{int(time.time())}"
        
    ext = os.path.splitext(filename)[1].lower()
    is_image = ext in ['.png', '.jpg', '.jpeg', '.webp']
    
    if is_image:
        dest_dir = os.path.join(AI_WORKSPACE_DIR, "agents", agent_name, "uploaded_media")
    else:
        dest_dir = os.path.join(AI_WORKSPACE_DIR, "agents", agent_name)
        
    os.makedirs(dest_dir, exist_ok=True)
    
    name, extension = os.path.splitext(filename)
    counter = 1
    unique_filename = filename
    while os.path.exists(os.path.join(dest_dir, unique_filename)):
        unique_filename = f"{name}_{counter}{extension}"
        counter += 1
        
    filepath = os.path.join(dest_dir, unique_filename)
    file.save(filepath)
    
    if is_image:
        relative_path = f"uploaded_media/{unique_filename}"
        web_url = f"/api/files/{agent_name}/{relative_path}"
        return jsonify({
            "status": "success",
            "type": "image",
            "filename": unique_filename,
            "url": web_url,
            "absolute_path": filepath
        })
    else:
        relative_path = unique_filename
        web_url = f"/api/files/{agent_name}/{relative_path}"
        return jsonify({
            "status": "success",
            "type": "document",
            "filename": unique_filename,
            "url": web_url,
            "absolute_path": filepath,
            "relative_path": f"agents/{agent_name}/{unique_filename}"
        })


@webhook_app.route('/api/files/<agent_name>/<path:filepath>', methods=['GET'])
def get_agent_file(agent_name, filepath):
    agent_dir = os.path.abspath(os.path.join(AI_WORKSPACE_DIR, "agents", agent_name))
    target_path = os.path.abspath(os.path.join(agent_dir, filepath))
    
    if not target_path.startswith(agent_dir):
        return jsonify({"error": "Access denied"}), 403
        
    if not os.path.exists(target_path):
        return jsonify({"error": "File not found"}), 404
        
    dir_name = os.path.dirname(target_path)
    base_name = os.path.basename(target_path)
    return send_from_directory(dir_name, base_name)


@webhook_app.route('/api/download', methods=['GET'])
def download_file():
    target_path = request.args.get('path')
    if not target_path:
        return jsonify({"error": "Missing path parameter"}), 400
        
    target_path = os.path.abspath(target_path)
    workspace = os.path.abspath(AI_WORKSPACE_DIR)
    
    if not target_path.startswith(workspace):
        return jsonify({"error": "Access denied"}), 403
        
    if not os.path.exists(target_path):
        return jsonify({"error": "File not found"}), 404
        
    dir_name = os.path.dirname(target_path)
    base_name = os.path.basename(target_path)
    return send_from_directory(dir_name, base_name, as_attachment=True)


@webhook_app.route('/api/message', methods=['POST'])
def handle_webhook_message():
    data = request.json or {}
    if not data or 'text' not in data:
        return jsonify({"error": "Missing 'text' in payload"}), 400

    channel = data.get("channel", "External")
    text = data.get("text", "")
    agent = data.get("agent", "Terry")
    media_paths = data.get("media_paths", [])
    
    sender_id = data.get("sender_id")
    chat_id = data.get("chat_id")
    
    # Check for pending text tool authorizations
    found_pending = None
    pending_appr_id = None
    with pending_approvals_lock:
        for app_id, info in pending_approvals.items():
            if info.get("status") == "pending" and info.get("agent_name") == agent:
                if info.get("channel") not in ["Web", "WhatsApp"]:
                    found_pending = info
                    pending_appr_id = app_id
                    break

    if found_pending:
        text_lower = text.lower()
        import re
        is_approved = any(re.search(rf"\b{word}\b", text_lower) for word in ["yes", "accept", "go"])
        is_denied = any(re.search(rf"\b{word}\b", text_lower) for word in ["no", "deny", "cancel", "reject", "stop"])
        
        if is_approved or is_denied:
            decision = "approved" if is_approved else "denied"
            with pending_approvals_lock:
                if pending_appr_id in pending_approvals:
                    pending_approvals[pending_appr_id]["status"] = decision
                    with ui_updates_lock:
                        for u in ui_updates:
                            if u.get("approval_id") == pending_appr_id:
                                u["decision"] = decision
                    found_pending["event"].set()
            
            status_text = "approved" if is_approved else "denied"
            reply_text = f"Tool Authorization {status_text}."
            add_ui_update("user", channel, text, agent)
            add_ui_update("system", channel, f"Authorization {status_text} by user text: '{text}'", agent)
            return jsonify({"reply": reply_text})
        else:
            reply_text = f"⚠️ Tool Authorization is pending for agent '{agent}'. Please reply with 'yes', 'accept', or 'go' to allow the action, or 'no'/'cancel' to deny it."
            return jsonify({"reply": reply_text})

    if channel == "WhatsApp":
        def run_async_process(c_id, s_id):
            request_context.channel = channel
            request_context.sender_id = s_id
            request_context.chat_id = c_id
            try:
                reply_text = process_message(channel, text, agent, media_paths)
                if reply_text:
                    requests.post(
                        "http://127.0.0.1:5056/send_message",
                        json={"chat_id": c_id, "text": reply_text},
                        timeout=10
                    )
            except Exception as e:
                print(f"[-] Error in async WhatsApp process: {e}")
                
        threading.Thread(target=run_async_process, args=(chat_id, sender_id), daemon=True).start()
        return jsonify({"status": "queued"})
    else:
        request_context.channel = channel
        request_context.sender_id = sender_id
        request_context.chat_id = chat_id
        reply_text = process_message(channel, text, agent, media_paths)
        return jsonify({"reply": reply_text})


@webhook_app.route('/api/approve', methods=['POST'])
def handle_approval():
    data = request.json or {}
    approval_id = data.get("approval_id")
    action = data.get("action")  # "approved" or "denied"
    
    if not approval_id or action not in ["approved", "denied"]:
        return jsonify({"error": "Missing or invalid approval_id or action"}), 400
        
    with pending_approvals_lock:
        if approval_id in pending_approvals:
            info = pending_approvals[approval_id]
            info["status"] = action
            
            with ui_updates_lock:
                for u in ui_updates:
                    if u.get("approval_id") == approval_id:
                        u["decision"] = action
                        
            info["event"].set()
            return jsonify({"status": "success"})
            
    return jsonify({"error": "Approval request not found or already processed"}), 404


@webhook_app.route('/api/request_consent', methods=['POST'])
def handle_request_consent():
    import random
    import time
    data = request.json or {}
    title = data.get("title", "Action Authorization")
    description = data.get("description", "")
    tool_name = data.get("tool_name")
    
    # Retrieve context based on tool_name
    context = {}
    if tool_name:
        with active_tool_contexts_lock:
            context = active_tool_contexts.get(tool_name, {})
            
    # Fallback to current request_context fields
    channel = context.get("channel") or getattr(request_context, "channel", "External")
    chat_id = context.get("chat_id") or getattr(request_context, "chat_id", None)
    sender_id = context.get("sender_id") or getattr(request_context, "sender_id", None)
    agent_name = context.get("agent_name") or "Terry"
    
    approval_id = f"appr_{int(time.time())}_{random.randint(1000, 9999)}"
    event = threading.Event()
    
    with pending_approvals_lock:
        pending_approvals[approval_id] = {
            "status": "pending",
            "title": title,
            "description": description,
            "event": event,
            "agent_name": agent_name,
            "channel": channel
        }
        
    if channel not in ["Web", "WhatsApp"]:
        # Text tool authentication for non-Web, non-WhatsApp channels
        auth_msg = (
            "⚠️ Tool Authorization\n"
            f"Agent: `{agent_name}`\n"
            f"{title}\n"
            f"`{description}`\n\n"
            "Reply `accept` or `deny` to respond."
        )
        add_ui_update(
            update_type="system",
            channel=channel,
            content=auth_msg,
            agent=agent_name
        )
    else:
        if channel == "Web":
            add_ui_update(
                update_type="approval_request",
                channel=channel,
                content=description,
                title=title,
                description=description,
                agent=agent_name,
                approval_id=approval_id,
                decision="pending"
            )
        elif channel == "WhatsApp":
            if chat_id:
                try:
                    payload = {
                        "chat_id": chat_id,
                        "command": f"{title}\n{description}",
                        "approval_id": approval_id,
                        "agent_name": agent_name
                    }
                    resp = requests.post("http://127.0.0.1:5056/send_poll", json=payload, timeout=10)
                    if resp.status_code != 200:
                        print(f"[-] WhatsApp listener returned error: {resp.text}")
                except Exception as ex:
                    print(f"[-] Failed to communicate with WhatsApp approval listener: {ex}")
            else:
                print("[-] Cannot request consent: chat_id is missing from context.")
                
    event.wait()
    
    with pending_approvals_lock:
        approval_info = pending_approvals.get(approval_id)
        decision = approval_info["status"] if approval_info else "denied"
        pending_approvals.pop(approval_id, None)
        
    return jsonify({"action": decision})



@webhook_app.route('/api/updates', methods=['GET'])
def get_updates():
    since = request.args.get('since', 0, type=int)
    agent = request.args.get('agent', 'Terry')
    with ui_updates_lock:
        updates = [u for u in ui_updates[since:] if u.get("agent") == agent]
    return jsonify({"updates": updates})


@webhook_app.route('/api/agents', methods=['GET'])
def get_agents():
    agents_working_dir = os.path.join(AI_WORKSPACE_DIR, "agents")
    if not os.path.exists(agents_working_dir):
        return jsonify({"agents": [], "agent_details": {}})
    agents = []
    agent_details = {}
    for item in os.listdir(agents_working_dir):
        if os.path.isdir(os.path.join(agents_working_dir, item)):
            agents.append(item)
            info = get_agent_info(item)
            agent_details[item] = info
    return jsonify({"agents": agents, "agent_details": agent_details})

@webhook_app.route('/api/create_agent', methods=['POST'])
def create_agent():
    data = request.json or {}
    agent_name = data.get('agent_name')
    agent_display_name = data.get('agent_display_name', agent_name)
    if not agent_name:
        return jsonify({"status": "error", "message": "agent_name is required"}), 400
    
    agent_working_dir = os.path.join(AI_WORKSPACE_DIR, "agents", agent_name)
    agent_files_dir = os.path.join(FILE_DIR, "agents", agent_name)
    
    os.makedirs(agent_working_dir, exist_ok=True)
    os.makedirs(agent_files_dir, exist_ok=True)
    
    config_file = os.path.join(agent_working_dir, "config.yaml")
    agent_config = {
        "AI_MODEL": config.get("DEFAULT_MODEL", "gpt-5.4-nano"),
        "AI_NAME": agent_display_name,
    }
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(agent_config, f)
        
    os.makedirs(os.path.join(agent_working_dir, "archived-sessions"), exist_ok=True)
    os.makedirs(os.path.join(agent_files_dir, "archived-sessions"), exist_ok=True)
    
    tools_yaml = os.path.join(agent_files_dir, "tools.yaml")
    if not os.path.exists(tools_yaml):
        with open(tools_yaml, "w", encoding="utf-8") as f:
            yaml.safe_dump({"disabled_tools": []}, f)
            
    skills_yaml = os.path.join(agent_files_dir, "skills.yaml")
    if not os.path.exists(skills_yaml):
        with open(skills_yaml, "w", encoding="utf-8") as f:
            yaml.safe_dump({"disabled_skills": []}, f)
    update_and_get_agent_skills(agent_name)
            
    sys_file = os.path.join(agent_working_dir, "SYSTEM.md")
    if not os.path.exists(sys_file):
        with open(sys_file, "w", encoding="utf-8") as f:
            f.write(DEFAULT_SYSTEM_PROMPT)
            
    soul_file = os.path.join(agent_working_dir, "SOUL.md")
    if not os.path.exists(soul_file):
        with open(soul_file, "w", encoding="utf-8") as f:
            f.write(DEFAULT_SOUL_TEXT.format(agent_name=agent_display_name))

    mem_file = os.path.join(agent_working_dir, "KEY_MEMORIES.json")
    if not os.path.exists(mem_file):
        with open(mem_file, "w", encoding="utf-8") as f:
            json.dump([], f)
    
    return jsonify({"status": "success", "agent": agent_name})

@webhook_app.route('/api/agent_settings', methods=['POST'])
def update_agent_settings():
    data = request.json or {}
    agent_name = data.get('agent')
    settings = data.get('settings', {})
    
    if not agent_name:
        return jsonify({"status": "error", "message": "agent is required"}), 400
        
    agent_working_dir = os.path.join(AI_WORKSPACE_DIR, "agents", agent_name)
    config_file = os.path.join(agent_working_dir, "config.yaml")
    
    current_config = {}
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if loaded:
                    current_config = loaded
        except Exception:
            pass
            
    current_config.update(settings)
    
    os.makedirs(agent_working_dir, exist_ok=True)
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(current_config, f)
        
    return jsonify({"status": "success"})


@webhook_app.route('/api/load_agent', methods=['GET'])
def load_agent():
    agent_name = request.args.get('agent', 'Terry')
    load_session_into_updates(agent_name)
    return jsonify({"status": "success", "agent": agent_name})

@webhook_app.route('/api/agent_tools', methods=['GET'])
def get_agent_tools():
    global tools
    if len(tools) <= 1:
        _build_tools()
        
    agent_name = request.args.get('agent', 'Terry')
    agent_files_dir = os.path.join(FILE_DIR, "agents", agent_name)
    tools_yaml_path = os.path.join(agent_files_dir, "tools.yaml")
    
    disabled_tools = []
    if os.path.exists(tools_yaml_path):
        try:
            with open(tools_yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                disabled_tools = data.get("disabled_tools") or []
        except Exception:
            pass
            
    mcp_tool_names = list(set(t["function"]["name"] for t in tools if "function" in t))
    disk_tools = list(get_disk_tools())
    needs_restart = [dt for dt in disk_tools if dt not in mcp_tool_names]
    
    all_tools = list(set(mcp_tool_names + disk_tools))
    all_tools.sort()
    
    return jsonify({
        "all_tools": all_tools,
        "disabled_tools": disabled_tools,
        "needs_restart": needs_restart
    })

@webhook_app.route('/api/agent_tools', methods=['POST'])
def update_agent_tools():
    data = request.json
    agent_name = data.get('agent', 'Terry')
    disabled_tools = data.get('disabled_tools', [])
    
    agent_files_dir = os.path.join(FILE_DIR, "agents", agent_name)
    tools_yaml_path = os.path.join(agent_files_dir, "tools.yaml")
    
    os.makedirs(agent_files_dir, exist_ok=True)
    with open(tools_yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"disabled_tools": disabled_tools}, f)
        
    return jsonify({"status": "success"})


@webhook_app.route('/api/agent_skills', methods=['GET'])
def get_agent_skills():
    agent_name = request.args.get('agent', 'Terry')
    
    skills_dir = os.path.join(AI_WORKSPACE_DIR, "skills")
    disk_skills = []
    if os.path.exists(skills_dir):
        try:
            for skill_name in sorted(os.listdir(skills_dir)):
                skill_path = os.path.join(skills_dir, skill_name)
                if os.path.isdir(skill_path):
                    skill_file = os.path.join(skill_path, "SKILL.md")
                    if os.path.exists(skill_file):
                        disk_skills.append(skill_name)
        except Exception:
            pass
            
    agent_files_dir = os.path.join(FILE_DIR, "agents", agent_name)
    skills_yaml_path = os.path.join(agent_files_dir, "skills.yaml")
    
    disabled_skills = []
    if os.path.exists(skills_yaml_path):
        try:
            with open(skills_yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                disabled_skills = data.get("disabled_skills") or []
        except Exception:
            pass
            
    return jsonify({
        "all_skills": disk_skills,
        "disabled_skills": disabled_skills
    })

@webhook_app.route('/api/agent_skills', methods=['POST'])
def update_agent_skills():
    data = request.json
    agent_name = data.get('agent', 'Terry')
    disabled_skills = data.get('disabled_skills', [])
    
    agent_files_dir = os.path.join(FILE_DIR, "agents", agent_name)
    skills_yaml_path = os.path.join(agent_files_dir, "skills.yaml")
    
    os.makedirs(agent_files_dir, exist_ok=True)
    with open(skills_yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"disabled_skills": disabled_skills}, f)
        
    update_and_get_agent_skills(agent_name)
        
    return jsonify({"status": "success"})

@webhook_app.route('/api/process_viewer', methods=['GET'])
def process_viewer():
    bg_procs = []
    for p in subprocesses:
        try:
            args = p.args
            name = " ".join(args) if isinstance(args, list) else str(args)
            
            if "voice-detector.py" in name:
                display_name = "Voice Detector"
            elif "whatsapp.py" in name:
                display_name = "WhatsApp Gateway"
            elif "TUI.py" in name:
                display_name = "TUI Interface"
            elif "terminal.py" in name:
                display_name = "Terminal Shell"
            elif "npm" in name and "dev" in name:
                display_name = "Web UI Server"
            else:
                display_name = name

            status = "Running" if p.poll() is None else "Terminated"
            bg_procs.append({"name": display_name, "status": status, "pid": p.pid, "command": name})
        except Exception:
            pass

    with tool_executions_lock:
        tools_list = list(tool_executions_log.values())
        tools_list.sort(key=lambda x: x.get("start_time", ""), reverse=True)
        recent_tools = []
        for t in tools_list[:50]:
            t_copy = t.copy()
            if "output" in t_copy:
                del t_copy["output"]
            recent_tools.append(t_copy)

    return jsonify({
        "background_processes": bg_procs,
        "tool_executions": recent_tools
    })

@webhook_app.route('/api/tool_execution/<tool_call_id>', methods=['GET'])
def get_tool_execution(tool_call_id):
    with tool_executions_lock:
        if tool_call_id in tool_executions_log:
            return jsonify({"status": "success", "tool_execution": tool_executions_log[tool_call_id]})
        else:
            return jsonify({"status": "error", "message": "Tool execution not found"}), 404



def run_in_new_terminal(args, cwd=None):
    if isinstance(args, str):
        args = [sys.executable, args]
    if not args:
        return None

    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        try:
            return subprocess.Popen(args, creationflags=creationflags, cwd=cwd)
        except Exception as e:
            print(f"Warning: Failed to start script in new console on Windows: {e}")
            return None
    elif sys.platform == "darwin":
        import shlex
        cmd = " ".join(shlex.quote(arg) for arg in args)
        applescript = f'tell application "Terminal" to do script {shlex.quote(cmd)}'
        try:
            return subprocess.Popen(["osascript", "-e", applescript], cwd=cwd)
        except Exception as e:
            print(f"Warning: Failed to start script in new terminal on macOS: {e}")
            return None
    else:
        import shlex
        for term in ["gnome-terminal", "konsole", "xfce4-terminal", "lxterminal", "xterm"]:
            if shutil.which(term):
                try:
                    if term == "gnome-terminal":
                        return subprocess.Popen([term, "--"] + args, cwd=cwd)
                    else:
                        return subprocess.Popen([term, "-e"] + args, cwd=cwd)
                except Exception as e:
                    print(f"Warning: Failed to start script in terminal {term}: {e}")
        # Fallback to background process
        try:
            return subprocess.Popen(args, cwd=cwd)
        except Exception as e:
            print(f"Warning: Failed to start script as fallback background process on Linux: {e}")
            return None


def start_subprograms():
    if not os.path.exists(SUBPROGRAMS_DIR):
        return

    voice_script = os.path.join(SUBPROGRAMS_DIR, "voice", "voice-detector.py")
    whatsapp_script = os.path.join(SUBPROGRAMS_DIR, "whatsapp", "whatsapp.py")
    tui_script = os.path.join(SUBPROGRAMS_DIR, "TUI", "TUI.py")
    terminal_script = os.path.join(SUBPROGRAMS_DIR, "terminal", "terminal.py")
    web_ui_dir = os.path.join(SUBPROGRAMS_DIR, "web-ui")

    show_terminal = "--terminal" in sys.argv
    print(f"[*] Starting subprograms. show_terminal={show_terminal} (sys.argv={sys.argv})")

    if os.path.exists(voice_script):
        try:
            if show_terminal:
                proc = run_in_new_terminal([sys.executable, voice_script])
            else:
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                proc = subprocess.Popen(
                    [sys.executable, voice_script],
                    creationflags=creationflags,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            if proc:
                subprocesses.append(proc)
        except Exception as e:
            print(f"Warning: Failed to start voice script: {e}")

    if os.path.exists(whatsapp_script):
        try:
            if show_terminal:
                proc = run_in_new_terminal([sys.executable, whatsapp_script])
            else:
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                proc = subprocess.Popen(
                    [sys.executable, whatsapp_script],
                    creationflags=creationflags,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            if proc:
                subprocesses.append(proc)
        except Exception as e:
            print(f"Warning: Failed to start WhatsApp script: {e}")

    if os.path.exists(tui_script):
        proc = run_in_new_terminal([sys.executable, tui_script])
        if proc:
            subprocesses.append(proc)
        else:
            print("Warning: Failed to start TUI script in a new terminal.")

    if os.path.exists(web_ui_dir) and os.path.exists(os.path.join(web_ui_dir, "package.json")):
        npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
        try:
            if show_terminal:
                proc = run_in_new_terminal([npm_cmd, "run", "dev"], cwd=web_ui_dir)
            else:
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                proc = subprocess.Popen(
                    [npm_cmd, "run", "dev"], 
                    cwd=web_ui_dir,
                    creationflags=creationflags,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            if proc:
                subprocesses.append(proc)
        except Exception as e:
            print(f"Warning: Failed to start web UI: {e}")


def set_ui_target(target):
    global ui_target
    ui_target = target


def _ui_call(method_name, *args, **kwargs):
    if ui_target is None:
        return
    method = getattr(ui_target, method_name, None)
    if callable(method):
        method(*args, **kwargs)


def cleanup_subprocesses():
    print("Cleaning up subprocesses...")
    for proc in subprocesses:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                proc.terminate()
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
    import time
    time.sleep(0.1)
    for proc in subprocesses:
        try:
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass


def start_mcp_thread():
    global mcp_loop, mcp_restart_event
    mcp_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(mcp_loop)
    mcp_restart_event = asyncio.Event()
    
    async def run_mcp_client():
        global mcp_session, mcp_client_context
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(ROOT_DIR / "mcp_server.py")],
            env=os.environ.copy()
        )
        while True:
            print("Starting MCP server...", flush=True)
            try:
                mcp_client_context = stdio_client(server_params)
                async with mcp_client_context as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        
                        # Rebuild tools with pre-fetched schemas first
                        try:
                            result = await session.list_tools()
                            _build_tools(result.tools)
                            print("MCP tools rebuilt successfully on startup/reconnect.", flush=True)
                        except Exception as list_err:
                            print(f"Error pre-fetching MCP tools: {list_err}", flush=True)
                            
                        # Set session global variable only after tools are fully ready
                        mcp_session = session
                        print("MCP connection initialized successfully.", flush=True)
                            
                        # Monitor session status and look for restart requests or connection health
                        while not mcp_restart_event.is_set():
                            try:
                                await session.send_ping()
                            except Exception:
                                print("MCP server connection lost (ping failed).", flush=True)
                                break
                            await asyncio.sleep(0.5)
                        if mcp_restart_event.is_set():
                            print("MCP restart event detected.", flush=True)
            except Exception as e:
                print(f"MCP client connection failed/lost: {e}", flush=True)
            finally:
                mcp_session = None
                mcp_client_context = None
                mcp_restart_event.clear()
                
            print("Reconnecting MCP server in 1 second...", flush=True)
            await asyncio.sleep(1)
            
    mcp_loop.create_task(run_mcp_client())
    mcp_loop.run_forever()


def start_mcp_client():
    global mcp_thread
    mcp_thread = threading.Thread(target=start_mcp_thread, daemon=True)
    mcp_thread.start()


def get_mcp_tools():
    if not mcp_session:
        return []
    try:
        future = asyncio.run_coroutine_threadsafe(mcp_session.list_tools(), mcp_loop)
        result = future.result(timeout=5)
        return result.tools
    except Exception as e:
        print(f"Error fetching MCP tools: {repr(e)}", flush=True)
        return []


def call_mcp_tool(name: str, arguments: dict, agent_name: str = "Terry"):
    if not mcp_session:
        raise RuntimeError("MCP server not connected.")
        
    channel = getattr(request_context, "channel", "External")
    
    with active_tool_contexts_lock:
        active_tool_contexts[name] = {
            "channel": channel,
            "sender_id": getattr(request_context, "sender_id", None),
            "chat_id": getattr(request_context, "chat_id", None),
            "agent_name": agent_name
        }
        
    try:
        if name in ["add_memory", "remove_memory"]:
            arguments["agent_name"] = agent_name
        future = asyncio.run_coroutine_threadsafe(mcp_session.call_tool(name, arguments), mcp_loop)
        result = future.result(timeout=190)
        text_parts = []
        for item in result.content:
            if getattr(item, "type", None) == "text":
                text_parts.append(item.text)
            elif hasattr(item, "text"):
                text_parts.append(item.text)
            else:
                text_parts.append(str(item))
        return "\n".join(text_parts)
    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        return f"Error executing tool {name} via MCP: {error_msg}"
    finally:
        with active_tool_contexts_lock:
            active_tool_contexts.pop(name, None)


def get_embedding(text: str) -> list:
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


def load_chat_history(agent_name: str) -> list:
    history_file = os.path.join(FILE_DIR, "agents", agent_name, "session_chat_history.json")
    os.makedirs(os.path.dirname(history_file), exist_ok=True)
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_chat_history(agent_name: str, history_to_save: list):
    history_file = os.path.join(FILE_DIR, "agents", agent_name, "session_chat_history.json")
    os.makedirs(os.path.dirname(history_file), exist_ok=True)
    serializable_history = []
    for msg in history_to_save:
        if isinstance(msg, dict) and msg.get("role") == "system":
            continue
        if isinstance(msg, dict):
            serializable_history.append(msg)
        else:
            msg_dict = {"role": msg.role, "content": msg.content}
            if getattr(msg, "tool_calls", None):
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in msg.tool_calls
                ]
            serializable_history.append(msg_dict)
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(serializable_history, f, indent=4)


def archive_current_session(agent_name: str):
    current_history = load_chat_history(agent_name)
    if not current_history:
        return None

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    json_filename = f"session_{timestamp}.json"
    agent_archive_files_dir = os.path.join(FILE_DIR, "agents", agent_name, "archived-sessions")
    agent_archive_working_dir = os.path.join(AI_WORKSPACE_DIR, "agents", agent_name, "archived-sessions")
    os.makedirs(agent_archive_files_dir, exist_ok=True)
    os.makedirs(agent_archive_working_dir, exist_ok=True)

    json_filepath = os.path.join(agent_archive_files_dir, json_filename)
    with open(json_filepath, "w", encoding="utf-8") as f:
        json.dump(current_history, f, indent=4)

    recent_path = os.path.join(agent_archive_files_dir, "recent.json")
    with open(recent_path, "w", encoding="utf-8") as f:
        json.dump(current_history, f, indent=4)

    md_filename = f"session_{timestamp}.md"
    md_filepath = os.path.join(agent_archive_working_dir, md_filename)
    with open(md_filepath, "w", encoding="utf-8") as f:
        f.write(f"# Session Archive - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for msg in current_history:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            if content:
                f.write(f"### **{role}**\n{content}\n\n")
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    f.write(f"* Tool Call: Executed `{tc['function']['name']}` with args `{tc['function']['arguments']}`\n")
                f.write("\n")

    recent_md = os.path.join(agent_archive_working_dir, "recent.md")
    with open(recent_md, "w", encoding="utf-8") as f:
        f.write(f"# Session Archive - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for msg in current_history:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            if content:
                f.write(f"### **{role}**\n{content}\n\n")
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    f.write(f"* Tool Call: Executed `{tc['function']['name']}` with args `{tc['function']['arguments']}`\n")
                f.write("\n")
    return timestamp


def get_available_sessions(agent_name: str) -> list:
    agent_archive_files_dir = os.path.join(FILE_DIR, "agents", agent_name, "archived-sessions")
    if not os.path.exists(agent_archive_files_dir):
        return []
    files = glob.glob(os.path.join(agent_archive_files_dir, "session_*.json"))
    sessions = [os.path.basename(f).replace(".json", "") for f in files]
    sessions.sort(reverse=True)
    recent_file_path = os.path.join(agent_archive_files_dir, "recent.json")
    if os.path.exists(recent_file_path):
        sessions.insert(0, "recent")
    return sessions


def load_system_prompt(agent_name: str, user_query: str = "") -> str:
    agent_working_dir = os.path.join(AI_WORKSPACE_DIR, "agents", agent_name)
    agent_files_dir = os.path.join(FILE_DIR, "agents", agent_name)
    system_file = os.path.join(agent_working_dir, "SYSTEM.md")
    soul_file = os.path.join(agent_working_dir, "SOUL.md")
    memories_file = os.path.join(agent_working_dir, "KEY_MEMORIES.json")
    tools_md_file = os.path.join(agent_files_dir, "TOOLS.md")

    loaded_prompts = []
    
    # Load workspace skills
    try:
        skills_prompts = update_and_get_agent_skills(agent_name)
        if skills_prompts:
            loaded_prompts.append("## AVAILABLE SKILLS\n\n" + "\n\n---\n\n".join(skills_prompts))
    except Exception as e:
        print(f"Error loading skills: {e}")
    
    if os.path.exists(tools_md_file):
        try:
            with open(tools_md_file, "r", encoding="utf-8") as f:
                content_md = f.read().strip()
                if content_md:
                    loaded_prompts.append(content_md)
        except Exception:
            pass
    
    if os.path.exists(system_file):
        try:
            with open(system_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    loaded_prompts.append(content)
        except Exception:
            pass

    if os.path.exists(soul_file):
        try:
            with open(soul_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    loaded_prompts.append(content)
        except Exception:
            pass

    try:
        if os.path.exists(memories_file):
            with open(memories_file, "r", encoding="utf-8") as f:
                mems = json.load(f)
            if mems:
                if user_query:
                    query_vector = get_embedding(user_query)
                    if query_vector:
                        for m in mems:
                            m["score"] = cosine_similarity(query_vector, m.get("embedding", []))
                        mems.sort(key=lambda x: x.get("score", 0), reverse=True)
                relevant_mems = mems[:4]
                mem_text = "### ACTIVE RELEVANT MEMORIES:\n"
                for m in relevant_mems:
                    exp_str = f" (Expires: {m['expiry_date']})" if m.get('expiry_date') else ""
                    mem_text += f"- [ID: {m['id']}] {m['text']}{exp_str}\n"
                loaded_prompts.append(mem_text)
    except Exception:
        pass

    if loaded_prompts:
        return "\n\n\n\n".join(loaded_prompts)
    return ""


def task_complete(summary_of_work: str) -> str:
    return f"STATUS_SUCCESS: {summary_of_work}"


def task_failed(reason_for_failure: str) -> str:
    return f"STATUS_FAILED: {reason_for_failure}"


def delegate_to_subagent(task_description: str, agent_name: str = "Terry", reasoning_amount: str = "low", parent_tool_call_id: str = None) -> str:
    max_steps = 100
    steps = 0
    exit_tools_schemas = [
        {
            "type": "function",
            "function": {
                "name": "task_complete",
                "description": "Call this tool when you have successfully accomplished the task.",
                "parameters": {
                    "type": "object",
                    "properties": {"summary_of_work": {"type": "string"}},
                    "required": ["summary_of_work"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "task_failed",
                "description": "Call this tool if you encounter a critical blocker.",
                "parameters": {
                    "type": "object",
                    "properties": {"reason_for_failure": {"type": "string"}},
                    "required": ["reason_for_failure"]
                }
            }
        }
    ]
    agent_tool_schemas = update_and_get_agent_tools(agent_name)
    subagent_tools = agent_tool_schemas + exit_tools_schemas
    subagent_system = {
        "role": "system",
        "content": "You are an autonomous sub-agent. When successful, call task_complete; otherwise task_failed."
    }
    messages = [subagent_system, {"role": "user", "content": f"YOUR ASSIGNED TASK:\n{task_description}"}]
    while steps < max_steps:
        try:
            subagent_model = config.get("SUBAGENT_MODEL")
            if not subagent_model:
                agent_info = get_agent_info(agent_name)
                subagent_model = agent_info.get("AI_MODEL", config.get("DEFAULT_MODEL", "gpt-5.4-nano"))

            api_params = {
                "model": subagent_model,
                "messages": messages,
                "tools": subagent_tools,
                "tool_choice": "auto"
            }

            is_non_reasoning_model = (
                "gpt-4" in subagent_model or
                "gpt-3" in subagent_model or
                "davinci" in subagent_model
            )
            if not is_non_reasoning_model:
                api_params["max_completion_tokens"] = 4000
                if reasoning_amount:
                    api_params["reasoning_effort"] = reasoning_amount
            else:
                api_params["max_tokens"] = 4000

            try:
                response = client.chat.completions.create(**api_params)
            except Exception as api_err:
                err_str = str(api_err).lower()
                if "reasoning_effort" in err_str or "max_completion_tokens" in err_str or "unsupported parameter" in err_str or "extra parameters" in err_str or "unexpected keyword" in err_str:
                    api_params.pop("reasoning_effort", None)
                    if "max_completion_tokens" in err_str or "max_completion_tokens" not in api_params:
                        api_params.pop("max_completion_tokens", None)
                        api_params["max_tokens"] = 4000
                    response = client.chat.completions.create(**api_params)
                else:
                    raise api_err
        except Exception as e:
            return f"Subagent execution broken due to API error: {str(e)}"

        msg = response.choices[0].message
        if msg.content and parent_tool_call_id:
            with tool_executions_lock:
                if parent_tool_call_id in tool_executions_log:
                    if "subagent_events" not in tool_executions_log[parent_tool_call_id]:
                        tool_executions_log[parent_tool_call_id]["subagent_events"] = []
                    tool_executions_log[parent_tool_call_id]["subagent_events"].append({
                        "type": "thought",
                        "content": msg.content
                    })

        if not msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content or ""})
            steps += 1
            continue

        tool_calls_list = [{"id": tc.id, "type": tc.type, "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in msg.tool_calls]
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": tool_calls_list})
        for tool_call in msg.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)
            
            if parent_tool_call_id:
                with tool_executions_lock:
                    if parent_tool_call_id in tool_executions_log:
                        if "subagent_events" not in tool_executions_log[parent_tool_call_id]:
                            tool_executions_log[parent_tool_call_id]["subagent_events"] = []
                        tool_executions_log[parent_tool_call_id]["subagent_events"].append({
                            "type": "tool_call",
                            "tool": func_name,
                            "args": func_args
                        })
            try:
                if func_name == "delegate_to_subagent":
                    tool_output = "Error: Subagents are restricted from spawning recursive subagents."
                elif func_name == "task_complete":
                    report = func_args.get("summary_of_work", "No summary provided.")
                    return f"Subagent completed task successfully. BACKGROUND SUMMARY (DO NOT RE-RUN):\n```\n{report}\n```"
                elif func_name == "task_failed":
                    reason = func_args.get("reason_for_failure", "No reason specified.")
                    return f"Subagent reported a task failure. DIAGNOSTIC LOG (DO NOT RE-RUN):\n```\n{reason}\n```"
                elif func_name in available_functions:
                    if func_name == "delegate_to_subagent":
                        func_args["agent_name"] = agent_name
                    tool_output = available_functions[func_name](**func_args)
                else:
                    tool_output = call_mcp_tool(func_name, func_args, agent_name)
            except Exception as e:
                tool_output = f"Error executing tool {func_name}: {str(e)}"
            messages.append({"tool_call_id": tool_call.id, "role": "tool", "name": func_name, "content": str(tool_output)})
        steps += 1
    return f"Subagent execution failed: Reached maximum step limit ({max_steps}) without cleanly declaring complete or failed status."


def _build_tools(mcp_tools=None):
    global tools, available_functions
    
    # Fetch MCP tools
    if mcp_tools is None:
        mcp_tools = get_mcp_tools()
        
    new_tools = []
    for t in mcp_tools:
        new_tools.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.inputSchema
            }
        })
        
    # Add local delegate_to_subagent
    new_tools.append({
        "type": "function",
        "function": {
            "name": "delegate_to_subagent",
            "description": "Spawn an autonomous background subagent to handle multi-step workspace objectives. It runs independently with its own tools and isolated scratchpad context, reporting back with an explicit success summary or a structural diagnostic failure log.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_description": {
                        "type": "string",
                        "description": "The precise instructions, constraints, file directories, and clear definition of success for the subagent's task."
                    },
                    "reasoning_amount": {
                        "type": "string",
                        "description": "The reasoning level/effort to pass to reasoning-capable models (e.g. 'low', 'medium', 'high'). Defaults to 'low' if not specified.",
                        "enum": ["low", "medium", "high"]
                    }
                },
                "required": ["task_description"]
            }
        }
    })
    tools = new_tools
    
    available_functions = {
        "delegate_to_subagent": delegate_to_subagent,
        "task_complete": task_complete,
        "task_failed": task_failed,
    }



def get_disk_tools():
    core_tools_dir = os.path.join(MAIN_DIR, "tools")
    custom_tools_dir = os.path.join(AI_WORKSPACE_DIR, "custom-tools")
    disk_tools = set()
    
    for tools_dir in [core_tools_dir, custom_tools_dir]:
        if os.path.exists(tools_dir):
            for py_file in glob.glob(os.path.join(tools_dir, "*.py")):
                with open(py_file, "r", encoding="utf-8") as f:
                    try:
                        tree = ast.parse(f.read())
                        for node in ast.walk(tree):
                            if isinstance(node, ast.FunctionDef):
                                for dec in node.decorator_list:
                                    if isinstance(dec, ast.Call) and getattr(dec.func, 'value', None) and getattr(dec.func.value, 'id', None) == 'mcp' and getattr(dec.func, 'attr', None) == 'tool':
                                        disk_tools.add(node.name)
                                    elif isinstance(dec, ast.Attribute) and getattr(dec.value, 'id', None) == 'mcp' and getattr(dec, 'attr', None) == 'tool':
                                        disk_tools.add(node.name)
                    except Exception:
                        pass
    return disk_tools


def update_and_get_agent_tools(agent_name):
    global tools
    
    # If tools list is empty or only has the local delegate_to_subagent,
    # attempt to rebuild/re-fetch them from the MCP server to handle slow startups.
    if len(tools) <= 1:
        _build_tools()
        
    agent_files_dir = os.path.join(FILE_DIR, "agents", agent_name)
    tools_yaml_path = os.path.join(agent_files_dir, "tools.yaml")
    
    disabled_tools = []
    if os.path.exists(tools_yaml_path):
        try:
            with open(tools_yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                disabled_tools = data.get("disabled_tools") or []
        except Exception:
            pass
            
    with open(tools_yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"disabled_tools": disabled_tools}, f)
        
    mcp_tool_names = set(t["function"]["name"] for t in tools if "function" in t)
    disk_tools = get_disk_tools()
    needs_restart = disk_tools - mcp_tool_names
    
    current_tools = []
    disabled_tools_present = []
    agent_tool_schemas = []
    
    for t in tools:
        if "function" in t:
            name = t["function"]["name"]
            if name in disabled_tools:
                disabled_tools_present.append(name)
            else:
                current_tools.append(name)
                agent_tool_schemas.append(t)
        else:
            agent_tool_schemas.append(t)
            
    tools_md_path = os.path.join(agent_files_dir, "TOOLS.md")
    with open(tools_md_path, "w", encoding="utf-8") as f:
        f.write("### Tools Status\n\n")
        f.write("**Current tools:**\n")
        for t in current_tools: f.write(f"- {t}\n")
        if not current_tools: f.write("- None\n")
        f.write("\n**Disabled tools:**\n")
        for t in disabled_tools_present: f.write(f"- {t}\n")
        if not disabled_tools_present: f.write("- None\n")
        f.write("\n**Tools that require a restart:**\n")
        for t in needs_restart: f.write(f"- {t}\n")
        if not needs_restart: f.write("- None\n")
        
    return agent_tool_schemas


def update_and_get_agent_skills(agent_name: str) -> list:
    skills_dir = os.path.join(AI_WORKSPACE_DIR, "skills")
    disk_skills = []
    if os.path.exists(skills_dir):
        try:
            for skill_name in sorted(os.listdir(skills_dir)):
                skill_path = os.path.join(skills_dir, skill_name)
                if os.path.isdir(skill_path):
                    skill_file = os.path.join(skill_path, "SKILL.md")
                    if os.path.exists(skill_file):
                        disk_skills.append(skill_name)
        except Exception:
            pass

    agent_files_dir = os.path.join(FILE_DIR, "agents", agent_name)
    skills_yaml_path = os.path.join(agent_files_dir, "skills.yaml")
    
    disabled_skills = []
    if os.path.exists(skills_yaml_path):
        try:
            with open(skills_yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                disabled_skills = data.get("disabled_skills") or []
        except Exception:
            pass
            
    os.makedirs(agent_files_dir, exist_ok=True)
    with open(skills_yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"disabled_skills": disabled_skills}, f)
        
    enabled_skills = []
    disabled_skills_present = []
    
    for s in disk_skills:
        if s in disabled_skills:
            disabled_skills_present.append(s)
        else:
            enabled_skills.append(s)
            
    def get_skill_desc(s):
        skill_file = os.path.join(skills_dir, s, "SKILL.md")
        desc = ""
        if os.path.exists(skill_file):
            try:
                with open(skill_file, "r", encoding="utf-8") as sf:
                    content = sf.read().strip()
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1])
                        if isinstance(frontmatter, dict):
                            desc = frontmatter.get("description", "")
            except Exception:
                pass
        return desc

    skills_md_path = os.path.join(agent_files_dir, "SKILLS.md")
    with open(skills_md_path, "w", encoding="utf-8") as f:
        f.write("### Skills Status\n\n")
        f.write("**Enabled skills:**\n")
        for s in enabled_skills:
            desc = get_skill_desc(s)
            if desc:
                f.write(f"- {s} - {desc}\n")
            else:
                f.write(f"- {s}\n")
        if not enabled_skills:
            f.write("- None\n")
            
        f.write("\n**Disabled skills:**\n")
        for s in disabled_skills_present:
            desc = get_skill_desc(s)
            if desc:
                f.write(f"- {s} - {desc}\n")
            else:
                f.write(f"- {s}\n")
        if not disabled_skills_present:
            f.write("- None\n")
            
    loaded_skills_content = []
    for s in enabled_skills:
        skill_file = os.path.join(skills_dir, s, "SKILL.md")
        try:
            with open(skill_file, "r", encoding="utf-8") as sf:
                content = sf.read().strip()
            if content:
                body = content
                name = s
                desc = ""
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        try:
                            frontmatter = yaml.safe_load(parts[1])
                            if isinstance(frontmatter, dict):
                                name = frontmatter.get("name", name)
                                desc = frontmatter.get("description", "")
                            body = parts[2].strip()
                        except Exception:
                            pass
                
                skill_block = f"### SKILL: {name}"
                if desc:
                    skill_block += f" - {desc}"
                skill_block += f"\n{body}"
                loaded_skills_content.append(skill_block)
        except Exception:
            pass
            
    return loaded_skills_content


def get_agent_info(agent_name: str) -> dict:
    agent_working_dir = os.path.join(AI_WORKSPACE_DIR, "agents", agent_name)
    agent_config_file = os.path.join(agent_working_dir, "config.yaml")
    info = {
        "AI_MODEL": config.get("DEFAULT_MODEL", "gpt-5.4-nano"),
        "AI_NAME": agent_name,
    }
    if os.path.exists(agent_config_file):
        try:
            with open(agent_config_file, "r", encoding="utf-8") as f:
                agent_yaml = yaml.safe_load(f)
                if agent_yaml:
                    info.update(agent_yaml)
        except Exception:
            pass
    return info


def encode_image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def process_message(context_channel: str, clean_prompt_text: str, agent_name: str = "Terry", media_paths: list = None) -> str:
    request_context.channel = context_channel
    if media_paths is None:
        media_paths = []
    ui_text = clean_prompt_text
    if media_paths and context_channel != "Web":
        ui_text = f"🖼️ [Image Uploaded] {clean_prompt_text}"
    add_ui_update("user", context_channel, ui_text, agent_name)

    if clean_prompt_text.startswith("/"):
        command_parts = clean_prompt_text.split(" ", 1)
        command = command_parts[0].lower()
        arg = command_parts[1].strip() if len(command_parts) > 1 else ""
        if command == "/newsession":
            with chat_lock:
                archived_id = archive_current_session(agent_name)
                save_chat_history(agent_name, [])
                load_session_into_updates(agent_name)
            log_msg = f"Started a brand new session for agent {agent_name}."
            if archived_id:
                log_msg += f" (Archived as {archived_id})"
            add_ui_update("system", context_channel, log_msg, agent_name)
            return log_msg
        if command == "/clear":
            if context_channel != "TUI":
                return "Clear screen command only affects the main terminal view."
            add_ui_update("system", context_channel, "CLEAR", agent_name)
            return "Screen cleared."
        if command == "/loadsession":
            if not arg:
                err_msg = "Please provide a session name."
                add_ui_update("system", context_channel, err_msg, agent_name)
                return err_msg
            agent_archive_files_dir = os.path.join(FILE_DIR, "agents", agent_name, "archived-sessions")
            target_path = os.path.join(agent_archive_files_dir, f"{arg}.json")
            if not os.path.exists(target_path):
                err_msg = f"Target session file '{arg}.json' could not be located."
                add_ui_update("system", context_channel, err_msg, agent_name)
                return err_msg
            with chat_lock:
                try:
                    with open(target_path, "r", encoding="utf-8") as f:
                        loaded_data = json.load(f)
                    save_chat_history(agent_name, loaded_data)
                    load_session_into_updates(agent_name)
                    success_msg = f"Successfully restored session data from '{arg}'!"
                    add_ui_update("system", context_channel, success_msg, agent_name)
                    return success_msg
                except Exception as e:
                    err_msg = f"Failed parsing profile data: {str(e)}"
                    add_ui_update("system", context_channel, err_msg, agent_name)
                    return err_msg
        unknown_msg = f"Unknown command '{command}'"
        add_ui_update("system", context_channel, unknown_msg, agent_name)
        return unknown_msg

    agent_info = get_agent_info(agent_name)
    agent_model = agent_info["AI_MODEL"]
    agent_name_str = agent_info["AI_NAME"]

    import platform
    os_name = platform.system()
    if os_name == "Darwin":
        os_name = "MacOS"

    raw_system_content = load_system_prompt(agent_name, clean_prompt_text)
    system_prompt_message = {
        "role": "system",
        "content": (
            f"CURRENT TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"OPERATING SYSTEM: {os_name}\n"
            f"You are the agent: '{agent_name}'. Your configuration-specific directory is 'agents/{agent_name}'.\n"
            f"Your archived sessions are saved under 'agents/{agent_name}/archived-sessions'.\n"
            f"{raw_system_content}\n\n"
            f"CRITICAL CHANNEL PROTOCOL:\n"
            f"The user's current message arrived via the execution channel: '{context_channel}'.\n"
            f"- IMPORTANT: You have the exact current time provided above at the very top of your system prompt. Do NOT look for an external function, tool call, or file system check to answer questions about the date or time. Read it directly from the 'CURRENT TIME' property.\n"
            f"- If channel is 'Voice', reply normally; your output text is handled by TTS.\n"
            f"- If channel is 'WhatsApp', reply naturally to the message context.\n"
            f"- If channel is 'TUI', the user is manually typing on a keyboard inside the terminal.\n\n"
            f"WEATHER CONTEXT HANDLING PROTOCOL:\n"
            f"- When the user requests weather metrics, match the duration context seamlessly to 'get_weather':\n"
            f"  * Current conditions/Today -> forecast_days=1\n"
            f"  * Tomorrow -> forecast_days=2\n"
            f"  * This week/7 days -> forecast_days=7\n"
        )
    }

    if media_paths:
        content_blocks = [{"type": "text", "text": f"[{context_channel} Channel]: {clean_prompt_text}"}]
        for path in media_paths:
            if path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                try:
                    base64_image = encode_image_to_base64(path)
                    content_blocks.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    })
                except Exception as e:
                    print(f"Error encoding image {path}: {e}")
        user_message_to_append = {"role": "user", "content": content_blocks}
    else:
        user_message_to_append = {"role": "user", "content": f"[{context_channel} Channel]: {clean_prompt_text}"}

    with chat_lock:
        chat_history = load_chat_history(agent_name)
        
        # Self-heal chat history from any orphaned assistant tool calls
        fixed_history = []
        history_changed = False
        for i, msg in enumerate(chat_history):
            fixed_history.append(msg)
            if msg.get("role") == "assistant" and "tool_calls" in msg and msg["tool_calls"]:
                tc_ids = [tc["id"] for tc in msg["tool_calls"]]
                responded_ids = set()
                for j in range(i + 1, len(chat_history)):
                    next_msg = chat_history[j]
                    if next_msg.get("role") == "tool" and next_msg.get("tool_call_id") in tc_ids:
                        responded_ids.add(next_msg["tool_call_id"])
                    elif next_msg.get("role") != "tool":
                        break
                for tc_id in tc_ids:
                    if tc_id not in responded_ids:
                        tool_name = "unknown"
                        for tc in msg["tool_calls"]:
                            if tc["id"] == tc_id:
                                tool_name = tc.get("function", {}).get("name", "unknown")
                                break
                        dummy_msg = {
                            "tool_call_id": tc_id,
                            "role": "tool",
                            "name": tool_name,
                            "content": "Error: Tool execution was interrupted or cancelled."
                        }
                        fixed_history.append(dummy_msg)
                        history_changed = True
                        
        if history_changed:
            chat_history = fixed_history
            
        chat_history.append(user_message_to_append)
        save_chat_history(agent_name, chat_history)

    while True:
        with chat_lock:
            chat_history = load_chat_history(agent_name)
            api_payload = [system_prompt_message]
            for m in chat_history:
                clean_m = {"role": m["role"], "content": m.get("content", "")}
                if "tool_calls" in m:
                    clean_m["tool_calls"] = m["tool_calls"]
                if "tool_call_id" in m:
                    clean_m["tool_call_id"] = m["tool_call_id"]
                    clean_m["name"] = m["name"]
                api_payload.append(clean_m)
        try:
            agent_tool_schemas = update_and_get_agent_tools(agent_name)
            response = client.chat.completions.create(model=agent_model, messages=api_payload, tools=agent_tool_schemas, tool_choice="auto")
        except Exception as api_err:
            err_msg = f"[API Error]: {str(api_err)}"
            add_ui_update("system", context_channel, err_msg, agent_name)
            return err_msg

        response_message = response.choices[0].message
        if not response_message.tool_calls:
            final_text = response_message.content or ""
            with chat_lock:
                chat_history = load_chat_history(agent_name)
                chat_history.append({"role": "assistant", "content": final_text, "channel": context_channel})
                save_chat_history(agent_name, chat_history)
            if final_text:
                import re
                ui_text = final_text
                if context_channel == "Web":
                    def replace_file_tag(m):
                        fpath = m.group(1).replace("\\", "/")
                        name = os.path.basename(fpath)
                        import urllib.parse
                        url_path = urllib.parse.quote(fpath)
                        return f"📎 [{name}](/api/download?path={url_path})"
                    ui_text = re.sub(r'\[SEND_FILE:\s*(.+?)\]', replace_file_tag, ui_text)
                add_ui_update("agent", context_channel, ui_text, agent_name)
            return final_text

        tool_calls_list = [{"id": tc.id, "type": tc.type, "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in response_message.tool_calls]
        with chat_lock:
            chat_history = load_chat_history(agent_name)
            chat_history.append({"role": "assistant", "content": response_message.content or "", "tool_calls": tool_calls_list})
            save_chat_history(agent_name, chat_history)

        for tool_call in response_message.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)
            
            with tool_executions_lock:
                tool_executions_log[tool_call.id] = {
                    "id": tool_call.id,
                    "tool": func_name,
                    "agent": agent_name,
                    "args": func_args,
                    "status": "running",
                    "start_time": datetime.now().isoformat(),
                    "output": None,
                    "error": None
                }
                
            add_ui_update("system", context_channel, f"Tool Call: Executing {func_name}({func_args})", agent_name, tool_call_id=tool_call.id)
            error_str = None
            try:
                if func_name in available_functions:
                    if func_name == "delegate_to_subagent":
                        func_args["agent_name"] = agent_name
                        func_args["parent_tool_call_id"] = tool_call.id
                    tool_output = available_functions[func_name](**func_args)
                else:
                    tool_output = call_mcp_tool(func_name, func_args, agent_name)
            except Exception as e:
                tool_output = f"Error executing tool {func_name}: {str(e)}"
                error_str = str(e)
                
            with tool_executions_lock:
                if tool_call.id in tool_executions_log:
                    tool_executions_log[tool_call.id]["status"] = "error" if error_str else "completed"
                    tool_executions_log[tool_call.id]["end_time"] = datetime.now().isoformat()
                    tool_executions_log[tool_call.id]["output"] = str(tool_output)
                    if error_str:
                        tool_executions_log[tool_call.id]["error"] = error_str
                        
            with chat_lock:
                chat_history = load_chat_history(agent_name)
                chat_history.append({"tool_call_id": tool_call.id, "role": "tool", "name": func_name, "content": str(tool_output)})
                save_chat_history(agent_name, chat_history)


def run_webhook_server():
    import flask.cli
    flask.cli.show_server_banner = lambda *args: None
    webhook_app.run(host='127.0.0.1', port=5050, debug=False, use_reloader=False)


def init_backend():
    global config, client

    config = load_config()
    api_key = config.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key) if api_key else None

    os.makedirs(MASTER_DIR, exist_ok=True)
    os.makedirs(AI_WORKSPACE_DIR, exist_ok=True)
    os.makedirs(FILE_DIR, exist_ok=True)
    os.makedirs(RUBBISH_BIN_DIR, exist_ok=True)
    
    skills_dir = os.path.join(AI_WORKSPACE_DIR, "skills")
    os.makedirs(skills_dir, exist_ok=True)
    os.makedirs(os.path.join(AI_WORKSPACE_DIR, "custom-tools"), exist_ok=True)

    # Prepopulate default skills
    read_session_skill_dir = os.path.join(skills_dir, "read-archived-session")
    os.makedirs(read_session_skill_dir, exist_ok=True)
    read_session_skill_file = os.path.join(read_session_skill_dir, "SKILL.md")
    if not os.path.exists(read_session_skill_file):
        with open(read_session_skill_file, "w", encoding="utf-8") as f:
            f.write("""---
name: read-archived-session
description: Instructions for locating and reading archived chat sessions.
---

# Reading Archived Sessions

To successfully locate and read an archived session without losing structural context, execute these steps sequentially:
1. Invoke the `list_directory` tool with `relative_path='agents/{agent_name}/archived-sessions'` to display available sessions.
2. Depending on what the user requested, invoke `read_file` on `agents/{agent_name}/archived-sessions/recent.md` or a specific archived session file in that folder.
3. Output the necessary information to the user.
""")

    create_tool_skill_dir = os.path.join(skills_dir, "create-tool")
    os.makedirs(create_tool_skill_dir, exist_ok=True)
    create_tool_skill_file = os.path.join(create_tool_skill_dir, "SKILL.md")
    if not os.path.exists(create_tool_skill_file):
        with open(create_tool_skill_file, "w", encoding="utf-8") as f:
            f.write("""---
name: create-tool
description: Instructions for creating new tools for the assistant.
---

# Creating Custom Tools

To create tools, read `custom-tools/CUSTOM_TOOLS_CREATION_TUTORIAL.md` first.
""")

    # 1. Ensure agents directories exist
    agents_working_dir = os.path.join(AI_WORKSPACE_DIR, "agents")
    agents_files_dir = os.path.join(FILE_DIR, "agents")
    os.makedirs(agents_working_dir, exist_ok=True)
    os.makedirs(agents_files_dir, exist_ok=True)

    # Define default prompts (now globally defined as DEFAULT_SYSTEM_PROMPT and DEFAULT_SOUL_TEXT)


    # 3. Check if agents directory is empty; if so, create a default 'Terry' agent
    if not os.listdir(agents_working_dir):
        print("No agents found. Creating default 'Terry' agent...")
        main_working_dir = os.path.join(agents_working_dir, "Terry")
        os.makedirs(main_working_dir, exist_ok=True)
    
    # 4. Initialize files and clean memories for all agents
    agents_list = [d for d in os.listdir(agents_working_dir) if os.path.isdir(os.path.join(agents_working_dir, d))]
    
    for agent_dir in agents_list:
        agent_working_path = os.path.join(agents_working_dir, agent_dir)
        agent_files_path = os.path.join(agents_files_dir, agent_dir)
        
        os.makedirs(os.path.join(agent_working_path, "archived-sessions"), exist_ok=True)
        os.makedirs(os.path.join(agent_files_path, "archived-sessions"), exist_ok=True)

        tools_yaml = os.path.join(agent_files_path, "tools.yaml")
        if not os.path.exists(tools_yaml):
            with open(tools_yaml, "w", encoding="utf-8") as f:
                yaml.safe_dump({"disabled_tools": []}, f)

        skills_yaml = os.path.join(agent_files_path, "skills.yaml")
        if not os.path.exists(skills_yaml):
            with open(skills_yaml, "w", encoding="utf-8") as f:
                yaml.safe_dump({"disabled_skills": []}, f)
        update_and_get_agent_skills(agent_dir)

        # Initialize missing default files for any agent
        config_file = os.path.join(agent_working_path, "config.yaml")
        if not os.path.exists(config_file):
            agent_config = {
                "AI_MODEL": config.get("DEFAULT_MODEL", "gpt-5.4-nano"),
                "AI_NAME": agent_dir,
            }
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.safe_dump(agent_config, f)

        sys_file = os.path.join(agent_working_path, "SYSTEM.md")
        if not os.path.exists(sys_file):
            with open(sys_file, "w", encoding="utf-8") as f:
                f.write(DEFAULT_SYSTEM_PROMPT)

        soul_file = os.path.join(agent_working_path, "SOUL.md")
        if not os.path.exists(soul_file):
            with open(soul_file, "w", encoding="utf-8") as f:
                f.write(DEFAULT_SOUL_TEXT.format(agent_name=agent_dir))

        mem_file = os.path.join(agent_working_path, "KEY_MEMORIES.json")
        if not os.path.exists(mem_file):
            with open(mem_file, "w", encoding="utf-8") as f:
                json.dump([], f)
        else:
            try:
                with open(mem_file, "r", encoding="utf-8") as f:
                    memories = json.load(f)
                valid_memories = []
                today = datetime.now().date()
                for mem in memories:
                    if mem.get("expiry_date"):
                        try:
                            exp_date = datetime.strptime(mem["expiry_date"], "%Y-%m-%d").date()
                            if exp_date >= today:
                                valid_memories.append(mem)
                        except ValueError:
                            valid_memories.append(mem)
                    else:
                        valid_memories.append(mem)
                with open(mem_file, "w", encoding="utf-8") as f:
                    json.dump(valid_memories, f, indent=4)
            except Exception:
                pass

    # Load session history for the first available agent
    if agents_list:
        load_session_into_updates(agents_list[0])

    # Start MCP client and wait for handshake
    start_mcp_client()
    import time
    for _ in range(100):
        if mcp_session:
            break
        time.sleep(0.1)

    _build_tools()
    start_subprograms()


def main():
    init_backend()
    print("Multi-Agent backend running on http://127.0.0.1:5050")
    try:
        run_webhook_server()
    except KeyboardInterrupt:
        print("Shutting down backend.")
    finally:
        cleanup_subprocesses()


if __name__ == "__main__":
    main()
