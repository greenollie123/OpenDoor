import os
import time
import sys
from pathlib import Path

# Force UTF-8 encoding for standard streams to prevent UnicodeEncodeError in libraries like segno on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
try:
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

import threading
import re
import subprocess
import requests  
import yaml      
import sqlite3
from neonize.client import NewClient
from neonize.events import MessageEv

# ---- CTYPES BUG PATCH FOR NEONIZE ----
# Neonize's Bytes ctypes structure defines ptr as c_char_p, which causes self.ptr to be truncated at the first null byte.
# Using ctypes.string_at(self.ptr, self.size) then reads from the address of the truncated bytes object, returning corrupt/garbage memory.
# We patch get_bytes to cast the structure to one with a c_void_p to get the true memory address.
import ctypes
try:
    from neonize._binder import Bytes
    class BytesVoid(ctypes.Structure):
        _fields_ = [("ptr", ctypes.c_void_p), ("size", ctypes.c_size_t)]
    
    def get_bytes_patched(self):
        void_struct = ctypes.cast(ctypes.pointer(self), ctypes.POINTER(BytesVoid)).contents
        return ctypes.string_at(void_struct.ptr, void_struct.size)
    
    Bytes.get_bytes = get_bytes_patched
except Exception as patch_err:
    print(f"[*] Warning: Failed to apply Neonize ctypes memory patch: {patch_err}")


# ---- AUDIO DEPENDENCIES ----
from faster_whisper import WhisperModel
from openai import OpenAI
import litellm

# --------------------------------------
# Paths
# --------------------------------------
VALID_CONFIG = True

MAIN_DIR = Path(__file__).resolve().parent.parent.parent

MAIN_CONFIG = os.path.join(MAIN_DIR, "config.yaml")

MASTER_DIR = os.path.join(MAIN_DIR, r"master")
FILE_DIR = os.path.join(MASTER_DIR, r"files")

CONFIG_FILE = os.path.join(Path(__file__).resolve().parent, "whatsapp_config.yaml")

WEBHOOK_URL = "http://127.0.0.1:5050/api/message"

def get_agent_ai_name(agent_name: str) -> str:
    agent_config_file = os.path.join(MAIN_DIR, "master", "files", "agents", agent_name, "config.yaml")
    if not os.path.exists(agent_config_file):
        fallback_file = os.path.join(MAIN_DIR, "master", "working", "agents", agent_name, "config.yaml")
        if os.path.exists(fallback_file):
            agent_config_file = fallback_file
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
            print(f"Error: '{CONFIG_FILE}' and its template '{os.path.basename(example_file)}' are both missing.")
            print("Please restore the config template or create whatsapp_config.yaml manually.")
            print("\nPress ENTER to close...")
            input()
            VALID_CONFIG = False
            return None
            
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

    # For backwards compatibility, merge loaded config with in-memory defaults.
    # This avoids rewriting the config file on disk and stripping comments.
    if not isinstance(loaded_config, dict):
        loaded_config = {}

    defaults = {
        "ID_ALLOWLIST": [],
        "ADDITIONAL_YOU_CHAT_PERMISSIONS": True,
        "REPLY_PREFIX": "\n{AI_NAME}:\n\n",
        "SELF_CHAT_AGENT": "Terry",
        "DEFAULT_AGENT": "Terry",
        "AGENT_MAPPING": {},
        "TRIGGER_PREFIX": "to ai:"
    }

    # Automatically migrate legacy CONTACT_AGENT_MAPPING to AGENT_MAPPING
    if isinstance(loaded_config, dict):
        if "CONTACT_AGENT_MAPPING" in loaded_config:
            if "AGENT_MAPPING" not in loaded_config:
                loaded_config["AGENT_MAPPING"] = loaded_config.pop("CONTACT_AGENT_MAPPING")
            else:
                loaded_config.pop("CONTACT_AGENT_MAPPING", None)

    return {**defaults, **loaded_config}

