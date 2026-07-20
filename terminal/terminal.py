import sys
import requests
import time
import threading
import os
import yaml
from pathlib import Path

AGENTS_URL = "http://127.0.0.1:5050/api/agents"
MESSAGE_URL = "http://127.0.0.1:5050/api/message"

MAIN_DIR = Path(__file__).resolve().parent.parent

def load_channel_protocol(channel_name):
    channels_file = os.path.join(MAIN_DIR, "channels.yaml")
    if os.path.exists(channels_file):
        try:
            with open(channels_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return data.get(channel_name, {})
        except Exception:
            pass
    return {}

def get_available_agents():
    try:
        response = requests.get(AGENTS_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            agents = data.get("agents", [])
            return list(agents)
    except Exception:
        pass
    return []

def get_current_update_id(agent):
    try:
        response = requests.get(f"http://127.0.0.1:5050/api/updates?since=0&agent={agent}", timeout=5)
        if response.status_code == 200:
            updates = response.json().get("updates", [])
            if updates:
                return max(u["id"] for u in updates) + 1
    except Exception:
        pass
    return 0

def poll_and_print_updates(agent, start_id, stop_event, print_lock, agent_response_received, auth_needed_event):
    since = start_id
    printed_updates = set()
    while not stop_event.is_set():
        try:
            resp = requests.get(f"http://127.0.0.1:5050/api/updates?since={since}&agent={agent}", timeout=2)
            if resp.status_code == 200:
                updates = resp.json().get("updates", [])
                for u in updates:
                    u_id = u["id"]
                    if u_id not in printed_updates:
                        printed_updates.add(u_id)
                        content = u.get("content", "")
                        u_type = u.get("type", "")
                        
                        if content == "CLEAR":
                            continue
                            
                        with print_lock:
                            if u_type == "agent":
                                print(f"\n{content}")
                                agent_response_received[0] = True
                            elif u_type == "system":
                                print(f"\n{content}")
                                if "⚠️ Tool Authorization" in content:
                                    auth_needed_event.set()
                        
                        since = max(since, u_id + 1)
        except Exception:
            pass
        time.sleep(0.5)

def print_normal_auth_message(agent):
    try:
        resp = requests.get(f"http://127.0.0.1:5050/api/updates?since=0&agent={agent}", timeout=5)
        if resp.status_code == 200:
            updates = resp.json().get("updates", [])
            for u in reversed(updates):
                if u.get("type") == "system" and "⚠️ Tool Authorization" in u.get("content", ""):
                    print(f"\n{u['content']}")
                    return
    except Exception:
        pass
    print(f"\n⚠️ Tool Authorization is pending for agent '{agent}'. Please reply with 'yes', 'accept', or 'go' to allow the action, or 'no'/'cancel' to deny it.")

def get_user_input(prompt_msg, result_list):
    try:
        result_list.append(input(prompt_msg))
    except Exception:
        pass

def execute_action(agent, prompt, action="ask"):
    # Get current update ID before sending the request
    last_id = get_current_update_id(agent)

    # Start polling updates in a background thread
    stop_event = threading.Event()
    print_lock = threading.Lock()
    agent_response_received = [False]
    auth_needed_event = threading.Event()
    
    poll_thread = threading.Thread(
        target=poll_and_print_updates,
        args=(agent, last_id, stop_event, print_lock, agent_response_received, auth_needed_event),
        daemon=True
    )
    poll_thread.start()

    payload = {
        "text": prompt,
        "agent": agent,
        "channel": "Terminal",
        "protocol": load_channel_protocol("Terminal")
    }
    
    request_result = {}
    def run_post():
        try:
            response = requests.post(MESSAGE_URL, json=payload)
            request_result["reply"] = response.json().get("reply", "") if response.status_code == 200 else ""
        except Exception as exc:
            request_result["reply"] = f"Error communicating with server: {exc}"

    req_thread = threading.Thread(target=run_post, daemon=True)
    req_thread.start()

    input_thread = None
    input_result = []

    while req_thread.is_alive():
        if auth_needed_event.is_set():
            if not input_thread or not input_thread.is_alive():
                input_result = []
                input_thread = threading.Thread(
                    target=get_user_input,
                    args=("", input_result),
                    daemon=True
                )
                input_thread.start()
            
            while req_thread.is_alive() and input_thread.is_alive():
                time.sleep(0.1)
                
            if input_result:
                user_response = input_result[0].strip()
                try:
                    requests.post(
                        MESSAGE_URL, 
                        json={
                            "text": user_response,
                            "agent": agent,
                            "channel": "Terminal",
                            "protocol": load_channel_protocol("Terminal")
                        },
                        timeout=10
                    )
                except Exception:
                    pass
                auth_needed_event.clear()
                input_thread = None
        else:
            time.sleep(0.1)

    req_thread.join()
    reply_text = request_result.get("reply", "")

    # Check for special replies
    if "⚠️ Tool Authorization is pending" in reply_text:
        stop_event.set()
        poll_thread.join()
        print_normal_auth_message(agent)
        
        # Now prompt the user for response inline!
        try:
            user_response = input().strip()
            if user_response:
                last_id = get_current_update_id(agent)
                stop_event = threading.Event()
                agent_response_received = [False]
                auth_needed_event = threading.Event()
                
                poll_thread = threading.Thread(
                    target=poll_and_print_updates,
                    args=(agent, last_id, stop_event, print_lock, agent_response_received, auth_needed_event),
                    daemon=True
                )
                poll_thread.start()
                
                payload = {
                    "text": user_response,
                    "agent": agent,
                    "channel": "Terminal",
                    "protocol": load_channel_protocol("Terminal")
                }
                response = requests.post(MESSAGE_URL, json=payload)
                response_json = response.json() if response.status_code == 200 else {}
                reply_text2 = response_json.get("reply", "")
                
                if reply_text2 == "Tool Authorization approved.":
                    while not agent_response_received[0]:
                        time.sleep(0.1)
                else:
                    time.sleep(0.3)
                    if not agent_response_received[0] and reply_text2:
                        print(f"\n{reply_text2}")
                        
                stop_event.set()
                poll_thread.join()
        except Exception as exc:
            print(f"Error: {exc}")
        return
        
    elif reply_text == "Tool Authorization approved.":
        # Wait for the agent's actual response to be printed
        while not agent_response_received[0]:
            time.sleep(0.1)
        stop_event.set()
        poll_thread.join()
        
    else:
        # Normal reply or tool authorization denied
        time.sleep(0.3)
        stop_event.set()
        poll_thread.join()
        
        if not agent_response_received[0] and reply_text:
            print(f"\n{reply_text}")

def run_interactive_session(agent_list):
    #print("=" * 60)
    #print("          OpenDoor Interactive Terminal Client          ")
    #print("=" * 60)
    #print(f"Available agents: {', '.join(agent_list)}")
    
    default_agent = "Terry" if "Terry" in agent_list else agent_list[0]
    try:
        agent = input(f"Select agent: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
        return
        
    if not agent:
        agent = default_agent
    if agent not in agent_list:
        print(f"Warning: Agent '{agent}' is not in the available agents list. Attempting to connect...")
        
    print(f"\nConnected to '{agent}'. Type 'exit' or 'quit' to end the session.")
    print("-" * 60)
    
    while True:
        try:
            prompt = input(f"\n{agent}> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting session...")
            break
            
        if prompt.lower() in ["exit", "quit"]:
            break
        if not prompt:
            continue
            
        execute_action(agent, prompt)

def print_help():
    print("OpenDoor CLI")
    print("\nUsage:")
    print("  opendoor launch/start/run/server        Start the server in the background")
    print("                                          (use --terminal to keep in foreground)")
    print("  opendoor stop                           Stop the background server and all subprograms")
    print("  opendoor chat                           Start interactive terminal chat")
    print("  opendoor ask/tell [agent] [prompt]      Chat to the agent and print the response")
    print("  opendoor setup                          Run the initial setup wizard")
    print("  opendoor configure/config               Run the configuration wizard")
    print("  opendoor update                         Check for updates")
    
def stop_server():
    import urllib.request
    import json
    import subprocess
    
    print("[*] Attempting to stop OpenDoor server...")
    stopped = False
    
    # 1. Try sending a stop request to the running coordinator server
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:5050/api/stop",
            method="POST",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode('utf-8'))
            print(f"[+] Server response: {data.get('message', 'Stopping...')}")
            stopped = True
    except Exception:
        # Server might be offline or hung
        pass

    # 2. Check and clean up PID file
    pid_file = os.path.join(MAIN_DIR, "opendoor.pid")
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            
            if pid > 0:
                print(f"[*] Found PID file with PID {pid}. Terminating process...")
                if os.name == "nt":
                    # taskkill /F /T terminates the process and its children
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    try:
                        os.killpg(os.getpgid(pid), 15)
                    except Exception:
                        try:
                            os.kill(pid, 15)
                        except Exception:
                            pass
                print(f"[+] Terminated process {pid}.")
                stopped = True
        except Exception as e:
            print(f"[-] Error while killing process from PID file: {e}")
        finally:
            if os.path.exists(pid_file):
                try:
                    os.remove(pid_file)
                except Exception:
                    pass
                    
    if stopped:
        print("[+] OpenDoor stopped successfully.")
    else:
        print("[-] OpenDoor is not running.")

def main():
    arguments = sys.argv[1:]
    
    if not arguments:
        print_help()
        return

    action = arguments[0].lower()

    if action in ["help", "--help", "-h"]:
        print_help()
        return

    if action == "stop":
        stop_server()
        return

    if action == "chat":
        agent_list = get_available_agents()
        if not agent_list:
            print("Error: Could not connect to the server. Make sure the server is running on http://127.0.0.1:5050")
            return
        run_interactive_session(agent_list)
        return

    if action in ["ask", "tell", "accept", "deny"]:
        agent_list = get_available_agents()
        if not agent_list:
            print("Error: Could not connect to the server. Make sure the server is running on http://127.0.0.1:5050")
            return
            
        if len(arguments) > 1:
            agent = arguments[1]
        else:
            agent = "Terry"
            
        if agent in agent_list:
            if action in ["ask", "tell"]:
                prompt = " ".join(arguments[2:])
                if not prompt:
                    print(f"Usage: opendoor {action} [agent] [prompt]")
                    return
            else:
                prompt = action  # "accept" or "deny"

            execute_action(agent, prompt, action)
        else:
            print(f"Agent '{agent}' was not found")
    else:
        print(f"Unknown action '{action}'")
        print_help()

if __name__ == "__main__":
    main()
