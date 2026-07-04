import os
import time
import sys
from pathlib import Path
import threading
import re
import subprocess
import requests  
import yaml      
from neonize.client import NewClient
from neonize.events import MessageEv

# ---- AUDIO DEPENDENCIES ----
from faster_whisper import WhisperModel
from openai import OpenAI

# --------------------------------------
# Paths
# --------------------------------------
VALID_CONFIG = True

MAIN_DIR = Path(__file__).resolve().parent.parent.parent

MAIN_CONFIG = os.path.join(MAIN_DIR, "config.yaml")

MASTER_DIR = os.path.join(MAIN_DIR, r"master")
FILE_DIR = os.path.join(MASTER_DIR, r"files")

CONFIG_FILE = os.path.join(Path(__file__).resolve().parent, "whatsapp_config.yaml")

DEFAULT_CONFIG_TEXT = """# =================================================================
# WhatsApp Gateway Configuration
# =================================================================

# ID_ALLOWLIST: A list of authorized WhatsApp IDs allowed to use the AI.
ID_ALLOWLIST:
  - "example 1"
  - "example 2"

# ADDITIONAL_YOU_CHAT_PERMISSIONS: Set to true if you want the bot to reply to your 
# own messages in self-chats without having to include the prefix at the start of your message.
ADDITIONAL_YOU_CHAT_PERMISSIONS: true

# REPLY_PREFIX: The way the AI responds when not talking in a "you chat".
REPLY_PREFIX: "\\n{AI_NAME}:\\n\\n"

# SELF_CHAT_AGENT: The default agent handling self-chats (notebook window).
SELF_CHAT_AGENT: "Main"

# DEFAULT_AGENT: The fallback agent handling incoming chats if not specifically mapped.
DEFAULT_AGENT: "Main"

# CONTACT_AGENT_MAPPING: Maps specific contact phone numbers to agent names.
# Example:
# CONTACT_AGENT_MAPPING:
#   "447123456789": "Friday"
#   "15551234567": "Jarvis"
CONTACT_AGENT_MAPPING: {}
"""

WEBHOOK_URL = "http://127.0.0.1:5050/api/message"

def get_agent_ai_name(agent_name: str) -> str:
    agent_config_file = os.path.join(MAIN_DIR, "master", "working", "agents", agent_name, "config.yaml")
    if os.path.exists(agent_config_file):
        try:
            with open(agent_config_file, "r", encoding="utf-8") as f:
                agent_yaml = yaml.safe_load(f)
                if agent_yaml and "AI_NAME" in agent_yaml:
                    return str(agent_yaml["AI_NAME"])
        except Exception:
            pass
    return agent_name

def load_config():
    global VALID_CONFIG
    if not os.path.exists(CONFIG_FILE):
        import shutil
        example_file = CONFIG_FILE + ".example"
        if os.path.exists(example_file):
            shutil.copy(example_file, CONFIG_FILE)
            print(f"'{CONFIG_FILE}' was not found. Automatically copied from '{os.path.basename(example_file)}'.")
        else:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(DEFAULT_CONFIG_TEXT)
            print(f"'{CONFIG_FILE}' was not found. Generated a default template.")
            
        print("\n" + "="*60)
        print(f" ACTION REQUIRED: Please open and edit '{os.path.basename(CONFIG_FILE)}' now.")
        print(" Add your authorized WhatsApp IDs/phone numbers to the allowlist.")
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
        VALID_CONFIG = False
        return None

    # For backwards compatibility, populate default settings if missing
    if not isinstance(loaded_config, dict):
        loaded_config = {}

    modified = False
    if "ID_ALLOWLIST" not in loaded_config:
        loaded_config["ID_ALLOWLIST"] = []
        modified = True
    if "ADDITIONAL_YOU_CHAT_PERMISSIONS" not in loaded_config:
        loaded_config["ADDITIONAL_YOU_CHAT_PERMISSIONS"] = True
        modified = True
    if "REPLY_PREFIX" not in loaded_config:
        loaded_config["REPLY_PREFIX"] = "\n{AI_NAME}:\n\n"
        modified = True
    if "SELF_CHAT_AGENT" not in loaded_config:
        loaded_config["SELF_CHAT_AGENT"] = "Jarvis"
        modified = True
    if "DEFAULT_AGENT" not in loaded_config:
        loaded_config["DEFAULT_AGENT"] = "Main"
        modified = True
    if "CONTACT_AGENT_MAPPING" not in loaded_config:
        loaded_config["CONTACT_AGENT_MAPPING"] = {}
        modified = True

    if modified:
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                yaml.safe_dump(loaded_config, f)
        except Exception:
            pass

    return loaded_config

# Load and validate configuration safely
config = load_config()

