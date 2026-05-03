"""
Sollie GUI - Graphical User Interface
Modern chat interface with approval system
"""

import customtkinter as ctk
import threading
import queue
import os
import time
import re
from datetime import datetime
import psutil
from sollie_core import SollieBrain

COLORS = {
    "bg": "#0f1418",
    "panel": "#141b21",
    "panel_alt": "#1c252c",
    "outline": "#2b3842",
    "text": "#ecf1f5",
    "muted": "#9aa7b2",
    "accent": "#4dd0a6",
    "accent_hover": "#3fb98f",
    "warning": "#f4b24d",
    "danger": "#e26d5a",
    "info": "#6aa9ff"
}

FONTS = {
    "title": ("Bahnschrift", 26, "bold"),
    "subtitle": ("Candara", 13),
    "section": ("Candara", 12, "bold"),
    "body": ("Candara", 12),
    "body_bold": ("Candara", 12, "bold"),
    "body_italic": ("Candara", 12, "italic"),
    "code": ("Cascadia Mono", 11)
}


class SollieGUI:
    def __init__(self):
        # Initialize Sollie brain
        self.brain = SollieBrain()
        self.pending_action = None
        self.pending_actions = []
        self.last_suggestion_time = 0
        
        # Setup window
        self.window = ctk.CTk()
        self.window.title("Sollie - Your AI Assistant")
        self.window.geometry("980x720")
        self.window.minsize(980, 720)
        self.window.configure(fg_color=COLORS["bg"])

        self.ui_queue = queue.Queue()
        self.window.after(50, self.process_ui_queue)
        
        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.setup_ui()
        self.start_monitoring()
        
    def setup_ui(self):
        """Setup the user interface"""

        # Main container
        main_frame = ctk.CTkFrame(self.window, fg_color=COLORS["bg"], corner_radius=0)
        main_frame.pack(fill="both", expand=True)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        # Sidebar
        sidebar = ctk.CTkFrame(
            main_frame,
            width=230,
            fg_color=COLORS["panel"],
            corner_radius=18
        )
        sidebar.grid(row=0, column=0, sticky="nsw", padx=(12, 6), pady=12)

        brand = ctk.CTkLabel(
            sidebar,
            text="SOLLIE",
            font=FONTS["title"],
            text_color=COLORS["text"]
        )
        brand.pack(padx=16, pady=(18, 4), anchor="w")

        tagline = ctk.CTkLabel(
            sidebar,
            text="Local assistant",
            font=FONTS["subtitle"],
            text_color=COLORS["muted"]
        )
        tagline.pack(padx=16, pady=(0, 12), anchor="w")

        status_frame = ctk.CTkFrame(sidebar, fg_color=COLORS["panel_alt"], corner_radius=12)
        status_frame.pack(fill="x", padx=14, pady=(0, 12))
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="● Ready",
            font=FONTS["body_bold"],
            text_color=COLORS["accent"]
        )
        self.status_label.pack(padx=12, pady=10, anchor="w")

        quick_label = ctk.CTkLabel(
            sidebar,
            text="Quick Actions",
            font=FONTS["section"],
            text_color=COLORS["muted"]
        )
        quick_label.pack(padx=16, pady=(4, 6), anchor="w")

        def quick_button(title, message):
            return ctk.CTkButton(
                sidebar,
                text=title,
                command=lambda: self.send_quick_message(message),
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                text_color=COLORS["bg"],
                height=36
            )

        quick_button("List Desktop", "List my Desktop files").pack(padx=14, pady=4, fill="x")
        quick_button("List Downloads", "List my Downloads folder").pack(padx=14, pady=4, fill="x")
        quick_button("System Status", "What's my PC status?").pack(padx=14, pady=4, fill="x")

        task_label = ctk.CTkLabel(
            sidebar,
            text="Task Mode",
            font=FONTS["section"],
            text_color=COLORS["muted"]
        )
        task_label.pack(padx=16, pady=(14, 4), anchor="w")
        task_hint = ctk.CTkLabel(
            sidebar,
            text="Use /task to plan\nmultistep actions",
            font=FONTS["body"],
            text_color=COLORS["text"],
            justify="left"
        )
        task_hint.pack(padx=16, pady=(0, 12), anchor="w")

        spacer = ctk.CTkFrame(sidebar, fg_color=COLORS["panel"], corner_radius=0)
        spacer.pack(fill="both", expand=True)

        settings_btn = ctk.CTkButton(
            sidebar,
            text="⚙ Settings",
            command=self.show_settings,
            fg_color=COLORS["panel_alt"],
            hover_color=COLORS["outline"],
            text_color=COLORS["text"],
            height=38
        )
        settings_btn.pack(padx=14, pady=(0, 16), fill="x")

        # Content
        content_frame = ctk.CTkFrame(main_frame, fg_color=COLORS["bg"], corner_radius=0)
        content_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(2, weight=1)

        header_frame = ctk.CTkFrame(content_frame, fg_color=COLORS["panel"], corner_radius=18)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header_frame.grid_columnconfigure(0, weight=1)
        header_title = ctk.CTkLabel(
            header_frame,
            text="Sollie Command Center",
            font=FONTS["section"],
            text_color=COLORS["text"]
        )
        header_title.grid(row=0, column=0, sticky="w", padx=18, pady=(12, 2))
        header_sub = ctk.CTkLabel(
            header_frame,
            text="Local-first · Safe actions · Agentic tasks",
            font=FONTS["subtitle"],
            text_color=COLORS["muted"]
        )
        header_sub.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 12))

        # Action approval frame (hidden by default)
        self.approval_frame = ctk.CTkFrame(content_frame, fg_color=COLORS["panel_alt"], corner_radius=16)
        self.approval_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.approval_frame.grid_remove()

        self.approval_label = ctk.CTkLabel(
            self.approval_frame,
            text="",
            font=FONTS["body_bold"],
            text_color=COLORS["text"]
        )
        self.approval_label.pack(pady=(10, 6))

        approval_buttons = ctk.CTkFrame(self.approval_frame, fg_color=COLORS["panel_alt"], corner_radius=12)
        approval_buttons.pack(pady=(0, 10))

        self.approve_btn = ctk.CTkButton(
            approval_buttons,
            text="✓ Approve",
            command=self.approve_action,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color=COLORS["bg"],
            width=140
        )
        self.approve_btn.pack(side="left", padx=6)

        self.deny_btn = ctk.CTkButton(
            approval_buttons,
            text="✗ Deny",
            command=self.deny_action,
            fg_color=COLORS["danger"],
            hover_color="#c85b4a",
            text_color=COLORS["bg"],
            width=140
        )
        self.deny_btn.pack(side="left", padx=6)

        # Chat display area
        chat_frame = ctk.CTkFrame(content_frame, fg_color=COLORS["panel_alt"], corner_radius=18)
        chat_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        chat_frame.grid_rowconfigure(0, weight=1)
        chat_frame.grid_columnconfigure(0, weight=1)

        self.chat_display = ctk.CTkTextbox(
            chat_frame,
            font=FONTS["body"],
            wrap="word",
            state="disabled",
            fg_color=COLORS["panel_alt"],
            text_color=COLORS["text"],
            scrollbar_button_color=COLORS["outline"],
            scrollbar_button_hover_color=COLORS["accent_hover"]
        )
        self.chat_display.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.configure_chat_tags()

        # Input area
        input_frame = ctk.CTkFrame(content_frame, fg_color=COLORS["panel"], corner_radius=18)
        input_frame.grid(row=3, column=0, sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)

        self.input_box = ctk.CTkEntry(
            input_frame,
            placeholder_text="Type your message to Sollie...",
            font=FONTS["body"],
            height=42,
            fg_color=COLORS["panel_alt"],
            text_color=COLORS["text"],
            placeholder_text_color=COLORS["muted"],
            border_color=COLORS["outline"],
            border_width=1
        )
        self.input_box.grid(row=0, column=0, sticky="ew", padx=(12, 10), pady=12)
        self.input_box.bind("<Return>", lambda e: self.send_message())

        self.send_btn = ctk.CTkButton(
            input_frame,
            text="Send",
            command=self.send_message,
            width=110,
            height=40,
            font=FONTS["body_bold"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color=COLORS["bg"]
        )
        self.send_btn.grid(row=0, column=1, padx=(0, 12), pady=12)
        
        # Add welcome message
        self.add_message("Sollie", "Hello! I'm Sollie, your AI assistant. I'm here to help you with tasks on your PC. What can I do for you today?", "assistant")
    
    def add_message(self, sender, message, msg_type="user"):
        """Add a message to the chat display"""
        if threading.current_thread() is not threading.main_thread():
            self.enqueue_ui(self.add_message, sender, message, msg_type)
            return

        self.chat_display.configure(state="normal")
        
        timestamp = datetime.now().strftime("%H:%M")
        
        if msg_type == "user":
            prefix = f"\n[{timestamp}] You: "
            self.chat_display.insert("end", prefix, "user_name")
            self.chat_display.insert("end", f"{message}\n", "user_msg")
        elif msg_type == "assistant":
            prefix = f"\n[{timestamp}] Sollie: "
            self.chat_display.insert("end", prefix, "assistant_name")
            self.insert_markdown(message, "assistant_msg")
            self.chat_display.insert("end", "\n")
        elif msg_type == "system":
            self.chat_display.insert("end", f"\n[{timestamp}] SYSTEM: ", "system_name")
            self.insert_markdown(message, "system_msg")
            self.chat_display.insert("end", "\n")
        elif msg_type == "action":
            self.chat_display.insert("end", f"\n[{timestamp}] ⚡ ACTION: ", "action_name")
            self.insert_markdown(message, "action_msg")
            self.chat_display.insert("end", "\n")
        
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    def configure_chat_tags(self):
        text_widget = getattr(self.chat_display, "_textbox", self.chat_display)

        for name, color in [
            ("user_name", COLORS["info"]),
            ("assistant_name", COLORS["accent"]),
            ("system_name", COLORS["warning"]),
            ("action_name", COLORS["danger"]),
            ("user_msg", COLORS["text"]),
            ("assistant_msg", COLORS["text"]),
            ("system_msg", COLORS["text"]),
            ("action_msg", COLORS["text"])
        ]:
            try:
                text_widget.tag_config(name, foreground=color)
            except Exception:
                pass

        for name, font, color in [
            ("bold", FONTS["body_bold"], COLORS["text"]),
            ("italic", FONTS["body_italic"], COLORS["text"]),
            ("inline_code", FONTS["code"], COLORS["info"]),
            ("code_block", FONTS["code"], COLORS["text"])
        ]:
            try:
                text_widget.tag_config(name, font=font, foreground=color)
            except Exception:
                pass

        try:
            text_widget.tag_config("code_block", background=COLORS["panel"])
            text_widget.tag_config("list_item", lmargin1=16, lmargin2=32)
        except Exception:
            pass

    def insert_markdown(self, text, default_tag):
        """Render basic markdown for assistant/system/action messages."""
        parts = text.split("```")
        for idx, part in enumerate(parts):
            if idx % 2 == 1:
                self.chat_display.insert("end", part, ("code_block",))
                continue

            for line in part.splitlines(keepends=True):
                list_match = re.match(r"^\s*(?:[-*]|\d+\.)\s+(.*)", line)
                if list_match:
                    self.chat_display.insert("end", "• ", ("list_item", default_tag))
                    self.insert_inline_markdown(list_match.group(1), default_tag)
                    if line.endswith("\n"):
                        self.chat_display.insert("end", "\n")
                else:
                    self.insert_inline_markdown(line, default_tag)

    def insert_inline_markdown(self, text, default_tag):
        patterns = [
            (re.compile(r"`([^`]+)`"), "inline_code"),
            (re.compile(r"\*\*([^*]+)\*\*"), "bold"),
            (re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)"), "italic")
        ]

        while text:
            matches = []
            for pattern, tag in patterns:
                match = pattern.search(text)
                if match:
                    matches.append((match.start(), match, tag))

            if not matches:
                self.chat_display.insert("end", text, (default_tag,))
                return

            matches.sort(key=lambda item: item[0])
            start, match, tag = matches[0]

            if start > 0:
                self.chat_display.insert("end", text[:start], (default_tag,))

            self.chat_display.insert("end", match.group(1), (tag,))
            text = text[match.end():]

    def set_status(self, text, color):
        if threading.current_thread() is not threading.main_thread():
            self.enqueue_ui(self.set_status, text, color)
            return
        self.status_label.configure(text=text, text_color=color)

    def enqueue_ui(self, func, *args, **kwargs):
        self.ui_queue.put((func, args, kwargs))

    def process_ui_queue(self):
        while True:
            try:
                func, args, kwargs = self.ui_queue.get_nowait()
            except queue.Empty:
                break

            try:
                func(*args, **kwargs)
            except Exception as e:
                print(f"UI update error: {e}")

        self.window.after(50, self.process_ui_queue)
    
    def send_message(self):
        """Send user message to Sollie"""
        message = self.input_box.get().strip()
        if not message:
            return
        
        # Clear input
        self.input_box.delete(0, "end")
        
        # Display user message
        self.add_message("You", message, "user")
        
        # Update status
        self.set_status("● Thinking...", COLORS["warning"])
        
        # Process in background thread to keep UI responsive
        thread = threading.Thread(target=self.process_message, args=(message,))
        thread.daemon = True
        thread.start()
    
    def process_message(self, message):
        """Process message with Sollie brain"""
        try:
            normalized = message.strip().lower()
            if normalized in ["/stop", "/cancel", "stop task"]:
                self.clear_pending_task()
                self.add_message("System", "Task cancelled.", "system")
                self.set_status("● Ready", "green")
                return

            if self.is_task_command(message):
                if not self.brain.config.get("agent", {}).get("enabled", True):
                    self.add_message("System", "Task mode is disabled in config.json.", "system")
                else:
                    self.process_task_message(message)
                self.set_status("● Ready", "green")
                return

            result = self.brain.chat(message)
            
            # Display Sollie's response
            self.add_message("Sollie", result['response'], "assistant")
            
            # Check if action needed
            if result['action']:
                self.pending_action = result['action']
                if result['needs_approval']:
                    self.show_approval_request(result['action'])
                else:
                    # Auto-execute if approval not required
                    self.execute_pending_action()
            
            # Update status
            self.set_status("● Ready", COLORS["accent"])
        
        except Exception as e:
            self.add_message("System", f"Error: {str(e)}", "system")
            self.set_status("● Error", COLORS["danger"])

    def send_quick_message(self, message):
        self.input_box.delete(0, "end")
        self.input_box.insert(0, message)
        self.send_message()
    
    def show_approval_request(self, action):
        """Show action approval UI"""
        if threading.current_thread() is not threading.main_thread():
            self.enqueue_ui(self.show_approval_request, action)
            return
        self.approval_label.configure(text=f"⚠ Sollie wants to: {action['description']}")
        self.approval_frame.grid()
    
    def approve_action(self):
        """User approves the action"""
        if self.pending_action:
            self.add_message("System", f"Executing: {self.pending_action['description']}", "action")
            self.execute_pending_action()
    
    def deny_action(self):
        """User denies the action"""
        if self.pending_action:
            self.add_message("System", f"Action denied: {self.pending_action['description']}", "system")
            self.brain.memory.log_action(
                action_type=self.pending_action['type'],
                action_details=self.pending_action['params'],
                approved=False,
                result="User denied"
            )
        self.clear_pending_task()
    
    def execute_pending_action(self):
        """Execute the pending action"""
        if not self.pending_action:
            return
        
        result = self.brain.execute_action(self.pending_action)
        
        if result['success']:
            self.add_message("System", f"✓ Success: {result.get('message', 'Action completed')}", "system")
        else:
            self.add_message("System", f"✗ Failed: {result.get('error', 'Unknown error')}", "system")

        self.pending_action = None
        if self.pending_actions:
            self.pending_action = self.pending_actions.pop(0)
            if self.brain.approval_required:
                self.show_approval_request(self.pending_action)
            else:
                self.execute_pending_action()
        else:
            self.hide_approval_ui()
    
    def hide_approval_ui(self):
        """Hide the approval UI"""
        if threading.current_thread() is not threading.main_thread():
            self.enqueue_ui(self.hide_approval_ui)
            return
        self.approval_frame.grid_remove()

    def clear_pending_task(self):
        self.pending_action = None
        self.pending_actions = []
        self.hide_approval_ui()

    def is_task_command(self, message):
        normalized = message.strip().lower()
        return (
            normalized.startswith("/task")
            or normalized.startswith("/agent")
            or normalized.startswith("task:")
            or normalized.startswith("agent:")
        )

    def extract_task_text(self, message):
        text = message.strip()
        lowered = text.lower()

        for prefix in ["/task", "/agent"]:
            if lowered.startswith(prefix):
                return text[len(prefix):].strip() or text

        for prefix in ["task:", "agent:"]:
            if lowered.startswith(prefix):
                return text[len(prefix):].strip() or text

        return text

    def process_task_message(self, message):
        task_text = self.extract_task_text(message)
        if not task_text or task_text.strip().lower() in ["/task", "/agent", "task:", "agent:"]:
            self.add_message("System", "Please provide a task after /task.", "system")
            return
        plan = self.brain.plan_task(task_text)

        self.add_message("Sollie", plan["plan_text"], "assistant")
        if plan.get("clarifying_questions"):
            self.add_message("Sollie", "Please answer the questions above.", "assistant")
            return

        actions = plan.get("actions") or []
        if not actions:
            self.add_message("System", "No safe actions detected for that plan.", "system")
            return

        self.pending_actions = actions
        self.pending_action = self.pending_actions.pop(0)
        self.show_approval_request(self.pending_action)

    def start_monitoring(self):
        config = self.brain.config.get("monitoring", {})
        if not config.get("enabled", False):
            return

        monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        monitor_thread.start()

    def is_quiet_hours(self, config):
        quiet = config.get("quiet_hours") or {}
        start = quiet.get("start")
        end = quiet.get("end")

        if not start or not end:
            return False

        try:
            start_time = datetime.strptime(start, "%H:%M").time()
            end_time = datetime.strptime(end, "%H:%M").time()
        except ValueError:
            return False

        now = datetime.now().time()
        if start_time <= end_time:
            return start_time <= now <= end_time
        return now >= start_time or now <= end_time

    def get_system_metrics(self):
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        if os.name == "nt":
            root = os.environ.get("SystemDrive", "C:") + "\\"
        else:
            root = "/"
        disk_percent = psutil.disk_usage(root).percent

        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "disk_percent": disk_percent
        }

    def build_suggestion(self, metrics, config):
        suggestions = []
        if metrics["cpu_percent"] >= config.get("cpu_percent", 85):
            suggestions.append("I can list running apps to help find heavy usage.")
        if metrics["memory_percent"] >= config.get("memory_percent", 85):
            suggestions.append("I can list running apps to help free memory.")
        if metrics["disk_percent"] >= config.get("disk_percent", 90):
            suggestions.append("I can list your Downloads folder if you want to clean up.")

        if not suggestions:
            return ""

        return "Suggestion: " + " ".join(suggestions)

    def build_suggestion_actions(self, metrics, config):
        actions = []
        if (
            metrics["cpu_percent"] >= config.get("cpu_percent", 85)
            or metrics["memory_percent"] >= config.get("memory_percent", 85)
        ):
            actions.append({
                "type": "list_running_apps",
                "params": {},
                "description": "List running apps"
            })

        if metrics["disk_percent"] >= config.get("disk_percent", 90):
            downloads_dir = str(self.brain.actions.user_home / "Downloads")
            actions.append({
                "type": "list_directory",
                "params": {"directory": downloads_dir},
                "description": "List Downloads folder"
            })

        return actions

    def monitor_loop(self):
        config = self.brain.config.get("monitoring", {})
        suggestions_config = self.brain.config.get("proactive_suggestions", {})

        interval = config.get("interval_sec", 30)
        cooldown = suggestions_config.get("cooldown_sec", 600)
        suggestions_enabled = suggestions_config.get("enabled", False)
        auto_queue = suggestions_config.get("auto_queue_actions", False)

        while True:
            if not self.is_quiet_hours(config):
                metrics = self.get_system_metrics()
                alerts = []

                if metrics["cpu_percent"] >= config.get("cpu_percent", 85):
                    alerts.append(f"High CPU usage: {metrics['cpu_percent']:.0f}%")
                if metrics["memory_percent"] >= config.get("memory_percent", 85):
                    alerts.append(f"High memory usage: {metrics['memory_percent']:.0f}%")
                if metrics["disk_percent"] >= config.get("disk_percent", 90):
                    alerts.append(f"Low disk space: {metrics['disk_percent']:.0f}% used")

                if alerts:
                    self.add_message("System", " | ".join(alerts), "system")

                    if suggestions_enabled:
                        now = time.monotonic()
                        if now - self.last_suggestion_time >= cooldown:
                            actions = self.build_suggestion_actions(metrics, config)
                            suggestion = self.build_suggestion(metrics, config)
                            if suggestion:
                                self.add_message("Sollie", suggestion, "assistant")

                            if auto_queue and actions and not self.pending_action and not self.pending_actions:
                                self.pending_actions = actions
                                self.pending_action = self.pending_actions.pop(0)
                                self.show_approval_request(self.pending_action)

                            self.last_suggestion_time = now

            time.sleep(interval)
    
    def show_settings(self):
        """Show settings window"""
        settings_window = ctk.CTkToplevel(self.window)
        settings_window.title("Sollie Settings")
        settings_window.geometry("500x400")
        settings_window.configure(fg_color=COLORS["bg"])
        
        ctk.CTkLabel(
            settings_window,
            text="Settings",
            font=FONTS["section"],
            text_color=COLORS["text"]
        ).pack(pady=20)
        
        # Connection test
        test_btn = ctk.CTkButton(
            settings_window,
            text="Test LM Studio Connection",
            command=self.test_lm_studio,
            fg_color=COLORS["panel_alt"],
            hover_color=COLORS["outline"],
            text_color=COLORS["text"]
        )
        test_btn.pack(pady=10)
        
        # View action log
        log_btn = ctk.CTkButton(
            settings_window,
            text="View Action Log",
            command=self.show_action_log,
            fg_color=COLORS["panel_alt"],
            hover_color=COLORS["outline"],
            text_color=COLORS["text"]
        )
        log_btn.pack(pady=10)
        
        # Clear memory
        clear_btn = ctk.CTkButton(
            settings_window,
            text="Clear Conversation History",
            command=self.clear_memory,
            fg_color=COLORS["warning"],
            hover_color="#d89a3d",
            text_color=COLORS["bg"]
        )
        clear_btn.pack(pady=10)
    
    def test_lm_studio(self):
        """Test connection to LM Studio"""
        self.add_message("System", "Testing LM Studio connection...", "system")
        
        def test():
            result = self.brain.test_connection()
            if result['success']:
                self.add_message("System", f"✓ Connected! Response: {result['response']}", "system")
            else:
                self.add_message("System", f"✗ Connection failed: {result['error']}", "system")
        
        thread = threading.Thread(target=test)
        thread.daemon = True
        thread.start()
    
    def show_action_log(self):
        """Show recent actions"""
        actions = self.brain.memory.get_recent_actions(limit=5)
        
        if not actions:
            self.add_message("System", "No recent actions.", "system")
            return
        
        self.add_message("System", "Recent Actions:", "system")
        for action in actions:
            status = "✓ Approved" if action['approved'] else "✗ Denied"
            self.add_message("System", f"  {status} - {action['action_type']}: {action['details']}", "system")
    
    def clear_memory(self):
        """Clear conversation history"""
        self.brain.memory.clear_old_conversations(keep_last=0)
        self.add_message("System", "Conversation history cleared.", "system")
    
    def run(self):
        """Start the GUI"""
        self.window.mainloop()


if __name__ == "__main__":
    app = SollieGUI()
    app.run()
