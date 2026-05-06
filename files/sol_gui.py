"""
Sol GUI - Modern Cyberpunk Edition
Refined cyberpunk aesthetic with clean, professional design
"""

import customtkinter as ctk
import tkinter as tk
import threading
import queue
import os
import time
import re
import json
import math
import random
from tkinter import filedialog
from datetime import datetime
import psutil
from sol_core import SolCore

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

COLORS = {
    "bg": "#0d1117",
    "panel": "#161b22",
    "panel_alt": "#21262d",
    "panel_hover": "#30363d",
    "border": "#30363d",
    "border_focus": "#58a6ff",
    "text": "#e6edf3",
    "text_dim": "#8b949e",
    "text_muted": "#6e7681",
    "accent": "#58a6ff",
    "accent_hover": "#79c0ff",
    "accent_dim": "#388bfd",
    "primary": "#238636",
    "primary_hover": "#2ea043",
    "danger": "#f85149",
    "danger_hover": "#ff7b72",
    "warning": "#d29922",
    "success": "#3fb950",
    "info": "#58a6ff",
    "purple": "#a371f7",
    "pink": "#db61a2",
    "cyan": "#39c5cf",
    "orange": "#f0883e",
}

FONTS = {
    "title": ("Segoe UI", 22, "bold"),
    "heading": ("Segoe UI Semibold", 16),
    "subhead": ("Segoe UI Semibold", 14),
    "body": ("Segoe UI", 14),
    "body_bold": ("Segoe UI Semibold", 14),
    "mono": ("Cascadia Code", 13),
    "small": ("Segoe UI", 12),
    "tiny": ("Segoe UI", 11),
}

ICONS = {
    "chat": "💬",
    "terminal": "⌨️",
    "settings": "⚙️",
    "brain": "🧠",
    "pulse": "💓",
    "memory": "💾",
    "gpu": "🎮",
    "check": "✓",
    "x": "✕",
    "arrow": "→",
}


class AnimatedProgressBar(tk.Canvas):
    def __init__(self, parent, **kwargs):
        self.height = kwargs.pop("height", 4)
        self.corner_radius = kwargs.pop("corner_radius", 2)
        self.bar_color = kwargs.pop("bar_color", COLORS["accent"])
        self.bg_color = kwargs.pop("bg_color", COLORS["panel_alt"])
        
        super().__init__(parent, height=self.height, highlightthickness=0, bg=self.bg_color, **kwargs)
        
        self.bar_value = 0
        self.glow_phase = 0
        self._draw_bar()
        
    def _draw_bar(self):
        self.delete("all")
        w = self.winfo_width()
        if w < 1:
            w = 100
        
        bar_width = int(w * self.bar_value)
        
        self.create_rectangle(
            0, 0, w, self.height,
            fill=self.bg_color, outline=""
        )
        
        if bar_width > 0:
            glow = COLORS[self.bar_color] if isinstance(self.bar_color, str) else self.bar_color
            if "accent" in str(self.bar_color).lower():
                alpha = 80 + 40 * math.sin(self.glow_phase)
            else:
                alpha = 80
            
            self.create_rectangle(
                0, 0, bar_width, self.height,
                fill=glow, outline=""
            )
            
    def set(self, value, animate=True):
        self.bar_value = max(0, min(1, value))
        self._draw_bar()
        
    def get(self):
        return self.bar_value
        
    def configure(self, **kwargs):
        if "bar_color" in kwargs:
            self.bar_color = kwargs.pop("bar_color")
        if "bg_color" in kwargs:
            self.bg_color = kwargs.pop("bg_color")
        self._draw_bar()


