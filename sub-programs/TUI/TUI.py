import os
import sys
import yaml
from types import SimpleNamespace
import requests
import pyfiglet
from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import ScrollableContainer, Vertical, Horizontal
from textual.widgets import Footer, Header, Input, Markdown, OptionList, Static


# =================================================================
# Configuration Variables
# =================================================================
VALID_CONFIG = True

MAIN_DIR = Path(__file__).resolve().parent.parent.parent
TUI_DIR = Path(__file__).resolve().parent

CONFIG_FILE = os.path.join(TUI_DIR, "tui_config.yaml")

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
            print("Please restore the config template or create tui_config.yaml manually.")
            print("\nPress ENTER to close...")
            input()
            VALID_CONFIG = False
            return None
            
        print("\n" + "="*60)
        print(f" ACTION REQUIRED: Please open and edit '{os.path.basename(CONFIG_FILE)}' now.")
        print(" Set your desired ART_BANNER_NAME and ART_BANNER_FONT settings.")
        print("="*60)
        print("\nPress ENTER when you are done editing to continue...")
        input()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            loaded_config = yaml.safe_load(f)
    except Exception as e:
        print(f"Error: '{CONFIG_FILE}' contains invalid YAML formatting. Please fix your config file or delete it to regenerate a fresh template.")
        print("\nPress ENTER to close...")
        input()  
        VALID_CONFIG = False
        return None

    if not isinstance(loaded_config, dict):
        loaded_config = {}

    defaults = {
        "ART_BANNER_NAME": "OPENDOOR",
        "ART_BANNER_FONT": "ansi_shadow"
    }

    merged = {**defaults, **loaded_config}
    return SimpleNamespace(**merged)

config = load_config()