def normalize_phone_number(val) -> str:
    """Normalizes a phone number or WhatsApp ID by extracting only its digits."""
    if val is None:
        return ""
    val_str = str(val).strip()
    if "@" in val_str:
        val_str = val_str.split("@")[0].split(":")[0]
    return re.sub(r"\D", "", val_str)

def jid_to_str(jid_obj) -> str:
    """Converts a neonize JID protobuf object into a clean standard WhatsApp JID string."""
    if jid_obj is None:
        return ""
    user = getattr(jid_obj, "User", None) or getattr(jid_obj, "user", None) or ""
    server = getattr(jid_obj, "Server", None) or getattr(jid_obj, "server", None) or ""
    device = getattr(jid_obj, "Device", 0) or getattr(jid_obj, "device", 0) or 0
    
    if not user:
        return str(jid_obj)
        
    res = str(user)
    if device:
        res += f":{device}"
    if server:
        res += f"@{server}"
    return res

def db_get_pn_from_lid(lid_val: str) -> str:
    """Queries the local sqlite database to resolve a phone number from an LID."""
    if not lid_val:
        return ""
    lid_clean = lid_val.split("@")[0].split(":")[0]
    db_path = os.path.join(Path(__file__).resolve().parent, "whatsapp_session.db")
    if not os.path.exists(db_path):
        return ""
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT pn FROM whatsmeow_lid_map WHERE lid = ?;", (lid_clean,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return str(row[0])
    except Exception as e:
        print(f" -> [DEBUG] Database LID resolution error: {e}")
    return ""

def safe_send_message(client, resolved_jid, message, **kwargs):
    """Sends a message using client.send_message, catching wire format parsing errors since they still deliver successfully."""
    try:
        return client.send_message(resolved_jid, message, **kwargs)
    except Exception as e:
        err_msg = str(e)
        if "Wire format was corrupt" in err_msg or "Error parsing message" in err_msg:
            # print(" -> [Info] Message sent successfully (ignored neonize return-value parsing error).")
            return None
        raise e

# Load and validate configuration safely
config = load_config()