if VALID_CONFIG and config is not None:
    ALLOWLIST = config["ID_ALLOWLIST"]
    ALLOW_OWN_MESSAGES = config["ADDITIONAL_YOU_CHAT_PERMISSIONS"]
    
    client = NewClient(os.path.join(Path(__file__).resolve().parent, "whatsapp_session.db"))

    # Global tracking variables
    my_personal_jid = None
    jid_cache = {}  

    # -----------------------------------------------------------------
    # Audio Subsystem Initialization
    # -----------------------------------------------------------------
    print("\n[*] Initializing Whisper STT Engine...")
    whisper_model = WhisperModel("small.en", compute_type="int8", device="cuda")
    
    print("[*] Initializing OpenAI TTS Engine...")
    openai_client = OpenAI() 
    
    TEMP_DIR = os.path.join(Path(__file__).resolve().parent, "temp_audio")
    os.makedirs(TEMP_DIR, exist_ok=True)

    def extract_user_id(jid_obj) -> str:
        """Extracts the clean phone number string from a WhatsApp JID object."""
        if not jid_obj:
            return ""
        if hasattr(jid_obj, "User") and jid_obj.User:
            return str(jid_obj.User)
        if hasattr(jid_obj, "user") and jid_obj.user:
            return str(jid_obj.user)
        jid_str = str(jid_obj)
        if "@" in jid_str:
            return jid_str.split("@")[0].split(":")[0]
        return jid_str

    # -----------------------------------------------------------------
    # Event Handler
    # -----------------------------------------------------------------
    
    # -----------------------------------------------------------------
    # Event Handler
    # -----------------------------------------------------------------
    @client.event(MessageEv)
    def on_message(client: NewClient, event: MessageEv):
        """Fires when any message event occurs on the account."""
        global my_personal_jid, jid_cache
        
        message_text = None
        audio_msg = None
        image_msg = None
        doc_msg = None
        parent_msg = None # Track the container
        
        # Check structural layout for Text vs Audio/Image/Doc attachments
        msg_obj = None
        if hasattr(event, "Message") and event.Message:
            msg_obj = event.Message
        elif hasattr(event, "message") and event.message:
            msg_obj = event.message

        if msg_obj:
            message_text = msg_obj.conversation or (
                msg_obj.extendedTextMessage.text if msg_obj.extendedTextMessage else None
            )
            
            def is_populated(media_msg):
                if not media_msg:
                    return False
                mimetype = getattr(media_msg, "mimetype", "")
                url = getattr(media_msg, "url", "")
                return bool(mimetype or url)

            a_msg = getattr(msg_obj, "audioMessage", None)
            i_msg = getattr(msg_obj, "imageMessage", None)
            d_msg = getattr(msg_obj, "documentMessage", None)
            
            if is_populated(a_msg):
                audio_msg = a_msg
            if is_populated(i_msg):
                image_msg = i_msg
            if is_populated(d_msg):
                doc_msg = d_msg
                
            parent_msg = msg_obj

        is_from_me = False
        chat_target = None
        sender_jid = None

        if hasattr(event, "Info") and event.Info:
            info_obj = event.Info
            if hasattr(info_obj, "MessageSource") and info_obj.MessageSource:
                src = info_obj.MessageSource
                is_from_me = getattr(src, "IsFromMe", False)
                chat_target = getattr(src, "Chat", None)
                sender_jid = getattr(src, "Sender", None)

        if not chat_target and hasattr(event, "info") and event.info:
            info_obj = event.info
            if hasattr(info_obj, "message_source") and info_obj.message_source:
                src = info_obj.message_source
                is_from_me = getattr(src, "is_from_me", False)
                chat_target = getattr(src, "chat", None)
                sender_jid = getattr(src, "sender", None)

        # Resolve true interacting ID
        sender_id = extract_user_id(sender_jid or chat_target)
        chat_id = extract_user_id(chat_target)

        # Identify if this is a self-chat notebook window
        is_self_chat = (sender_id == chat_id) or (chat_target and not sender_jid)

        default_agent = config.get("DEFAULT_AGENT", "Main")
        routed_agent = default_agent
        if is_self_chat:
            routed_agent = config.get("SELF_CHAT_AGENT", default_agent)
        else:
            mapping = config.get("CONTACT_AGENT_MAPPING", {})
            routed_agent = mapping.get(sender_id, default_agent)

        is_authorized = False
        requires_prefix = True

        # -----------------------------------------------------------------
        # Dynamic Authorization & Prefix Checking Rules
        # -----------------------------------------------------------------
        if is_from_me:
            if is_self_chat:
                if ALLOW_OWN_MESSAGES:
                    is_authorized = True
                    requires_prefix = False
                    my_personal_jid = chat_target
            else:
                if sender_id in ALLOWLIST:
                    is_authorized = True
                    requires_prefix = True
        else:
            if sender_id in ALLOWLIST:
                is_authorized = True
                requires_prefix = True

        if not is_authorized:
            return

        is_audio_interaction = bool(audio_msg)
        is_media_interaction = bool(image_msg or doc_msg)
        
        # Temp message text for prefix check before media is fully downloaded/transcribed
        temp_message_text = message_text or ""
        if image_msg and not temp_message_text:
            temp_message_text = getattr(image_msg, "caption", "") or "[Image Upload]"
        if doc_msg and not temp_message_text:
            temp_message_text = getattr(doc_msg, "caption", "") or f"[Document: {getattr(doc_msg, 'fileName', 'file')}]"
            
        has_prefix = temp_message_text.lower().startswith("to ai:")
        cleaned_text = temp_message_text
        if has_prefix:
            cleaned_text = temp_message_text[6:].lstrip()

        # Intercept `/agent <name>` command if sender has permission
        if cleaned_text.lower().startswith("/agent "):
            parts = cleaned_text.split(" ", 1)
            if len(parts) > 1:
                new_agent = parts[1].strip()
                if is_self_chat:
                    config["SELF_CHAT_AGENT"] = new_agent
                else:
                    if "CONTACT_AGENT_MAPPING" not in config:
                        config["CONTACT_AGENT_MAPPING"] = {}
                    config["CONTACT_AGENT_MAPPING"][sender_id] = new_agent
                
                try:
                    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                        yaml.safe_dump(config, f)
                    reply_msg = f"Your WhatsApp agent has been switched to: {new_agent}"
                except Exception as save_err:
                    reply_msg = f"Failed to switch agent: {save_err}"
                
                resolved_jid = jid_cache.get(sender_id) or sender_jid or chat_target
                if not resolved_jid:
                    resolved_jid = f"{sender_id}@s.whatsapp.net"
                client.send_message(resolved_jid, reply_msg)
                print(f" -> [Command Intercepted] Switched agent for {sender_id} to {new_agent}")
                return

        if requires_prefix and not has_prefix and not is_audio_interaction and not is_media_interaction:
            print(f" -> [Dropped] Message from {sender_id} to {chat_id} is missing 'To AI:' prefix.")
            return

        # -----------------------------------------------------------------
        # Media Download (Now Safe as user is authorized)
        # -----------------------------------------------------------------
        media_paths = []
        if audio_msg:
            print("\n -> [Voice Note Intercepted] Downloading media payload...")
            try:
                audio_bytes = client.download_any(parent_msg) 
                inbound_ogg = os.path.join(TEMP_DIR, "whatsapp_received.ogg")
                with open(inbound_ogg, "wb") as f:
                    f.write(audio_bytes)
                
                segments, _ = whisper_model.transcribe(inbound_ogg)
                message_text = " ".join([s.text for s in segments]).strip()
            except Exception as audio_err:
                print(f" -> [Audio Error] Failed downloading or transcribing voice note: {audio_err}")
                return
        elif image_msg:
            print("\n -> [Image Intercepted] Downloading image...")
            try:
                image_bytes = client.download_any(parent_msg)
                # Media goes to the agent's folder
                media_dir = os.path.join(MASTER_DIR, "working", "agents", routed_agent, "whatsapp_media")
                os.makedirs(media_dir, exist_ok=True)
                filename = f"img_{int(time.time())}.jpg"
                img_path = os.path.join(media_dir, filename)
                with open(img_path, "wb") as f:
                    f.write(image_bytes)
                media_paths = [img_path]
                message_text = image_msg.caption or "[Image Upload]"
            except Exception as img_err:
                print(f" -> [Image Error] Failed downloading image: {img_err}")
                return
        elif doc_msg:
            print("\n -> [Document Intercepted] Downloading document...")
            try:
                pending_doc_bytes = client.download_any(parent_msg)
                filename = doc_msg.fileName or ""
                if not filename:
                    ext = ".bin"
                    mimetype = doc_msg.mimetype or ""
                    if "pdf" in mimetype:
                        ext = ".pdf"
                    elif "sheet" in mimetype or "excel" in mimetype:
                        ext = ".xlsx"
                    elif "csv" in mimetype:
                        ext = ".csv"
                    elif "plain" in mimetype:
                        ext = ".txt"
                    filename = f"doc_{int(time.time())}{ext}"
                
                workspace_agent_dir = os.path.join(MASTER_DIR, "working", "agents", routed_agent)
                os.makedirs(workspace_agent_dir, exist_ok=True)
                doc_path = os.path.join(workspace_agent_dir, filename)
                with open(doc_path, "wb") as f:
                    f.write(pending_doc_bytes)
                print(f" -> [Document Saved] Stored file at: {doc_path}")
                
                message_text = f"[Uploaded Document: 'agents/{routed_agent}/{filename}']"
                if doc_msg.caption:
                    message_text += f"\n{doc_msg.caption}"
            except Exception as doc_err:
                print(f" -> [Document Error] Failed downloading document: {doc_err}")
                return

        if not message_text and not is_audio_interaction:
            return
            
        # Re-apply prefix removal for audio/image captions if they had it
        if has_prefix and message_text.lower().startswith("to ai:"):
            message_text = message_text[6:].lstrip()

        # -----------------------------------------------------------------
        # Immediate Global Logging (Shows for all intercepted texts)
        # -----------------------------------------------------------------
        print("\n--- [WhatsApp Event] New Message Intercepted ---")
        print(f" -> Message Text: '{message_text}'")
        print(f" -> Sender ID:    {sender_id}")
        print(f" -> Chat ID:      {chat_id}")
        print(f" -> Audio Input:  {is_audio_interaction}")
        
        print(f" -> [MATCH SUCCESS] Message authorized from {sender_id}! Routing via Webhook for agent '{routed_agent}'...")
        
        jid_cache[sender_id] = chat_target
        
        payload = {
            "channel": "WhatsApp",
            "text": message_text,
            "agent": routed_agent,
            "media_paths": media_paths
        }
        
        try:
            response = requests.post(WEBHOOK_URL, json=payload, timeout=60)
            
            if response.status_code == 200:
                ai_reply = response.json().get("reply", "").strip()
                
                if ai_reply:
                    resolved_jid = jid_cache.get(sender_id)
                    if not resolved_jid and sender_id:
                        resolved_jid = f"{sender_id}@s.whatsapp.net"
                    elif not resolved_jid:
                        resolved_jid = my_personal_jid

                    if resolved_jid:
                        if is_audio_interaction:
                            print(f" -> [Generating Audio Voice Note] Synthesizing speech via OpenAI TTS...")
                            temp_mp3 = os.path.join(TEMP_DIR, "tts_temp.mp3")
                            outbound_ogg = os.path.join(TEMP_DIR, "whatsapp_outbound.ogg")

                            # 1. Ask OpenAI's API to construct speech data
                            with openai_client.audio.speech.with_streaming_response.create(
                                model="gpt-4o-mini-tts",
                                voice="alloy",
                                input=ai_reply,
                                response_format="mp3"
                            ) as tts_response:
                                tts_response.stream_to_file(temp_mp3)

                            # 2. Use FFmpeg subprocess to scale audio to precise Ogg/Opus specs for WhatsApp PTT
                            ffmpeg_cmd = [
                                "ffmpeg", "-y", "-i", temp_mp3,
                                "-c:a", "libopus", "-b:a", "16k", "-vbr", "on",
                                outbound_ogg
                            ]
                            subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                            # 3. Read raw opus file bytes
                            with open(outbound_ogg, "rb") as audio_file:
                                opus_bytes = audio_file.read()

                            # 4. Wrap audio object and mark as a true voice note (ptt=True)
                            audio_message = client.build_audio_message(
                                opus_bytes,
                                ptt=True
                            )
                            audio_message.audioMessage.mimetype = "audio/ogg; codecs=opus"
                            print(f" -> [Sending Reply] Blasting voice note back to: {resolved_jid}")
                            client.send_message(resolved_jid, audio_message)

                            # Cleanup execution footprints safely
                            try:
                                os.remove(temp_mp3)
                                os.remove(outbound_ogg)
                            except OSError:
                                pass
                        else:
                            print(f" -> [Sending Reply] Mailing text response back to: {resolved_jid}")
                            agent_ai_name = get_agent_ai_name(routed_agent)
                            prefix_template = str(config.get("REPLY_PREFIX", "\n{AI_NAME}:\n\n"))
                            prefix = prefix_template.replace("{AI_NAME}", agent_ai_name)
                            full_reply = f"{prefix}{ai_reply}"
                            full_reply = re.sub(r'\*+', '*', full_reply)
                            client.send_message(resolved_jid, full_reply)
                    else:
                        print(" -> [Error] JID resolution initialization pending.")
            else:
                print(f" -> [Error] Webhook responded with status code: {response.status_code}")
                
        except Exception as e:
            print(f" -> [Error] Failed executing webhook message exchange: {e}")

    def main():
        print("=" * 60)
        print(" WhatsApp Multi-User Gateway Active (Voice + Webhook Mode)")
        print("=" * 60)
        
        print("\n[*] Connecting to WhatsApp...")
        client.connect()

if __name__ == "__main__":
    if VALID_CONFIG:
        main()