if VALID_CONFIG:
    BACKEND_URL = "http://127.0.0.1:5050/api/message"

    # Generate the adaptive title using variables from the dynamically loaded config
    art_banner = f"\n{pyfiglet.figlet_format(config.ART_BANNER_NAME, font=config.ART_BANNER_FONT).rstrip()}\n"

    class GenieInput(Input):
        # Fixed: Changed key_down to on_key so Textual correctly maps key events
        def on_key(self, event) -> None:
            autocomplete_list = self.app.query_one("#autocomplete-list")
            if autocomplete_list.styles.display == "block" and getattr(autocomplete_list, "option_count", 0) > 0:
                if event.key == "tab":
                    event.stop()
                    first_option = str(autocomplete_list.get_option_at_index(0).prompt)
                    self.app.apply_autocomplete(first_option)
                elif event.key == "down":
                    event.stop()
                    autocomplete_list.focus()

    class AiTUI(App):
        CSS = """
        Screen {
            background: #1e1e2e;
            color: #cdd6f4;
        }
        #header-area {
            margin: 1 2 0 2;
            color: #89b4fa;
            text-style: bold;
        }
        #header-info {
            height: auto;
            max-height: 3;
            margin: 0 2 0 2;
            padding: 0;
        }
        #status-bar {
            width: 1fr;
            content-align: right middle;
            color: #a6adc8;
            padding-right: 0;
            margin: 0;
            height: 1;
        }
        #main-body {
            height: 1fr;
            margin: 0;
            padding: 0;
        }
        #sidebar-container {
            width: 28;
            height: 1fr;
            border: solid #313244;
            background: #11111b;
            margin: 0 0 0 2;
            padding: 1 1;
        }
        #sidebar-header {
            color: #89b4fa;
            text-style: bold;
            margin: 1 1;
            content-align: center middle;
            height: auto;
        }
        #agents-sidebar {
            background: transparent;
            border: none;
            margin: 0;
            max-height: 100%;
            display: block;
            height: 1fr;
        }
        #agents-sidebar > .option-list--option {
            padding: 0 1;
            color: #a6adc8;
        }
        #agents-sidebar > .option-list--option-highlighted {
            background: #313244;
            color: #f5c2e7;
            text-style: bold;
        }
        #chat-col {
            width: 1fr;
            height: 1fr;
        }
        #chat-container {
            height: 1fr;
            border: solid #313244;
            margin: 0 2;
            padding: 1 2;
            background: #181825;
        }
        OptionList {
            background: #11111b;
            border: solid #89b4fa;
            margin: 0 2;
            max-height: 7;
            display: none;
        }
        OptionList > .option-list--option {
            padding: 0 1;
            color: #a6adc8;
        }
        OptionList > .option-list--option-highlighted {
            background: #45475a;
            color: #f5c2e7;
            text-style: bold;
        }
        .user-msg {
            color: #89dceb;
            margin-bottom: 1;
        }
        .agent-msg {
            color: #cdd6f4;
            margin-bottom: 1;
        }
        .system-log {
            color: #f9e2af;
            text-style: italic;
            margin-bottom: 1;
            margin-left: 2;
        }
        Input {
            margin: 1 2;
            border: round #89b4fa;
            background: #11111b;
            color: #cdd6f4;
        }
        Input:focus {
            border: round #b4befe;
        }
        """

        BASE_COMMANDS = ["/newsession", "/clear", "/loadsession", "/agent"]

        def __init__(self):
            super().__init__()
            self.messages = []
            self.chat_history = []
            self.current_agent = "Terry"
            self.agents_list = []
            self.agent_details = {}

        def compose(self) -> ComposeResult:
            # Utilize the dynamically generated ASCII art banner
            yield Static(art_banner, id="header-area")
            #yield Horizontal(
            #    Static("Using: Local Webhook Server (Port 5050)", id="status-bar"),
            #    id="header-info"
            #)
            yield Horizontal(
                Vertical(
                    Static("CONTROL PANEL\n[#a6adc8]Select Session[/]", id="sidebar-header"),
                    OptionList(id="agents-sidebar"),
                    id="sidebar-container"
                ),
                Vertical(
                    ScrollableContainer(id="chat-container"),
                    OptionList(id="autocomplete-list"),
                    # Utilize the dynamic AI name for the input placeholder
                    GenieInput(placeholder="> Ask agent anything... (Type / for commands)", id="user-input"),
                    id="chat-col"
                ),
                id="main-body"
            )
            yield Footer()


        def on_mount(self) -> None:
            self.chat_container = self.query_one("#chat-container")
            self.user_input = self.query_one("#user-input")
            self.user_input.focus()
            self.last_update_id = 0
            self.set_interval(0.5, self.poll_updates)
            self.load_agents_list()

        @work(thread=True)
        def load_agents_list(self) -> None:
            import time
            while True:
                try:
                    response = requests.get("http://127.0.0.1:5050/api/agents", timeout=2)
                    if response.status_code == 200:
                        data = response.json()
                        agents = data.get("agents", [])
                        details = data.get("agent_details", {})
                        if agents:
                            self.agents_list = agents
                            self.agent_details = details
                            self.call_from_thread(self.update_select_widget, agents)
                            break
                except Exception:
                    pass
                time.sleep(2.0)

        def update_select_widget(self, agents: list) -> None:
            self.agents_list = agents
            if "Terry" in agents:
                self.current_agent = "Terry"
            elif agents:
                self.current_agent = agents[0]
            
            # Update placeholder for initial agent
            details = self.agent_details.get(self.current_agent, {})
            ai_display_name = details.get("AI_NAME", self.current_agent)
            self.user_input.placeholder = f"> Ask {ai_display_name} anything... (Type / for commands)"
            
            self.update_sidebar()

        def update_sidebar(self) -> None:
            sidebar = self.query_one("#agents-sidebar", OptionList)
            sidebar.clear_options()
            highlighted_idx = 0
            for idx, agent in enumerate(self.agents_list):
                details = self.agent_details.get(agent, {})
                display_name = details.get("AI_NAME", agent)
                if agent == self.current_agent:
                    prompt = Text.from_markup(f"[green]●[/green] [bold]{display_name}[/bold]")
                    highlighted_idx = idx
                else:
                    prompt = Text.from_markup(f"[bright_black]○[/bright_black] {display_name}")
                sidebar.add_option(prompt)
            if self.agents_list:
                sidebar.highlighted = highlighted_idx

        def switch_agent(self, agent_name: str) -> None:
            self.current_agent = agent_name
            self.clear_chat_ui()
            self.last_update_id = 0
            details = self.agent_details.get(agent_name, {})
            ai_display_name = details.get("AI_NAME", agent_name)
            self.user_input.placeholder = f"> Ask {ai_display_name} anything... (Type / for commands)"
            self.notify_agent_switch(agent_name)
            self.update_sidebar()

        @work(thread=True)
        def notify_agent_switch(self, agent_name: str) -> None:
            try:
                requests.get(f"http://127.0.0.1:5050/api/load_agent?agent={agent_name}", timeout=2)
            except Exception:
                pass

        @work(exclusive=True, thread=True)
        def poll_updates(self) -> None:
            try:
                response = requests.get(
                    f"http://127.0.0.1:5050/api/updates?since={self.last_update_id}&agent={self.current_agent}",
                    timeout=2
                )
                if response.status_code == 200:
                    updates = response.json().get("updates", [])
                    if updates:
                        self.call_from_thread(self.process_updates, updates)
            except Exception:
                pass

        def process_updates(self, updates: list) -> None:
            for update in updates:
                up_id = update["id"]
                up_type = update["type"]
                channel = update["channel"]
                content = update["content"]

                if content == "CLEAR":
                    self.clear_chat_ui()
                elif up_type == "user":
                    self.mount_user_msg(channel, content)
                elif up_type == "agent" or up_type == "assistant":
                    self.mount_agent_msg(channel, content)
                elif up_type == "system":
                    self.mount_sys_log(content)

                self.last_update_id = max(self.last_update_id, up_id + 1)

        def on_unmount(self) -> None:
            return None

        def clear_chat_ui(self) -> None:
            self.messages.clear()
            self.chat_history.clear()
            try:
                self.chat_container.remove_children()
            except Exception:
                pass

        def mount_sys_log(self, content: str) -> None:
            self.chat_container.mount(Markdown(f"**[SYS]** {content}", classes="system-log"))
            self.chat_container.scroll_end(animate=False)

        def mount_user_msg(self, context_channel: str, content: str) -> None:
            tag = f" [{context_channel}]" if context_channel and context_channel != "TUI" else ""
            self.chat_container.mount(Markdown(f"**You{tag}:** {content}", classes="user-msg"))
            self.chat_container.scroll_end(animate=False)

        def mount_agent_msg(self, context_channel: str, content: str) -> None:
            tag = f" [{context_channel}]" if context_channel and context_channel != "TUI" else ""
            details = self.agent_details.get(self.current_agent, {})
            ai_display_name = details.get("AI_NAME", self.current_agent)
            self.chat_container.mount(Markdown(f"**{ai_display_name}{tag}:** {content}", classes="agent-msg"))
            self.chat_container.scroll_end(animate=False)

        def render_history_to_ui(self) -> None:
            self.clear_chat_ui()
            for msg in self.chat_history:
                self.chat_container.mount(Static(msg))

        def watch_user_input_changes(self, value: str) -> None:
            autocomplete_list = self.query_one("#autocomplete-list")
            autocomplete_list.clear_options()
            if value.startswith("/"):
                all_suggestions = list(self.BASE_COMMANDS)
                if value.startswith("/loadsession"):
                    all_suggestions += ["/loadsession recent"]
                elif value.startswith("/agent"):
                    all_suggestions += [f"/agent {agent}" for agent in self.agents_list]
                matches = [cmd for cmd in all_suggestions if cmd.startswith(value) and cmd != value]
                if matches:
                    autocomplete_list.styles.display = "block"
                    for match in matches:
                        autocomplete_list.add_option(match)
                    return
            autocomplete_list.styles.display = "none"

        def apply_autocomplete(self, completed_text: str) -> None:
            input_widget = self.query_one("#user-input")
            input_widget.value = completed_text + " "
            input_widget.cursor_position = len(input_widget.value)
            input_widget.focus()
            self.query_one("#autocomplete-list").styles.display = "none"

        def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
            if event.option_list.id == "autocomplete-list":
                self.apply_autocomplete(str(event.option.prompt))
            elif event.option_list.id == "agents-sidebar":
                idx = getattr(event, "option_index", None)
                if idx is None:
                    idx = getattr(event, "option_idx", 0)
                if 0 <= idx < len(self.agents_list):
                    agent_dir = self.agents_list[idx]
                    self.switch_agent(agent_dir)

        def on_input_changed(self, event: Input.Changed) -> None:
            self.watch_user_input_changes(event.value.strip())

        def on_input_submitted(self, event: Input.Submitted) -> None:
            self.query_one("#autocomplete-list").styles.display = "none"
            user_text = event.value.strip()
            if not user_text:
                return

            self.user_input.value = ""
            
            # Catch /agent switching commands locally
            if user_text.lower().startswith("/agent "):
                parts = user_text.split(" ", 1)
                if len(parts) > 1:
                    new_agent = parts[1].strip()
                    matched_agent = None
                    for agent in self.agents_list:
                        if agent.lower() == new_agent.lower():
                            matched_agent = agent
                            break
                    if matched_agent:
                        self.switch_agent(matched_agent)
                    else:
                        self.mount_sys_log(f"Agent '{new_agent}' not found.")
                    return

            self.send_message_to_backend(user_text)

        @work(thread=True)
        def send_message_to_backend(self, text: str) -> None:
            try:
                requests.post(
                    BACKEND_URL,
                    json={
                        "channel": "TUI",
                        "text": text,
                        "agent": self.current_agent
                    },
                    timeout=300,
                )
            except Exception as exc:
                self.call_from_thread(self.mount_sys_log, f"Error contacting backend: {exc}")

    if __name__ == "__main__":
        AiTUI().run()