if VALID_CONFIG and config is not None:
    ALLOWLIST = [normalize_phone_number(item) for item in config.get("ID_ALLOWLIST", []) if item]
    ALLOW_OWN_MESSAGES = config["ADDITIONAL_YOU_CHAT_PERMISSIONS"]
    
    client = NewClient(os.path.join(Path(__file__).resolve().parent, "whatsapp_session.db"))

    @client.qr
    def on_qr(client, data_qr: bytes):
        qr_path = os.path.join(Path(__file__).resolve().parent, "whatsapp_qr.png")
        qr_txt_path = os.path.join(Path(__file__).resolve().parent, "whatsapp_qr.txt")
        try:
            with open(qr_txt_path, "wb") as f_txt:
                f_txt.write(data_qr)
        except Exception as e:
            print(f"[-] Error saving QR text: {e}")
        try:
            import segno
            qr = segno.make_qr(data_qr)
            qr.save(qr_path, scale=5)
            print(f"\n[!] QR Code received! Saved to image: {qr_path}")
            print("[!] Please open this image and scan it with your phone's WhatsApp Linked Devices.")
            try:
                qr.terminal(compact=True)
            except Exception:
                try:
                    qr.terminal(compact=False)
                except Exception:
                    print("[!] (Terminal print skipped due to encoding limits. Please use the saved PNG.)")
        except Exception as e:
            print(f"[-] Error displaying/saving QR code: {e}")

    # Global tracking variables
    my_personal_jid = None
    jid_cache = {}  
    active_approvals = {}  
    audio_chats = {}


    # -----------------------------------------------------------------
    # Audio Subsystem Initialization
    # -----------------------------------------------------------------
    print("\n[*] Initializing STT Engine...")
    stt_model_config = {}
    models_file = os.path.join(MAIN_DIR, "models.yaml")
    if os.path.exists(models_file):
        try:
            with open(models_file, "r", encoding="utf-8") as f:
                m_cfg = yaml.safe_load(f) or {}
                stt_model_config = m_cfg.get("STT_MODEL", {})
        except Exception as e:
            print(f"[*] Warning: Failed to read models.yaml in WhatsApp gateway: {e}")

    stt_model_name = stt_model_config.get("model", "faster-whisper/small.en")
    
    whisper_model = None
    if stt_model_name.startswith("faster-whisper/"):
        model_size = stt_model_name.replace("faster-whisper/", "")
        print(f"[*] Initializing local faster-whisper model '{model_size}'...")
        whisper_model = WhisperModel(model_size, compute_type="int8", device="auto")
    else:
        print(f"[*] Configured for LiteLLM STT using model '{stt_model_name}'...")
    
    print("[*] Initializing TTS Engine...")
    tts_model_config = {}
    models_file = os.path.join(MAIN_DIR, "models.yaml")
    if os.path.exists(models_file):
        try:
            with open(models_file, "r", encoding="utf-8") as f:
                m_cfg = yaml.safe_load(f) or {}
                tts_model_config = m_cfg.get("TTS_MODEL", {})
        except Exception as e:
            print(f"[*] Warning: Failed to read models.yaml in WhatsApp gateway: {e}")

    tts_model_name = tts_model_config.get("model", "openai/tts-1")
    tts_voice = tts_model_config.get("voice", "alloy")
    tts_api_key = tts_model_config.get("api_key")
    tts_api_base = tts_model_config.get("api_base")

    # Fallback key check
    if not tts_api_key:
        tts_api_key = os.environ.get("OPENAI_API_KEY")
    if not tts_api_key and os.path.exists(models_file):
        try:
            with open(models_file, "r", encoding="utf-8") as f:
                m_cfg = yaml.safe_load(f) or {}
            for m_id in ["DEFAULT_MODEL", "DEFAULT_SUBAGENT_MODEL", "SUBAGENT_MODEL", "EMBEDDING_MODEL"]:
                m_info = m_cfg.get(m_id, {})
                m_name = m_info.get("model", "")
                m_k = m_info.get("api_key", "")
                if m_k and ("gpt" in m_name.lower() or "openai" in m_name.lower() or "text-embedding" in m_name.lower()):
                    tts_api_key = m_k
                    break
        except Exception:
            pass

    if not tts_api_key:
        print("[*] Warning: No API key was found for TTS. WhatsApp TTS engine will be unavailable.") 
    
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
            if msg_obj.HasField('pollUpdateMessage'):
                try:
                    original_msg_id = msg_obj.pollUpdateMessage.pollCreationMessageKey.ID
                    print(f"[*] Received poll update for message ID: {original_msg_id}")
                    print(f"[*] Active approvals: {list(active_approvals.keys())}")
                    if original_msg_id in active_approvals:
                        approval_id = active_approvals[original_msg_id]
                        decrypted_vote = client.decrypt_poll_vote(event)
                        
                        import hashlib
                        action = None
                        print(f"[*] Selected option hashes: {[opt.hex() for opt in decrypted_vote.selectedOptions]}")
                        print(f"[*] Expected Approve hash: {hashlib.sha256(b'Approve').digest().hex()}")
                        print(f"[*] Expected Deny hash: {hashlib.sha256(b'Deny').digest().hex()}")
                        for option in decrypted_vote.selectedOptions:
                            hash_approve = hashlib.sha256(b"Approve").digest()
                            hash_deny = hashlib.sha256(b"Deny").digest()
                            if option == hash_approve:
                                action = "approved"
                                break
                            elif option == hash_deny:
                                action = "denied"
                                break
                        
                        if action:
                            print(f"[*] WhatsApp User voted '{action}' for command approval ID {approval_id}")
                            try:
                                requests.post(
                                    "http://127.0.0.1:5050/api/approve",
                                    json={"approval_id": approval_id, "action": action},
                                    timeout=5
                                )
                                active_approvals.pop(original_msg_id, None)
                            except Exception as ex:
                                print(f"[-] Failed to send vote callback to coordinator: {ex}")
                        else:
                            print("[-] Vote option hash did not match Approve or Deny hashes.")
                    else:
                        print(f"[-] Poll original message ID '{original_msg_id}' not found in active approvals.")
                except Exception as e:
                    print(f"[-] Error processing WhatsApp poll vote: {e}")
                return

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
        interacting_jid = sender_jid or chat_target
        sender_phone = ""
        resolved_phone_jid = None
        
        is_lid = False
        if interacting_jid:
            server = getattr(interacting_jid, "Server", "") or getattr(interacting_jid, "server", "") or ""
            if server == "lid":
                is_lid = True
                
        if is_lid:
            raw_lid = extract_user_id(interacting_jid)
            # Try database lookup (avoids neonize protobuf wire format corrupt bug)
            sender_phone = db_get_pn_from_lid(raw_lid)
            if sender_phone:
                from neonize.utils import build_jid
                resolved_phone_jid = build_jid(sender_phone, "s.whatsapp.net")
            else:
                print(f" -> [DEBUG] Attempting to resolve LID {jid_to_str(interacting_jid)} using get_pn_from_lid...")
                try:
                    resolved_phone_jid = client.get_pn_from_lid(interacting_jid)
                    if resolved_phone_jid:
                        sender_phone = extract_user_id(resolved_phone_jid)
                        print(f" -> [DEBUG] Resolved JID successfully: {jid_to_str(resolved_phone_jid)}")
                except Exception as e:
                    print(f" -> [DEBUG] get_pn_from_lid raised: {e}")
                
                if not resolved_phone_jid:
                    print(f" -> [DEBUG] Attempting fallback resolution using get_user_info...")
                    try:
                        res_info = client.get_user_info(interacting_jid)
                        if res_info:
                            for single_info in res_info:
                                ret_jid = getattr(single_info, "JID", None) or getattr(single_info, "jid", None)
                                if ret_jid and (getattr(ret_jid, "Server", "") or getattr(ret_jid, "server", "")) == "s.whatsapp.net":
                                    resolved_phone_jid = ret_jid
                                    sender_phone = extract_user_id(resolved_phone_jid)
                                    print(f" -> [DEBUG] Resolved JID from get_user_info: {jid_to_str(resolved_phone_jid)}")
                                    break
                    except Exception as ex:
                        print(f" -> [DEBUG] get_user_info raised: {ex}")

        sender_id = extract_user_id(interacting_jid)
        chat_id = extract_user_id(chat_target)

        # Identify if this is a self-chat notebook window
        is_self_chat = (sender_id == chat_id) or (chat_target and not sender_jid)

        # Log incoming event with sender phone number / ID
        print(f"\n--- [WhatsApp Event] Received Message ---")
        if sender_phone:
            print(f" -> Sender Phone:    {sender_phone}")
        print(f" -> Sender ID/LID:   {sender_id}")
        print(f" -> Full Sender JID: {jid_to_str(interacting_jid)}")
        if resolved_phone_jid:
            print(f" -> Resolved JID:    {jid_to_str(resolved_phone_jid)}")
        print(f" -> Is From Me:      {is_from_me}")
        print(f" -> Is Self Chat:    {is_self_chat}")

        default_agent = config.get("DEFAULT_AGENT", "Terry")
        routed_agent = default_agent
        if is_self_chat:
            routed_agent = config.get("SELF_CHAT_AGENT", default_agent)
        else:
            mapping = config.get("AGENT_MAPPING", {})
            normalized_mapping = {normalize_phone_number(k): v for k, v in mapping.items()}
            normalized_sender_phone = normalize_phone_number(sender_phone) if sender_phone else ""
            normalized_sender_id = normalize_phone_number(sender_id)
            routed_agent = (
                normalized_mapping.get(normalized_sender_phone, None)
                or normalized_mapping.get(normalized_sender_id, default_agent)
            )

        is_authorized = False
        requires_prefix = True

        # -----------------------------------------------------------------
        # Dynamic Authorization & Prefix Checking Rules
        # -----------------------------------------------------------------
        normalized_sender_id = normalize_phone_number(sender_id)
        normalized_sender_phone = normalize_phone_number(sender_phone) if sender_phone else ""
        if is_from_me:
            if is_self_chat:
                if ALLOW_OWN_MESSAGES:
                    is_authorized = True
                    requires_prefix = False
                    my_personal_jid = chat_target
            else:
                if normalized_sender_id in ALLOWLIST or (normalized_sender_phone and normalized_sender_phone in ALLOWLIST):
                    is_authorized = True
                    requires_prefix = True
        else:
            if normalized_sender_id in ALLOWLIST or (normalized_sender_phone and normalized_sender_phone in ALLOWLIST):
                is_authorized = True
                requires_prefix = True

        if not is_authorized:
            dropped_info = sender_phone if sender_phone else sender_id
            print(f" -> [UNAUTHORIZED] Message from {dropped_info} dropped (not in ID_ALLOWLIST).")
            return

        is_audio_interaction = bool(audio_msg)
        is_media_interaction = bool(image_msg or doc_msg)
        
        # Temp message text for prefix check before media is fully downloaded/transcribed
        temp_message_text = message_text or ""
        if image_msg and not temp_message_text:
            temp_message_text = getattr(image_msg, "caption", "") or "[Image Upload]"
        if doc_msg and not temp_message_text:
            temp_message_text = getattr(doc_msg, "caption", "") or f"[Document: {getattr(doc_msg, 'fileName', 'file')}]"
            
        trigger_prefix = str(config.get("TRIGGER_PREFIX", "to ai:")).strip().lower()
        has_prefix = False
        cleaned_text = temp_message_text
        if trigger_prefix:
            has_prefix = temp_message_text.lower().startswith(trigger_prefix)
            if has_prefix:
                cleaned_text = temp_message_text[len(trigger_prefix):].lstrip()
        else:
            has_prefix = True

        # Intercept `/agent <name>` command if sender has permission
        if cleaned_text.lower().startswith("/agent "):
            parts = cleaned_text.split(" ", 1)
            if len(parts) > 1:
                new_agent = parts[1].strip()
                
                # Check if agent exists using the agent API (with filesystem fallback)
                existing_agents = []
                try:
                    api_url = WEBHOOK_URL.rsplit('/', 1)[0] + "/agents"
                    response = requests.get(api_url, timeout=5)
                    if response.status_code == 200:
                        existing_agents = response.json().get("agents", [])
                except Exception as api_err:
                    print(f" -> [API Error] Failed to fetch agents from API: {api_err}. Falling back to directory list.")
                
                if not existing_agents:
                    agents_dir = os.path.join(MAIN_DIR, "master", "working", "agents")
                    if os.path.exists(agents_dir):
                        existing_agents = [
                            item for item in os.listdir(agents_dir)
                            if os.path.isdir(os.path.join(agents_dir, item))
                        ]
                
                matched_agent = None
                for agent in existing_agents:
                    if agent.lower() == new_agent.lower():
                        matched_agent = agent
                        break
                
                resolved_jid = jid_cache.get(sender_id) or sender_jid or chat_target
                if not resolved_jid:
                    resolved_jid = f"{sender_id}@s.whatsapp.net"
                
                if not matched_agent:
                    reply_msg = f"Agent '{new_agent}' does not exist. Available agents: {', '.join(existing_agents)}"
                    safe_send_message(client, resolved_jid, reply_msg)
                    print(f" -> [Command Intercepted] Failed to switch agent for {sender_id} to '{new_agent}' (not found)")
                    return
                
                if is_self_chat:
                    config["SELF_CHAT_AGENT"] = matched_agent
                else:
                    if "AGENT_MAPPING" not in config:
                        config["AGENT_MAPPING"] = {}
                    config["AGENT_MAPPING"][sender_id] = matched_agent
                
                try:
                    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                        yaml.safe_dump(config, f)
                    reply_msg = f"Your WhatsApp agent has been switched to: {matched_agent}"
                    print(f" -> [Command Intercepted] Switched agent for {sender_id} to {matched_agent}")
                except Exception as save_err:
                    reply_msg = f"Failed to switch agent: {save_err}"
                    print(f" -> [Command Intercepted] Failed to save config for {sender_id}: {save_err}")
                
                safe_send_message(client, resolved_jid, reply_msg)
                return


        if requires_prefix and not has_prefix and not is_audio_interaction and not is_media_interaction:
            prefix_display = trigger_prefix if trigger_prefix else "no prefix"
            print(f" -> [Dropped] Message from {sender_id} to {chat_id} is missing '{prefix_display}' prefix.")
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
                
                if whisper_model is not None:
                    segments, _ = whisper_model.transcribe(inbound_ogg)
                    message_text = " ".join([s.text for s in segments]).strip()
                else:
                    litellm_params = {}
                    if stt_model_config.get("api_key"):
                        litellm_params["api_key"] = stt_model_config["api_key"]
                    if stt_model_config.get("api_base"):
                        litellm_params["api_base"] = stt_model_config["api_base"]
                    
                    with open(inbound_ogg, "rb") as audio_file:
                        response = litellm.transcription(
                            model=stt_model_name,
                            file=audio_file,
                            **litellm_params
                        )
                    message_text = getattr(response, "text", "").strip()
            except Exception as audio_err:
                print(f" -> [Audio Error] Failed downloading or transcribing voice note: {audio_err}")
                return
        elif image_msg:
            print("\n -> [Image Intercepted] Downloading image...")
            try:
                image_bytes = client.download_any(parent_msg)
                # Media goes to the agent's folder
                media_dir = os.path.join(MASTER_DIR, "working", "agents", routed_agent, "uploaded_media")
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
        if trigger_prefix and has_prefix and message_text.lower().startswith(trigger_prefix):
            message_text = message_text[len(trigger_prefix):].lstrip()

        # -----------------------------------------------------------------
        # Immediate Global Logging (Shows for all intercepted texts)
        # -----------------------------------------------------------------
        print("\n--- [WhatsApp Event] New Message Intercepted ---")
        print(f" -> Message Text: '{message_text}'")
        print(f" -> Sender ID:    {sender_id}")
        print(f" -> Chat ID:      {chat_id}")
        print(f" -> Audio Input:  {is_audio_interaction}")
        
        print(f" -> [MATCH SUCCESS] Message authorized from {sender_id}! Routing via Webhook for agent '{routed_agent}'...")
        
        if is_audio_interaction:
            audio_chats[chat_id] = time.time()
        else:
            audio_chats.pop(chat_id, None)

        jid_cache[sender_id] = chat_target
        if sender_phone:
            jid_cache[sender_phone] = chat_target
        
        protocol = {}
        channels_file = os.path.join(MAIN_DIR, "channels.yaml")
        if os.path.exists(channels_file):
            try:
                with open(channels_file, "r", encoding="utf-8") as f:
                    channels_data = yaml.safe_load(f) or {}
                    protocol = channels_data.get("WhatsApp", {})
            except Exception:
                pass

        payload = {
            "channel": "WhatsApp",
            "text": message_text,
            "agent": routed_agent,
            "media_paths": media_paths,
            "sender_id": sender_id,
            "chat_id": chat_id,
            "protocol": protocol
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
                        audio_reply_sent = False
                        if is_audio_interaction:
                            if not tts_api_key:
                                print(" -> [Generating Audio Voice Note] Skipped: TTS API key is not initialized. Falling back to text response.")
                            else:
                                print(f" -> [Generating Audio Voice Note] Synthesizing speech via LiteLLM TTS using model '{tts_model_name}'...")
                                temp_mp3 = os.path.join(TEMP_DIR, "tts_temp.mp3")
                                outbound_ogg = os.path.join(TEMP_DIR, "whatsapp_outbound.ogg")

                                try:
                                    litellm_params = {
                                        "model": tts_model_name,
                                        "voice": tts_voice,
                                        "input": ai_reply,
                                        "api_key": tts_api_key
                                    }
                                    if tts_api_base:
                                        litellm_params["api_base"] = tts_api_base
                                    
                                    response_tts = litellm.speech(**litellm_params)
                                    response_tts.write_to_file(temp_mp3)

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
                                    safe_send_message(client, resolved_jid, audio_message)
                                    audio_reply_sent = True
                                except Exception as tts_err:
                                    print(f" -> [TTS Error] LiteLLM TTS failed, falling back to text response: {tts_err}")
                                finally:
                                    # Cleanup execution footprints safely
                                    for path_to_del in [temp_mp3, outbound_ogg]:
                                        try:
                                            if os.path.exists(path_to_del):
                                                os.remove(path_to_del)
                                        except OSError:
                                            pass

                        if not audio_reply_sent:
                            print(f" -> [Sending Reply] Mailing text response back to: {resolved_jid}")
                            agent_ai_name = get_agent_ai_name(routed_agent)
                            prefix_template = str(config.get("REPLY_PREFIX", "\n{AI_NAME}:\n\n"))
                            prefix = prefix_template.replace("{AI_NAME}", agent_ai_name)
                            
                            # Extract files to send
                            files_to_send = re.findall(r'\[SEND_FILE:\s*(.+?)\]', ai_reply)
                            # Remove the tags from the text
                            ai_reply_clean = re.sub(r'\[SEND_FILE:\s*(.+?)\]', '', ai_reply).strip()

                            full_reply = f"{prefix}{ai_reply_clean}"
                            full_reply = re.sub(r'\*+', '*', full_reply)
                            
                            if ai_reply_clean:
                                safe_send_message(client, resolved_jid, full_reply)
                                
                            import mimetypes
                            for fpath in files_to_send:
                                if os.path.exists(fpath):
                                    print(f" -> [Sending File] {fpath}")
                                    try:
                                        filename = os.path.basename(fpath)
                                        mime_type, _ = mimetypes.guess_type(fpath)
                                        if not mime_type:
                                            mime_type = "application/octet-stream"
                                            
                                        client.send_document(resolved_jid, fpath, filename=filename, mimetype=mime_type)
                                    except Exception as e:
                                        print(f" -> [Error] Failed to send file {fpath}: {e}")
                                else:
                                    print(f" -> [Error] File to send not found: {fpath}")
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
        
        def start_approval_listener():
            from flask import Flask, request, jsonify
            import logging
            
            listener_app = Flask("whatsapp_approval_listener")
            log = logging.getLogger('werkzeug')
            log.setLevel(logging.ERROR)
            
            @listener_app.route('/send_poll', methods=['POST'])
            def handle_send_poll():
                data = request.json or {}
                chat_id = data.get("chat_id")
                command = data.get("command")
                approval_id = data.get("approval_id")
                agent_name = data.get("agent_name", "Terry")
                
                if not chat_id or not command or not approval_id:
                    return jsonify({"error": "Missing parameters"}), 400
                    
                try:
                    from neonize.utils import build_jid
                    from neonize.utils.enum import VoteType
                    
                    resolved_jid = jid_cache.get(chat_id)
                    if not resolved_jid:
                        resolved_jid = jid_cache.get(data.get("sender_id"))
                    if not resolved_jid:
                        if "@" in chat_id:
                            user, server = chat_id.split("@", 1)
                            resolved_jid = build_jid(user, server)
                        else:
                            resolved_jid = build_jid(chat_id)
                    
                    parts = command.split("\n")
                    poll_message = client.build_poll_vote_creation(
                        name=f"⚠️ Tool Authorization\nAgent: `{agent_name}`\n{parts[0]}\n`{parts[1]}`",
                        options=["Approve", "Deny"],
                        selectable_count=VoteType.SINGLE
                    )
                    
                    try:
                        res = client.send_message(resolved_jid, poll_message, add_msg_secret=True)
                        if res and hasattr(res, "ID"):
                            active_approvals[res.ID] = approval_id
                        print(f"[*] Sent approval poll for command ID {approval_id} to WhatsApp.")
                    except Exception as poll_err:
                        err_msg = str(poll_err)
                        if "Wire format was corrupt" in err_msg or "Error parsing message" in err_msg:
                            print(f"[*] Sent approval poll for command ID {approval_id} (ignored neonize parsing error).")
                        else:
                            raise poll_err
                    return jsonify({"status": "success"})
                except Exception as e:
                    print(f"[-] Error sending WhatsApp approval poll: {e}")
                    return jsonify({"error": str(e)}), 500

            @listener_app.route('/send_message', methods=['POST'])
            def handle_send_message():
                data = request.json or {}
                chat_id = data.get("chat_id")
                text = data.get("text")
                
                if not chat_id or not text:
                    return jsonify({"error": "Missing parameters"}), 400
                    
                try:
                    from neonize.utils import build_jid
                    
                    resolved_jid = jid_cache.get(chat_id)
                    if not resolved_jid:
                        if "@" in chat_id:
                            user, server = chat_id.split("@", 1)
                            resolved_jid = build_jid(user, server)
                        else:
                            resolved_jid = build_jid(chat_id)
                            
                    # Check if this chat expects an audio response (meaning the last message received was a voice note)
                    audio_reply_sent = False
                    is_audio_interaction = chat_id in audio_chats
                    
                    if is_audio_interaction:
                        if not tts_api_key:
                            print(" -> [Generating Audio Voice Note (Async)] Skipped: TTS API key is not initialized. Sending text reply instead.")
                        else:
                            print(f" -> [Generating Audio Voice Note (Async)] Synthesizing speech via LiteLLM TTS using model '{tts_model_name}'...")
                            temp_mp3 = os.path.join(TEMP_DIR, f"tts_temp_async_{int(time.time())}.mp3")
                            outbound_ogg = os.path.join(TEMP_DIR, f"whatsapp_outbound_async_{int(time.time())}.ogg")

                            try:
                                litellm_params = {
                                    "model": tts_model_name,
                                    "voice": tts_voice,
                                    "input": text,
                                    "api_key": tts_api_key
                                }
                                if tts_api_base:
                                    litellm_params["api_base"] = tts_api_base
                                
                                response_tts = litellm.speech(**litellm_params)
                                response_tts.write_to_file(temp_mp3)

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
                                print(f" -> [Sending Reply (Async)] Blasting voice note back to: {resolved_jid}")
                                safe_send_message(client, resolved_jid, audio_message)
                                audio_reply_sent = True
                            except Exception as tts_err:
                                print(f" -> [TTS Error (Async)] LiteLLM TTS failed, falling back to text response: {tts_err}")
                            finally:
                                # Cleanup execution footprints safely
                                for path_to_del in [temp_mp3, outbound_ogg]:
                                    try:
                                        if os.path.exists(path_to_del):
                                            os.remove(path_to_del)
                                    except OSError:
                                        pass

                    if not audio_reply_sent:
                        formatted_text = text.replace("**", "*")
                        print(f" -> [Sending Reply (Async)] Mailing text response back to: {resolved_jid}")
                        safe_send_message(client, resolved_jid, formatted_text)
                        
                    return jsonify({"status": "success"})
                except Exception as e:
                    print(f"[-] Error sending WhatsApp async message: {e}")
                    return jsonify({"error": str(e)}), 500

            listener_app.run(host='127.0.0.1', port=5056, debug=False, use_reloader=False)

        listener_thread = threading.Thread(target=start_approval_listener, daemon=True)
        listener_thread.start()
        print("[*] Started WhatsApp approval HTTP listener on port 5056.")
        
        print("\n[*] Connecting to WhatsApp...")
        client.connect()

if __name__ == "__main__":
    if VALID_CONFIG:
        main()