class SolGUI:
    def __init__(self):
        self.brain = SolCore()
        self.pending_action = None
        self.pending_actions = []
        self.last_suggestion_time = 0
        self.last_assistant_message = ""
        self.connection_status = "UNKNOWN"
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        
        self.last_response_seconds = None
        self.last_tool_confidence = None
        self.last_gpu_refresh = 0.0
        self.gpu_name = "N/A"
        self.gpu_vram_gb = None
        self.mood = "calm"
        
        self.brain.actions.register_reminder_callback(self._on_reminder)
        
        agent_config = self.brain.config.get("agent", {})
        monitoring_config = self.brain.config.get("monitoring", {})
        suggestions_config = self.brain.config.get("proactive_suggestions", {})
        
        self.task_enabled = bool(agent_config.get("enabled", True))
        self.monitoring_enabled = bool(monitoring_config.get("enabled", True))
        self.suggestions_enabled = bool(suggestions_config.get("enabled", False))
        self.auto_queue_enabled = bool(suggestions_config.get("auto_queue_actions", False))
        
        self.window = ctk.CTk()
        self.window.title("SOL")
        self.window.geometry("1280x800")
        self.window.minsize(1100, 700)
        self.window.configure(fg_color=COLORS["bg"])
        
        self.ui_queue = queue.Queue()
        self.window.after(100, self.process_ui_queue)
        
        self.setup_ui()
        self.start_monitoring()
        
    def setup_ui(self):
        self.window.rowconfigure(0, weight=1)
        self.window.columnconfigure(0, weight=1)
        
        main = ctk.CTkFrame(self.window, fg_color="transparent", corner_radius=0)
        main.grid(row=0, column=0, sticky="nsew")
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)
        
        sidebar = self._build_sidebar(main)
        content = self._build_content(main)
        
    def _build_sidebar(self, parent):
        sidebar = ctk.CTkFrame(
            parent,
            width=260,
            fg_color=COLORS["panel"],
            corner_radius=0,
            border_width=1,
            border_color=COLORS["border"]
        )
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 1), pady=0)
        sidebar.grid_rowconfigure(0, weight=0)
        sidebar.grid_rowconfigure(1, weight=1)
        sidebar.grid_rowconfigure(100, weight=1)
        
        header = ctk.CTkFrame(sidebar, fg_color="transparent", corner_radius=0, height=80)
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        header.grid_columnconfigure(0, weight=1)
        
        logo = ctk.CTkLabel(
            header,
            text="SOL",
            font=("Segoe UI", 28, "bold"),
            text_color=COLORS["accent"]
        )
        logo.grid(row=0, column=0, sticky="w")
        
        tagline = ctk.CTkLabel(
            header,
            text="Neural Assistant",
            font=FONTS["small"],
            text_color=COLORS["text_muted"]
        )
        tagline.grid(row=1, column=0, sticky="w", pady=(0, 0))
        
        self.status_indicator = ctk.CTkFrame(
            sidebar,
            fg_color=COLORS["panel_alt"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"]
        )
        self.status_indicator.grid(row=1, column=0, sticky="ew", padx=16, pady=(8, 16))
        
        status_row = ctk.CTkFrame(self.status_indicator, fg_color="transparent", corner_radius=0)
        status_row.pack(fill="x", padx=12, pady=(10, 6))
        
        self.status_dot = tk.Canvas(
            status_row,
            width=10, height=10,
            highlightthickness=0,
            bg=COLORS["panel_alt"]
        )
        self.status_dot.pack(side="left", pady=6)
        self.status_dot.create_oval(1, 1, 9, 9, fill=COLORS["success"], outline="")
        
        self.status_text = ctk.CTkLabel(
            status_row,
            text="Ready",
            font=FONTS["body_bold"],
            text_color=COLORS["success"]
        )
        self.status_text.pack(side="left", padx=(8, 0))
        
        conn_row = ctk.CTkFrame(self.status_indicator, fg_color="transparent", corner_radius=0)
        conn_row.pack(fill="x", padx=12, pady=(0, 10))
        
        self.conn_text = ctk.CTkLabel(
            conn_row,
            text="Model: Unknown",
            font=FONTS["small"],
            text_color=COLORS["text_muted"]
        )
        self.conn_text.pack(side="left")
        
        quick_label = ctk.CTkLabel(
            sidebar,
            text="Quick Actions",
            font=FONTS["subhead"],
            text_color=COLORS["text_dim"]
        )
        quick_label.grid(row=2, column=0, sticky="w", padx=16, pady=(16, 8))
        
        quick_actions = [
            ("List Desktop", "List my Desktop files"),
            ("Open Downloads", "Open Downloads folder"),
            ("Open Documents", "Open Documents folder"),
            ("System Status", "What's my PC status?"),
        ]
        
        for i, (label, msg) in enumerate(quick_actions):
            is_alt = i % 2 == 1
            btn = ctk.CTkButton(
                sidebar,
                text=label,
                command=lambda m=msg: self.send_quick_message(m),
                fg_color=COLORS["panel_alt"] if not is_alt else COLORS["panel_hover"],
                hover_color=COLORS["border"],
                text_color=COLORS["text"],
                font=FONTS["small"],
                height=36,
                corner_radius=8
            )
            btn.grid(row=3+i, column=0, sticky="ew", padx=16, pady=4)
        
        system_label = ctk.CTkLabel(
            sidebar,
            text="System",
            font=FONTS["subhead"],
            text_color=COLORS["text_dim"]
        )
        system_label.grid(row=10, column=0, sticky="w", padx=16, pady=(20, 8))
        
        self.cpu_label = ctk.CTkLabel(
            sidebar,
            text="CPU: 0%",
            font=FONTS["small"],
            text_color=COLORS["text"]
        )
        self.cpu_label.grid(row=11, column=0, sticky="w", padx=16, pady=(4, 2))
        
        self.mem_label = ctk.CTkLabel(
            sidebar,
            text="Memory: 0%",
            font=FONTS["small"],
            text_color=COLORS["text"]
        )
        self.mem_label.grid(row=12, column=0, sticky="w", padx=16, pady=(2, 2))
        
        self.gpu_label = ctk.CTkLabel(
            sidebar,
            text="GPU: --",
            font=FONTS["small"],
            text_color=COLORS["text"]
        )
        self.gpu_label.grid(row=13, column=0, sticky="w", padx=16, pady=(2, 16))
        
        self.task_var = tk.BooleanVar(value=self.task_enabled)
        self.monitor_var = tk.BooleanVar(value=self.monitoring_enabled)
        self.suggest_var = tk.BooleanVar(value=self.suggestions_enabled)
        self.auto_queue_var = tk.BooleanVar(value=self.auto_queue_enabled)
        
        options = [
            ("Task Mode", self.task_var, self.toggle_task_mode),
            ("Monitoring", self.monitor_var, self.toggle_monitoring),
            ("Suggestions", self.suggest_var, self.toggle_suggestions),
            ("Auto-Queue", self.auto_queue_var, self.toggle_auto_queue),
        ]
        
        for i, (label, var, cmd) in enumerate(options):
            switch = ctk.CTkSwitch(
                sidebar,
                text=label,
                variable=var,
                command=cmd,
                font=FONTS["small"],
                text_color=COLORS["text_dim"]
            )
            switch.grid(row=20+i, column=0, sticky="w", padx=16, pady=6)
        
        settings_btn = ctk.CTkButton(
            sidebar,
            text="Settings",
            command=self.show_settings,
            fg_color=COLORS["panel_hover"],
            hover_color=COLORS["border"],
            text_color=COLORS["text"],
            font=FONTS["small"],
            height=40
        )
        settings_btn.grid(row=99, column=0, sticky="ew", padx=16, pady=(16, 16))
        
        return sidebar
    
    def _build_content(self, parent):
        content = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        content.grid_rowconfigure(1, weight=1)
        content.grid_columnconfigure(0, weight=1)
        
        header = self._build_header(content)
        
        chat_frame = ctk.CTkFrame(
            content,
            fg_color=COLORS["panel"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"]
        )
        chat_frame.grid(row=1, column=0, sticky="nsew", padx=(16, 16), pady=(0, 12))
        chat_frame.grid_rowconfigure(0, weight=1)
        chat_frame.grid_columnconfigure(0, weight=1)
        
        self.chat_display = ctk.CTkTextbox(
            chat_frame,
            font=FONTS["body"],
            wrap="word",
            state="disabled",
            fg_color=COLORS["panel"],
            text_color=COLORS["text"],
            border_width=0,
            scrollbar_button_color=COLORS["panel_hover"],
            scrollbar_button_hover_color=COLORS["border"]
        )
        self.chat_display.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=(12, 6))
        self.configure_chat_tags()
        
        input_frame = ctk.CTkFrame(
            content,
            fg_color=COLORS["panel"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"]
        )
        input_frame.grid(row=2, column=0, sticky="ew", padx=(16, 16), pady=(0, 16))
        input_frame.grid_columnconfigure(0, weight=1)
        
        self.input_box = ctk.CTkEntry(
            input_frame,
            placeholder_text="Message Sol...",
            font=FONTS["body"],
            height=48,
            fg_color=COLORS["panel_alt"],
            text_color=COLORS["text"],
            placeholder_text_color=COLORS["text_muted"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=8
        )
        self.input_box.grid(row=0, column=0, sticky="ew", padx=(12, 8), pady=12)
        self.input_box.bind("<Return>", lambda e: self.send_message())
        
        self.send_btn = ctk.CTkButton(
            input_frame,
            text="Send",
            command=self.send_message,
            width=100,
            height=40,
            font=FONTS["body_bold"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#ffffff",
            corner_radius=8
        )
        self.send_btn.grid(row=0, column=1, padx=(0, 12), pady=12)
        
        footer = ctk.CTkFrame(input_frame, fg_color="transparent", corner_radius=0)
        footer.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 8))
        footer.grid_columnconfigure((0, 2), weight=1)
        
        copy_btn = ctk.CTkButton(
            footer,
            text="Copy",
            command=self.copy_last_response,
            fg_color="transparent",
            hover_color=COLORS["panel_hover"],
            text_color=COLORS["text_dim"],
            font=FONTS["tiny"],
            height=28
        )
        copy_btn.grid(row=0, column=0, sticky="w")
        
        export_btn = ctk.CTkButton(
            footer,
            text="Export",
            command=self.export_chat_history,
            fg_color="transparent",
            hover_color=COLORS["panel_hover"],
            text_color=COLORS["text_dim"],
            font=FONTS["tiny"],
            height=28
        )
        export_btn.grid(row=0, column=1, sticky="w", padx=8)
        
        self.queue_label = ctk.CTkLabel(
            footer,
            text="",
            font=FONTS["tiny"],
            text_color=COLORS["text_muted"]
        )
        self.queue_label.grid(row=0, column=2, sticky="e")
        
        self.refresh_gpu_info()
        self.add_message("System", "Hello! I'm Sol, your AI assistant.", "assistant")
        
        return content
    
    def _build_header(self, parent):
        header = ctk.CTkFrame(
            parent,
            fg_color=COLORS["panel"],
            corner_radius=0,
            border_width=1,
            border_color=COLORS["border"],
            height=60
        )
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=(16, 0))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)
        
        title = ctk.CTkLabel(
            header,
            text="Neural Interface",
            font=FONTS["heading"],
            text_color=COLORS["text"]
        )
        title.grid(row=0, column=0, sticky="w", padx=20)
        
        clock_frame = ctk.CTkFrame(header, fg_color="transparent", corner_radius=0)
        clock_frame.grid(row=0, column=1, sticky="e", padx=20)
        
        self.clock_label = ctk.CTkLabel(
            clock_frame,
            text="00:00:00",
            font=FONTS["body_bold"],
            text_color=COLORS["accent"]
        )
        self.clock_label.pack(side="right")
        
        self.window.after(100, self._update_clock)
        
        return header
    
    def _update_clock(self):
        try:
            now = datetime.now()
            self.clock_label.configure(text=now.strftime("%H:%M:%S"))
        except Exception:
            pass
        self.window.after(1000, self._update_clock)
    
    def configure_chat_tags(self):
        text = self.chat_display._textbox
        
        colors = [
            ("user_name", COLORS["pink"]),
            ("assistant_name", COLORS["accent"]),
            ("system_name", COLORS["warning"]),
            ("action_name", COLORS["danger"]),
        ]
        for tag, color in colors:
            try:
                text.tag_config(tag, foreground=color, font=FONTS["body_bold"])
            except Exception:
                pass
        
        try:
            text.tag_config("user_msg", foreground=COLORS["text"])
            text.tag_config("assistant_msg", foreground=COLORS["text"])
            text.tag_config("system_msg", foreground=COLORS["text"])
            text.tag_config("action_msg", foreground=COLORS["text"])
            text.tag_config("code_block", foreground=COLORS["cyan"], font=FONTS["mono"])
            text.tag_config("list_item", lmargin1=20, lmargin2=28)
        except Exception:
            pass
    
    def add_message(self, sender, message, msg_type="user"):
        if threading.current_thread() is not threading.main_thread():
            self.enqueue_ui(self.add_message, sender, message, msg_type)
            return
        
        self.chat_display.configure(state="normal")
        
        timestamp = datetime.now().strftime("%H:%M")
        
        if msg_type == "user":
            self.chat_display.insert("end", f"\n[{timestamp}] You: ", "user_name")
            self.chat_display.insert("end", f"{message}\n", "user_msg")
        elif msg_type == "assistant":
            self.chat_display.insert("end", f"\n[{timestamp}] Sol: ", "assistant_name")
            self.insert_markdown(message, "assistant_msg")
            self.chat_display.insert("end", "\n")
            self.last_assistant_message = message
        elif msg_type == "system":
            self.chat_display.insert("end", f"\n[{timestamp}] System: ", "system_name")
            self.chat_display.insert("end", f"{message}\n", "system_msg")
        
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")
    
    def insert_markdown(self, text, default_tag):
        for part in text.split("```"):
            for line in part.splitlines(keepends=True):
                list_match = re.match(r"^\s*(?:[-*]|\d+\.)\s+(.*)", line)
                if list_match:
                    self.chat_display.insert("end", "• ", "list_item")
                    self.insert_inline(line, default_tag)
                else:
                    self.insert_inline(line, default_tag)
    
    def insert_inline(self, text, default_tag):
        patterns = [
            (re.compile(r"`([^`]+)`"), "code_block"),
            (re.compile(r"\*\*([^*]+)\*\*"), "user_msg"),
        ]
        
        text_widget = self.chat_display._textbox
        
        for pattern, tag in patterns:
            match = pattern.search(text)
            if match:
                text_widget.insert("end", text[:match.start()], default_tag)
                text_widget.insert("end", match.group(1), tag)
                text = text[match.end():]
        
        self.chat_display.insert("end", text, default_tag)
    
    def send_message(self):
        message = self.input_box.get().strip()
        if not message:
            return
        
        self.input_box.delete(0, "end")
        self.add_message("You", message, "user")
        self.set_status("Thinking...", COLORS["warning"])
        
        thread = threading.Thread(target=self._process_message, args=(message,))
        thread.daemon = True
        thread.start()
    
    def _process_message(self, message):
        try:
            start_time = time.monotonic()
            result = self.brain.chat(message)
            self.last_response_seconds = time.monotonic() - start_time
            
            tool_conf = result.get("tool_confidence")
            self.last_tool_confidence = tool_conf if isinstance(tool_conf, (int, float)) else None
            
            self.add_message("Sol", result["response"], "assistant")
            
            if result.get("action"):
                self.pending_action = result["action"]
                self.show_action_approval(result["action"])
            
            self.set_status("Ready", COLORS["success"])
            self.set_connection_status("Online")
            
        except Exception as e:
            self.add_message("System", f"Error: {str(e)}", "system")
            self.set_status("Error", COLORS["danger"])
            self.set_connection_status("Offline")
    
    def send_quick_message(self, message):
        self.input_box.delete(0, "end")
        self.input_box.insert(0, message)
        self.send_message()
    
    def set_status(self, text, color):
        if threading.current_thread() is not threading.main_thread():
            self.enqueue_ui(self.set_status, text, color)
            return
        
        self.status_text.configure(text=text, text_color=color)
        
        fill_color = color
        if color == COLORS["success"]:
            fill_color = "#2ea043"
        elif color == COLORS["warning"]:
            fill_color = "#d29922"
        elif color == COLORS["danger"]:
            fill_color = "#f85149"
        
        self.status_dot.delete("all")
        self.status_dot.create_oval(1, 1, 9, 9, fill=fill_color, outline="")
    
    def set_connection_status(self, status):
        self.connection_status = status.upper()
        
        color = COLORS["text_muted"]
        if self.connection_status == "ONLINE":
            color = COLORS["success"]
        elif self.connection_status == "OFFLINE":
            color = COLORS["danger"]
        
        model_name = self.brain.config.get("lm_studio", {}).get("model", "local")
        self.conn_text.configure(text=f"Model: {model_name}", text_color=color)
    
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
    
    def toggle_task_mode(self):
        self.task_enabled = bool(self.task_var.get())
        self.brain.config.setdefault("agent", {})["enabled"] = self.task_enabled
        self.save_config()
        self.add_message("System", f"Task mode {'enabled' if self.task_enabled else 'disabled'}.", "system")
    
    def toggle_monitoring(self):
        self.monitoring_enabled = bool(self.monitor_var.get())
        self.brain.config.setdefault("monitoring", {})["enabled"] = self.monitoring_enabled
        self.save_config()
    
    def toggle_suggestions(self):
        self.suggestions_enabled = bool(self.suggest_var.get())
        self.brain.config.setdefault("proactive_suggestions", {})["enabled"] = self.suggestions_enabled
        self.save_config()
    
    def toggle_auto_queue(self):
        self.auto_queue_enabled = bool(self.auto_queue_var.get())
        self.brain.config.setdefault("proactive_suggestions", {})["auto_queue_actions"] = self.auto_queue_enabled
        self.save_config()
    
    def show_settings(self):
        self.add_message("System", "Settings panel coming soon.", "system")
    
    def copy_last_response(self):
        if not self.last_assistant_message:
            self.add_message("System", "No message to copy.", "system")
            return
        
        self.window.clipboard_clear()
        self.window.clipboard_append(self.last_assistant_message)
        self.add_message("System", "Copied to clipboard.", "system")
    
    def export_chat_history(self):
        default_name = f"sol_chat_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt")],
            initialfile=default_name
        )
        if not file_path:
            return
        
        messages = self.brain.memory.get_conversation_history_with_timestamps(limit=None)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                for item in messages:
                    ts = item.get("timestamp", "")
                    role = item.get("role", "").capitalize()
                    content = item.get("content", "")
                    f.write(f"[{ts}] {role}: {content}\n")
        except Exception as e:
            self.add_message("System", f"Export failed: {str(e)}", "system")
            return
        
        self.add_message("System", f"Exported to: {file_path}", "system")
    
    def show_action_approval(self, action):
        desc = action.get("description", "Unknown action")
        self.add_message("System", f"Action pending: {desc}", "system")
        
        self.queue_label.configure(text=f"Action: {desc[:30]}...")
    
    def refresh_gpu_info(self):
        self.gpu_name = "N/A"
        self.gpu_vram_gb = None
        
        if os.name != "nt":
            return
        
        try:
            import win32com.client
            wmi = win32com.client.GetObject("winmgmts:")
            adapters = wmi.InstancesOf("Win32_VideoController")
            
            for adapter in adapters:
                name = getattr(adapter, "Name", None)
                ram = getattr(adapter, "AdapterRAM", None)
                if name:
                    self.gpu_name = name
                    if ram:
                        self.gpu_vram_gb = round(int(ram) / (1024**3), 1)
                    break
        except Exception:
            pass
        
        gpu_text = self.gpu_name
        if self.gpu_vram_gb:
            gpu_text += f" ({self.gpu_vram_gb}GB)"
        
        self.gpu_label.configure(text=f"GPU: {gpu_text}")
    
    def get_system_metrics(self, interval=1):
        try:
            return {
                "cpu_percent": psutil.cpu_percent(interval=interval),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage("/").percent
            }
        except Exception:
            return {"cpu_percent": 0, "memory_percent": 0, "disk_percent": 0}
    
    def start_monitoring(self):
        self._update_system_metrics()
        self._check_proactive_alerts()
    
    def _update_system_metrics(self):
        try:
            monitor = self.brain.monitor
            all_metrics = monitor.get_all_metrics()
            
            cpu = all_metrics.get("cpu_percent", 0)
            mem = all_metrics.get("memory_percent", 0)
            disk = all_metrics.get("disk_percent", 0)
            battery = all_metrics.get("battery_percent")
            
            self.cpu_label.configure(text=f"CPU: {cpu:.0f}%")
            self.mem_label.configure(text=f"Memory: {mem:.0f}%")
            
            extras = []
            if disk:
                extras.append(f"D: {disk:.0f}%")
            if battery is not None:
                power = "⚡" if all_metrics.get("battery_plugged") else "🔋"
                extras.append(f"{power} {battery:.0f}%")
            
            if extras:
                self.gpu_label.configure(text=" | ".join(extras))
            
        except Exception as e:
            pass
        
        self.window.after(3000, self._update_system_metrics)
    
    def _check_proactive_alerts(self):
        try:
            if not self.monitoring_enabled:
                self.window.after(10000, self._check_proactive_alerts)
                return
                
            monitor = self.brain.monitor
            all_metrics = monitor.get_all_metrics()
            alerts = []
            
            cpu = all_metrics.get("cpu_percent", 0)
            mem = all_metrics.get("memory_percent", 0)
            
            if cpu >= 85:
                alerts.append(f"⚠️ CPU at {cpu:.0f}% - consider closing apps")
            if mem >= 85:
                alerts.append(f"⚠️ Memory at {mem:.0f}% - running low")
            
            battery = all_metrics.get("battery_percent")
            if battery is not None and battery <= 15 and not all_metrics.get("battery_plugged"):
                alerts.append(f"🔋 Battery low ({battery:.0f}%) - plug in soon")
            
            if alerts and time.time() - getattr(self, '_last_alert_time', 0) > 300:
                for alert in alerts:
                    self.add_message("System", alert, "system")
                self._last_alert_time = time.time()
                
        except Exception:
            pass
        
        self.window.after(10000, self._check_proactive_alerts)
    
    def _on_reminder(self, message, reminder_data):
        """Callback for when a reminder is due"""
        try:
            self.enqueue_ui(self.add_message, "🔔 REMINDER", message, "system")
        except Exception:
            pass
    
    def save_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.brain.config, f, ensure_ascii=True, indent=2)
        except Exception as e:
            print(f"Config save failed: {e}")

    def run(self):
        self.window.mainloop()


if __name__ == "__main__":
    app = SolGUI()
    app.run()