"""
Sol GUI - Enhanced Edition
Cyberpunk aesthetic with settings panel, chat history sidebar, theme switcher, and system monitor
"""

import customtkinter as ctk
import threading
import queue
import os
import time
import re
import json
import math
import tkinter as tk
from tkinter import filedialog
from datetime import datetime
import psutil
from sol_core import SolBrain

CYBERDECK_COLORS = {
    "bg": "#0a0e27",
    "panel": "#0f1419",
    "panel_alt": "#151b2f",
    "outline": "#1a2847",
    "outline_bright": "#2a4a7f",
    "text": "#b8e6cc",
    "text_alt": "#e0e6ff",
    "muted": "#4a6fa0",
    "accent": "#66ffaa",
    "accent_alt": "#ff66a3",
    "accent_hover": "#00cc6a",
    "warning": "#ffff99",
    "danger": "#ff4466",
    "info": "#66d9ef",
    "success": "#66ffaa",
}

CLEAN_COLORS = {
    "bg": "#1e1e1e",
    "panel": "#252526",
    "panel_alt": "#2d2d2d",
    "outline": "#3e3e42",
    "outline_bright": "#5a5a5f",
    "text": "#d4d4d4",
    "text_alt": "#e0e0e0",
    "muted": "#a0a0a0",
    "accent": "#007acc",
    "accent_alt": "#4ec9b0",
    "accent_hover": "#0095f7",
    "warning": "#f1d000",
    "danger": "#f44747",
    "info": "#3aa5ff",
    "success": "#2d9d78",
}

CYBERDECK_FONTS = {
    "title": ("Courier New", 24, "bold"),
    "subtitle": ("Courier New", 14),
    "section": ("Courier New", 16, "bold"),
    "body": ("Courier New", 14),
    "body_bold": ("Courier New", 14, "bold"),
    "body_italic": ("Courier New", 14, "italic"),
    "caption": ("Courier New", 12),
    "code": ("Consolas", 13)
}

CLEAN_FONTS = {
    "title": ("Segoe UI", 20, "bold"),
    "subtitle": ("Segoe UI", 14),
    "section": ("Segoe UI", 14, "bold"),
    "body": ("Segoe UI", 14),
    "body_bold": ("Segoe UI", 14, "bold"),
    "caption": ("Segoe UI", 12),
    "code": ("Consolas", 13)
}


class SolGUI:
    def __init__(self):
        self.brain = SolBrain()
        self.pending_action = None
        self.connection_status = "UNKNOWN"
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.last_response_seconds = None
        self.last_tool_confidence = None
        self.glow_phase = 0.0
        self.current_theme = "cyberdeck"
        self.sidebar_visible = True
        self.settings_visible = False
        self._switching_theme = False

        agent_config = self.brain.config.get("agent", {})
        self.task_enabled = bool(agent_config.get("enabled", True))

        self.window = ctk.CTk()
        self.window.title("SOL AI Assistant")
        self.window.geometry("1400x850")
        self.window.minsize(1200, 700)

        self.ui_queue = queue.Queue()
        self.window.after(100, self.process_ui_queue)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.colors = CYBERDECK_COLORS.copy()
        self.fonts = CYBERDECK_FONTS.copy()

        self.setup_ui()
        self.start_monitoring()
        self.animate_glow()

    def setup_ui(self):
        self.main_frame = ctk.CTkFrame(self.window, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=0, pady=0)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        self.build_header()
        self.build_content_area()

    def build_header(self):
        header = ctk.CTkFrame(
            self.main_frame,
            fg_color=self.colors["panel_alt"],
            corner_radius=0,
            border_width=2,
            border_color=self.colors["accent"]
        )
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(1, weight=1)

        header_left = ctk.CTkFrame(header, fg_color="transparent")
        header_left.grid(row=0, column=0, sticky="w", padx=20, pady=10)

        self.title_label = ctk.CTkLabel(
            header_left,
            text="SOL AI ASSISTANT",
            font=self.fonts["title"],
            text_color=self.colors["accent"]
        )
        self.title_label.pack(side="left")

        header_right = ctk.CTkFrame(header, fg_color="transparent")
        header_right.grid(row=0, column=1, sticky="e", padx=20, pady=10)

        self.theme_var = tk.StringVar(value="cyberdeck")
        theme_dropdown = ctk.CTkOptionMenu(
            header_right,
            variable=self.theme_var,
            values=["cyberdeck", "clean"],
            command=self.switch_theme,
            fg_color=self.colors["panel"],
            button_color=self.colors["outline_bright"],
            button_hover_color=self.colors["accent"],
            text_color=self.colors["text_alt"],
            font=self.fonts["caption"],
            width=120,
            height=30
        )
        theme_dropdown.pack(side="left", padx=(0, 10))

        self.sysmon_label = ctk.CTkLabel(
            header_right,
            text="CPU: --% | RAM: --%",
            font=self.fonts["caption"],
            text_color=self.colors["info"]
        )
        self.sysmon_label.pack(side="left", padx=(0, 10))

        indicators = ctk.CTkFrame(header_right, fg_color="transparent")
        indicators.pack(side="left", padx=(0, 10))

        self.status_label = ctk.CTkLabel(
            indicators,
            text="READY",
            font=self.fonts["body_bold"],
            text_color=self.colors["success"]
        )
        self.status_label.pack(side="left", padx=10)

        self.connection_label = ctk.CTkLabel(
            indicators,
            text="LM: OFFLINE",
            font=self.fonts["caption"],
            text_color=self.colors["danger"]
        )
        self.connection_label.pack(side="left", padx=10)

        self.time_label = ctk.CTkLabel(
            indicators,
            text="00:00:00",
            font=self.fonts["caption"],
            text_color=self.colors["info"]
        )
        self.time_label.pack(side="left", padx=10)

        settings_btn = ctk.CTkButton(
            header_right,
            text="Settings",
            command=self.toggle_settings,
            fg_color=self.colors["panel"],
            hover_color=self.colors["outline_bright"],
            text_color=self.colors["accent"],
            border_width=1,
            border_color=self.colors["accent"],
            font=self.fonts["caption"],
            height=30,
            width=80
        )
        settings_btn.pack(side="left", padx=(0, 10))

        history_btn = ctk.CTkButton(
            header_right,
            text="History",
            command=self.toggle_sidebar,
            fg_color=self.colors["panel"],
            hover_color=self.colors["outline_bright"],
            text_color=self.colors["info"],
            border_width=1,
            border_color=self.colors["info"],
            font=self.fonts["caption"],
            height=30,
            width=80
        )
        history_btn.pack(side="left")

        accent_line = ctk.CTkFrame(
            header,
            fg_color=self.colors["accent"],
            height=3
        )
        accent_line.grid(row=1, column=0, columnspan=2, sticky="ew")

    def build_content_area(self):
        self.content_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.content_container.grid(row=1, column=0, sticky="nsew", padx=15, pady=15)
        self.content_container.grid_columnconfigure(1, weight=1)
        self.content_container.grid_rowconfigure(0, weight=1)

        self.build_sidebar()
        self.build_main_panel()
        self.build_settings_panel()

    def build_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(
            self.content_container,
            fg_color=self.colors["panel"],
            corner_radius=8,
            border_width=1,
            border_color=self.colors["outline"],
            width=250
        )
        self.sidebar_frame.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self.sidebar_frame.grid_propagate(False)

        sidebar_title = ctk.CTkLabel(
            self.sidebar_frame,
            text="Chat History",
            font=self.fonts["section"],
            text_color=self.colors["accent"]
        )
        sidebar_title.pack(pady=(15, 10), padx=10)

        self.history_scroll = ctk.CTkScrollableFrame(
            self.sidebar_frame,
            fg_color="transparent"
        )
        self.history_scroll.pack(fill="both", expand=True, padx=10, pady=5)

        self.load_chat_history()

    def build_main_panel(self):
        main_panel = ctk.CTkFrame(self.content_container, fg_color="transparent")
        main_panel.grid(row=0, column=1, sticky="nsew")
        main_panel.grid_columnconfigure(0, weight=1)
        main_panel.grid_rowconfigure(1, weight=1)

        chat_title = ctk.CTkLabel(
            main_panel,
            text="Chat",
            font=self.fonts["section"],
            text_color=self.colors["accent"],
            anchor="w"
        )
        chat_title.grid(row=0, column=0, sticky="w", pady=(0, 8))

        chat_frame = ctk.CTkFrame(
            main_panel,
            fg_color=self.colors["panel"],
            corner_radius=8,
            border_width=1,
            border_color=self.colors["outline"]
        )
        chat_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 15))

        self.chat_display = tk.Text(
            chat_frame,
            bg=self.colors["panel"],
            fg=self.colors["text_alt"],
            font=("Consolas", 13),
            wrap="word",
            relief="flat",
            borderwidth=0,
            padx=15,
            pady=15,
            insertbackground=self.colors["accent"]
        )
        self.chat_display.pack(fill="both", expand=True)
        self.chat_display.configure(state="disabled")

        self.chat_display.tag_config("user_name", foreground=self.colors["accent_alt"], font=("Consolas", 12, "bold"))
        self.chat_display.tag_config("user_msg", foreground=self.colors["text_alt"])
        self.chat_display.tag_config("assistant_name", foreground=self.colors["accent"], font=("Consolas", 12, "bold"))
        self.chat_display.tag_config("assistant_msg", foreground=self.colors["text_alt"])
        self.chat_display.tag_config("system_name", foreground=self.colors["warning"], font=("Consolas", 12, "bold"))
        self.chat_display.tag_config("system_msg", foreground=self.colors["info"])
        self.chat_display.tag_config("code_block", foreground=self.colors["info"], font=("Consolas", 12))

        input_frame = ctk.CTkFrame(main_panel, fg_color="transparent")
        input_frame.grid(row=2, column=0, sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)

        input_container = ctk.CTkFrame(
            input_frame,
            fg_color=self.colors["panel_alt"],
            corner_radius=8,
            border_width=1,
            border_color=self.colors["outline_bright"]
        )
        input_container.grid(row=0, column=0, sticky="ew")
        input_container.grid_columnconfigure(0, weight=1)

        self.input_box = ctk.CTkEntry(
            master=input_frame,
            font=self.fonts["body"],
            fg_color=self.colors["panel_alt"],
            text_color=self.colors["text"],
            border_color=self.colors["outline"],
            border_width=1,
            placeholder_text="Type your message to Sol...",
            height=40
        )
        self.input_box.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        self.input_box.bind("<Return>", lambda e: self.send_message())
        
        # Bind Ctrl+V to handle image paste attempts
        self.input_box.bind("<Control-v>", self._handle_paste)

        button_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        button_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        send_btn = ctk.CTkButton(
            button_frame,
            text="Send",
            command=self.send_message,
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_hover"],
            text_color=self.colors["bg"],
            font=self.fonts["body_bold"],
            height=40,
            width=100
        )
        send_btn.pack(side="left", padx=(0, 8))

        clear_btn = ctk.CTkButton(
            button_frame,
            text="Clear",
            command=self.clear_chat,
            fg_color=self.colors["panel_alt"],
            hover_color=self.colors["outline"],
            text_color=self.colors["text"],
            font=self.fonts["body_bold"],
            height=40,
            width=100
        )
        clear_btn.pack(side="left", padx=(0, 8))

        export_btn = ctk.CTkButton(
            button_frame,
            text="Export",
            command=self.export_chat,
            fg_color=self.colors["panel_alt"],
            hover_color=self.colors["outline"],
            text_color=self.colors["info"],
            font=self.fonts["body_bold"],
            height=40,
            width=100
        )
        export_btn.pack(side="left")

        self.add_message("SYSTEM", "SOL initialized. Ready.", "system")

    def build_settings_panel(self):
        self.settings_frame = ctk.CTkFrame(
            self.content_container,
            fg_color=self.colors["panel"],
            corner_radius=8,
            border_width=1,
            border_color=self.colors["outline"],
            width=350
        )
        self.settings_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        self.settings_frame.grid_propagate(False)
        self.settings_frame.grid_remove()

        settings_title = ctk.CTkLabel(
            self.settings_frame,
            text="Settings",
            font=self.fonts["section"],
            text_color=self.colors["accent"]
        )
        settings_title.pack(pady=(15, 10), padx=10)

        settings_scroll = ctk.CTkScrollableFrame(
            self.settings_frame,
            fg_color="transparent"
        )
        settings_scroll.pack(fill="both", expand=True, padx=10, pady=5)

        self.build_settings_lm_studio(settings_scroll)
        self.build_settings_personality(settings_scroll)
        self.build_settings_emotion(settings_scroll)
        self.build_settings_memory(settings_scroll)

        save_btn = ctk.CTkButton(
            self.settings_frame,
            text="Save Settings",
            command=self.save_settings,
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_hover"],
            text_color=self.colors["bg"],
            font=self.fonts["body_bold"],
            height=40
        )
        save_btn.pack(pady=(10, 15), padx=10, fill="x")

    def build_settings_lm_studio(self, parent):
        section = ctk.CTkLabel(
            parent,
            text="LM Studio",
            font=self.fonts["section"],
            text_color=self.colors["accent_alt"],
            anchor="w"
        )
        section.pack(fill="x", pady=(10, 5), padx=5)

        lm_config = self.brain.config.get("lm_studio", {})

        ctk.CTkLabel(parent, text="API URL", font=self.fonts["caption"], text_color=self.colors["muted"], anchor="w").pack(fill="x", padx=5)
        self.settings_api_url = ctk.CTkEntry(parent, fg_color=self.colors["panel"], text_color=self.colors["text"], font=self.fonts["body"])
        self.settings_api_url.insert(0, lm_config.get("api_url", "http://localhost:1234/v1"))
        self.settings_api_url.pack(fill="x", padx=5, pady=(0, 10))

        ctk.CTkLabel(parent, text="Model", font=self.fonts["caption"], text_color=self.colors["muted"], anchor="w").pack(fill="x", padx=5)
        self.settings_model = ctk.CTkEntry(parent, fg_color=self.colors["panel"], text_color=self.colors["text"], font=self.fonts["body"])
        self.settings_model.insert(0, lm_config.get("model", "local-model"))
        self.settings_model.pack(fill="x", padx=5, pady=(0, 10))

        ctk.CTkLabel(parent, text="Temperature", font=self.fonts["caption"], text_color=self.colors["muted"], anchor="w").pack(fill="x", padx=5)
        self.settings_temp = ctk.CTkSlider(parent, from_=0.0, to=1.0, number_of_steps=10, fg_color=self.colors["outline"], button_color=self.colors["accent"])
        self.settings_temp.set(lm_config.get("temperature", 0.7))
        self.settings_temp.pack(fill="x", padx=5, pady=(0, 5))
        self.settings_temp_label = ctk.CTkLabel(parent, text=f"{lm_config.get('temperature', 0.7):.1f}", font=self.fonts["caption"], text_color=self.colors["text"])
        self.settings_temp_label.pack(pady=(0, 10), padx=5)
        self.settings_temp.configure(command=lambda v: self.settings_temp_label.configure(text=f"{float(v):.1f}"))

        ctk.CTkLabel(parent, text="Max Tokens", font=self.fonts["caption"], text_color=self.colors["muted"], anchor="w").pack(fill="x", padx=5)
        self.settings_max_tokens = ctk.CTkEntry(parent, fg_color=self.colors["panel"], text_color=self.colors["text"], font=self.fonts["body"])
        self.settings_max_tokens.insert(0, str(lm_config.get("max_tokens", 500)))
        self.settings_max_tokens.pack(fill="x", padx=5, pady=(0, 10))

    def build_settings_personality(self, parent):
        section = ctk.CTkLabel(
            parent,
            text="Personality",
            font=self.fonts["section"],
            text_color=self.colors["accent_alt"],
            anchor="w"
        )
        section.pack(fill="x", pady=(10, 5), padx=5)

        sol_config = self.brain.config.get("sol", {})

        ctk.CTkLabel(parent, text="Name", font=self.fonts["caption"], text_color=self.colors["muted"], anchor="w").pack(fill="x", padx=5)
        self.settings_name = ctk.CTkEntry(parent, fg_color=self.colors["panel"], text_color=self.colors["text"], font=self.fonts["body"])
        self.settings_name.insert(0, sol_config.get("name", "Sol"))
        self.settings_name.pack(fill="x", padx=5, pady=(0, 10))

        ctk.CTkLabel(parent, text="Approval Required", font=self.fonts["caption"], text_color=self.colors["muted"], anchor="w").pack(fill="x", padx=5)
        self.settings_approval = ctk.CTkCheckBox(
            parent,
            text="Require action approval",
            font=self.fonts["body"],
            text_color=self.colors["text"],
            fg_color=self.colors["accent"],
            checkbox_height=18,
            checkbox_width=18
        )
        if sol_config.get("approval_required", True):
            self.settings_approval.select()
        self.settings_approval.pack(anchor="w", padx=5, pady=(0, 10))

    def build_settings_emotion(self, parent):
        section = ctk.CTkLabel(
            parent,
            text="Emotion System",
            font=self.fonts["section"],
            text_color=self.colors["accent_alt"],
            anchor="w"
        )
        section.pack(fill="x", pady=(10, 5), padx=5)

        emotion_config = self.brain.config.get("emotion", {})

        self.settings_emotion_enabled = ctk.CTkCheckBox(
            parent,
            text="Enable emotion system",
            font=self.fonts["body"],
            text_color=self.colors["text"],
            fg_color=self.colors["accent"],
            checkbox_height=18,
            checkbox_width=18
        )
        if emotion_config.get("enabled", True):
            self.settings_emotion_enabled.select()
        self.settings_emotion_enabled.pack(anchor="w", padx=5, pady=(0, 5))

        self.settings_curiosity = ctk.CTkCheckBox(
            parent,
            text="Enable curiosity",
            font=self.fonts["body"],
            text_color=self.colors["text"],
            fg_color=self.colors["accent"],
            checkbox_height=18,
            checkbox_width=18
        )
        if emotion_config.get("curiosity_enabled", True):
            self.settings_curiosity.select()
        self.settings_curiosity.pack(anchor="w", padx=5, pady=(0, 10))

        ctk.CTkLabel(parent, text="Mood Decay", font=self.fonts["caption"], text_color=self.colors["muted"], anchor="w").pack(fill="x", padx=5)
        self.settings_mood_decay = ctk.CTkSlider(parent, from_=0.0, to=1.0, number_of_steps=20, fg_color=self.colors["outline"], button_color=self.colors["accent"])
        self.settings_mood_decay.set(emotion_config.get("mood_decay", 0.15))
        self.settings_mood_decay.pack(fill="x", padx=5, pady=(0, 5))
        self.settings_mood_decay_label = ctk.CTkLabel(parent, text=f"{emotion_config.get('mood_decay', 0.15):.2f}", font=self.fonts["caption"], text_color=self.colors["text"])
        self.settings_mood_decay_label.pack(pady=(0, 10), padx=5)
        self.settings_mood_decay.configure(command=lambda v: self.settings_mood_decay_label.configure(text=f"{float(v):.2f}"))

    def build_settings_memory(self, parent):
        section = ctk.CTkLabel(
            parent,
            text="Memory",
            font=self.fonts["section"],
            text_color=self.colors["accent_alt"],
            anchor="w"
        )
        section.pack(fill="x", pady=(10, 5), padx=5)

        memory_config = self.brain.config.get("memory", {})

        self.settings_rag = ctk.CTkCheckBox(
            parent,
            text="Enable RAG retrieval",
            font=self.fonts["body"],
            text_color=self.colors["text"],
            fg_color=self.colors["accent"],
            checkbox_height=18,
            checkbox_width=18
        )
        if memory_config.get("rag_enabled", True):
            self.settings_rag.select()
        self.settings_rag.pack(anchor="w", padx=5, pady=(0, 5))

        self.settings_summary = ctk.CTkCheckBox(
            parent,
            text="Enable conversation summaries",
            font=self.fonts["body"],
            text_color=self.colors["text"],
            fg_color=self.colors["accent"],
            checkbox_height=18,
            checkbox_width=18
        )
        if memory_config.get("summary_enabled", True):
            self.settings_summary.select()
        self.settings_summary.pack(anchor="w", padx=5, pady=(0, 5))

        self.settings_long_term = ctk.CTkCheckBox(
            parent,
            text="Enable long-term memory",
            font=self.fonts["body"],
            text_color=self.colors["text"],
            fg_color=self.colors["accent"],
            checkbox_height=18,
            checkbox_width=18
        )
        if memory_config.get("long_term_memory_enabled", True):
            self.settings_long_term.select()
        self.settings_long_term.pack(anchor="w", padx=5, pady=(0, 10))

        ctk.CTkLabel(parent, text="Max Conversation History", font=self.fonts["caption"], text_color=self.colors["muted"], anchor="w").pack(fill="x", padx=5)
        self.settings_conv_history = ctk.CTkEntry(parent, fg_color=self.colors["panel"], text_color=self.colors["text"], font=self.fonts["body"])
        self.settings_conv_history.insert(0, str(memory_config.get("max_conversation_history", 50)))
        self.settings_conv_history.pack(fill="x", padx=5, pady=(0, 10))

    def load_chat_history(self):
        for widget in self.history_scroll.winfo_children():
            widget.destroy()

        memory = self.brain.memory
        history = memory.get_conversation_history_with_timestamps(limit=100)

        if not history:
            ctk.CTkLabel(
                self.history_scroll,
                text="No conversations yet",
                font=self.fonts["caption"],
                text_color=self.colors["muted"]
            ).pack(pady=20)
            return

        grouped = {}
        for entry in history:
            ts = entry.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts)
                    date_key = dt.strftime("%Y-%m-%d")
                except Exception:
                    date_key = "Unknown"
            else:
                date_key = "Unknown"

            if date_key not in grouped:
                grouped[date_key] = []
            grouped[date_key].append(entry)

        for date_key in sorted(grouped.keys(), reverse=True):
            date_label = ctk.CTkLabel(
                self.history_scroll,
                text=date_key,
                font=self.fonts["caption"],
                text_color=self.colors["accent"],
                anchor="w"
            )
            date_label.pack(fill="x", pady=(10, 2), padx=5)

            entries = grouped[date_key][-10:]
            for entry in entries:
                role = entry.get("role", "unknown")
                content = entry.get("content", "")
                preview = content[:60] + "..." if len(content) > 60 else content

                role_indicators = {
                    "user": self.colors["accent_alt"],
                    "assistant": self.colors["accent"],
                    "system": self.colors["warning"]
                }
                indicator = role_indicators.get(role, self.colors["muted"])

                btn_frame = ctk.CTkFrame(self.history_scroll, fg_color="transparent")
                btn_frame.pack(fill="x", pady=2, padx=5)

                dot = ctk.CTkLabel(
                    btn_frame,
                    text="●",
                    font=("Segoe UI", 8),
                    text_color=indicator,
                    width=15
                )
                dot.pack(side="left", padx=(0, 5))

                btn = ctk.CTkButton(
                    btn_frame,
                    text=f"[{role.title()}] {preview}",
                    font=self.fonts["body"],
                    fg_color="transparent",
                    hover_color=self.colors["outline"],
                    text_color=self.colors["text_alt"],
                    anchor="w",
                    height=28,
                    corner_radius=4
                )
                btn.pack(side="left", fill="x", expand=True)

    def toggle_sidebar(self):
        if self.sidebar_visible:
            self.sidebar_frame.grid_remove()
            self.sidebar_visible = False
        else:
            self.sidebar_frame.grid()
            self.sidebar_visible = True
            self.load_chat_history()

    def toggle_settings(self):
        if self.settings_visible:
            self.settings_frame.grid_remove()
            self.settings_visible = False
        else:
            self.settings_frame.grid()
            self.settings_visible = True

    def switch_theme(self, theme_name):
        if self._switching_theme:
            return
        self._switching_theme = True

        self.current_theme = theme_name
        if theme_name == "clean":
            self.colors = CLEAN_COLORS.copy()
            self.fonts = CLEAN_FONTS.copy()
            self.window.title("SOL AI Assistant")
        else:
            self.colors = CYBERDECK_COLORS.copy()
            self.fonts = CYBERDECK_FONTS.copy()
            self.window.title("SOL CYBERDECK")

        self.main_frame.destroy()
        self.setup_ui()

        self._switching_theme = False

    def save_settings(self):
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
        except Exception:
            config = {}

        config.setdefault("lm_studio", {})
        config["lm_studio"]["api_url"] = self.settings_api_url.get().strip()
        config["lm_studio"]["model"] = self.settings_model.get().strip()
        config["lm_studio"]["temperature"] = self.settings_temp.get()
        try:
            config["lm_studio"]["max_tokens"] = int(self.settings_max_tokens.get().strip())
        except ValueError:
            pass

        config.setdefault("sol", {})
        config["sol"]["name"] = self.settings_name.get().strip()
        config["sol"]["approval_required"] = self.settings_approval.get()

        config.setdefault("emotion", {})
        config["emotion"]["enabled"] = self.settings_emotion_enabled.get()
        config["emotion"]["curiosity_enabled"] = self.settings_curiosity.get()
        config["emotion"]["mood_decay"] = self.settings_mood_decay.get()

        config.setdefault("memory", {})
        config["memory"]["rag_enabled"] = self.settings_rag.get()
        config["memory"]["summary_enabled"] = self.settings_summary.get()
        config["memory"]["long_term_memory_enabled"] = self.settings_long_term.get()
        try:
            config["memory"]["max_conversation_history"] = int(self.settings_conv_history.get().strip())
        except ValueError:
            pass

        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)

        self.brain.reload_config()

        self.add_message("SYSTEM", "Settings saved successfully.", "system")

    def add_message(self, sender, message, msg_type="user"):
        if threading.current_thread() is not threading.main_thread():
            self.enqueue_ui(self.add_message, sender, message, msg_type)
            return
        
        try:
            self.chat_display.configure(state="normal")
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            if msg_type == "user":
                self.chat_display.insert("end", f"[{timestamp}] YOU: ", "user_name")
                self.chat_display.insert("end", f"{message}\n\n", "user_msg")
            elif msg_type == "assistant":
                self.chat_display.insert("end", f"[{timestamp}] SOL: ", "assistant_name")
                self.chat_display.insert("end", f"{message}\n\n", "assistant_msg")
            elif msg_type == "system":
                self.chat_display.insert("end", f"[{timestamp}] {sender}: ", "system_name")
                self.chat_display.insert("end", f"{message}\n\n", "system_msg")
            
            self.chat_display.configure(state="disabled")
            self.chat_display.see("end")
        except Exception as e:
            print(f"add_message error: {e}")

    def clear_chat(self):
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        self.add_message("SYSTEM", "Chat cleared.", "system")

    def export_chat(self):
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"sol_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.chat_display.get("1.0", "end"))
                self.add_message("SYSTEM", f"Chat exported to: {file_path}", "system")
        except Exception as e:
            self.add_message("SYSTEM", f"Export failed: {str(e)}", "system")

    def send_message(self):
        message = self.input_box.get().strip()
        if not message:
            return
        
        # Check if message contains image-related content
        image_indicators = ["[image", "cannot read", "clipboard", "image input", "does not support", "model does not"]
        if any(indicator in message.lower() for indicator in image_indicators):
            self.input_box.delete(0, "end")
            self.add_message("YOU", "[Image paste attempt]", "user")
            self.add_message("SOL", "Boss, I.can't.see.images. Still. Describe it with words.", "assistant")
            return
        
        self.input_box.delete(0, "end")
        self.add_message("YOU", message, "user")
        self.set_status("THINKING...", self.colors["warning"])
        
        thread = threading.Thread(target=self.process_message, args=(message,))
        thread.daemon = True
        thread.start()
    
    def _handle_paste(self, event):
        """Handle paste events to detect images"""
        try:
            clipboard = self.window.clipboard_get()
            # Check if clipboard content looks like an image reference
            if clipboard and any(x in clipboard.lower() for x in ["[image", "bitmap", "png", "jpg", "\\x00", "cannot read"]):
                self.input_box.delete(0, "end")
                self.add_message("YOU", "[Image paste attempt]", "user")
                self.add_message("SOL", "Boss, really? I'm text-only. Describe what you're trying to show me.", "assistant")
                return "break"
        except tk.TclError:
            # Clipboard contains non-text (image)
            self.input_box.delete(0, "end")
            self.add_message("YOU", "[Image paste attempt]", "user")
            self.add_message("SOL", "*sigh* Still can't see images, boss. Use your words.", "assistant")
            return "break"
        return None

    def process_message(self, message):
        try:
            start_time = time.monotonic()
            result = self.brain.chat(message)
            self.last_response_seconds = time.monotonic() - start_time
            tool_conf = result.get("tool_confidence")
            self.last_tool_confidence = tool_conf if isinstance(tool_conf, (int, float)) else None
            
            self.set_connection_status("ONLINE")
            
            # Check if model returned an image-related error
            response = result['response']
            if any(x in response.lower() for x in ["cannot read", "image input", "does not support", "clipboard"]):
                self.add_message("SOL", "Boss, I literally just said I can't see images. What part was unclear? Describe it with words.", "assistant")
            else:
                self.add_message("SOL", response, "assistant")
            
            if result.get('follow_up'):
                self.add_message("SOL", f"[Follow-up: {result['follow_up']}]", "system")
            
            if result['action']:
                self.pending_action = result['action']
                if result['needs_approval']:
                    self.enqueue_ui(self.handle_action_approval, result['action'])

            self.set_status("READY", self.colors["success"])

        except Exception as e:
            self.add_message("SYSTEM", f"ERROR: {str(e)}", "system")
            self.set_status("ERROR", self.colors["danger"])
            self.set_connection_status("OFFLINE")

    def handle_action_approval(self, action):
        """Prompt user to approve an action and execute if approved"""
        action_desc = action.get('description', str(action))
        
        dialog = ctk.CTkToplevel(self.window)
        dialog.title("Action Approval Required")
        dialog.geometry("400x180")
        dialog.resizable(False, False)
        dialog.transient(self.window)
        dialog.grab_set()
        
        ctk.CTkLabel(
            dialog,
            text=f"Sol wants to perform this action:\n\n{action_desc}",
            wraplength=350,
            font=("Segoe UI", 12)
        ).pack(pady=(20, 10), padx=20)
        
        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(pady=10)
        
        result = {"approved": False}
        
        def on_approve():
            result["approved"] = True
            dialog.destroy()
        
        def on_deny():
            result["approved"] = False
            dialog.destroy()
        
        ctk.CTkButton(
            button_frame, text="Allow", width=100,
            fg_color=self.colors["success"], hover_color=self.colors["success"],
            command=on_approve
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            button_frame, text="Deny", width=100,
            fg_color=self.colors["danger"], hover_color=self.colors["danger"],
            command=on_deny
        ).pack(side="left", padx=10)
        
        self.window.wait_window(dialog)
        
        if result["approved"]:
            self.add_message("SYSTEM", f"ACTION APPROVED: {action_desc}", "system")
            thread = threading.Thread(target=self.execute_pending_action)
            thread.daemon = True
            thread.start()
        else:
            self.add_message("SYSTEM", f"ACTION DENIED: {action_desc}", "system")
            self.pending_action = None

    def execute_pending_action(self):
        """Execute the currently pending action"""
        if not self.pending_action:
            return
        
        try:
            self.add_message("SYSTEM", "Executing action...", "system")
            result = self.brain.execute_action(self.pending_action)
            
            if result.get('success'):
                self.add_message("SYSTEM", f"Action succeeded: {result.get('message', 'Done')}", "system")
            else:
                self.add_message("SYSTEM", f"Action failed: {result.get('error', 'Unknown error')}", "system")
        except Exception as e:
            self.add_message("SYSTEM", f"Execution error: {str(e)}", "system")
        finally:
            self.pending_action = None

    def set_status(self, text, color):
        if threading.current_thread() is not threading.main_thread():
            self.enqueue_ui(self.set_status, text, color)
            return
        self.status_label.configure(text=text, text_color=color)

    def set_connection_status(self, status):
        if threading.current_thread() is not threading.main_thread():
            self.enqueue_ui(self.set_connection_status, status)
            return
        self.connection_status = status
        color = self.colors["success"] if status == "ONLINE" else self.colors["danger"]
        symbol = "LM:"
        self.connection_label.configure(text=f"{symbol} {status.upper()}", text_color=color)

    def update_time(self):
        now = datetime.now().strftime("%H:%M:%S")
        self.time_label.configure(text=now)
        self.window.after(1000, self.update_time)

    def update_system_monitor(self):
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent
            self.sysmon_label.configure(text=f"CPU: {cpu:.0f}% | RAM: {ram:.0f}% | Disk: {disk:.0f}%")
        except Exception:
            pass
        self.window.after(5000, self.update_system_monitor)

    def _monitoring_loop(self):
        """Background thread for proactive system monitoring"""
        while True:
            try:
                if not self.monitoring_config.get("enabled", True):
                    time.sleep(30)
                    continue
                
                # Check quiet hours
                if self._is_quiet_hours():
                    time.sleep(60)
                    continue
                
                # Get system metrics
                cpu = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory().percent
                disk = psutil.disk_usage('/').percent
                
                # Check thresholds and alert
                self._check_and_alert("cpu", cpu, self.monitoring_config.get("cpu_percent", 85))
                self._check_and_alert("memory", memory, self.monitoring_config.get("memory_percent", 85))
                self._check_and_alert("disk", disk, self.monitoring_config.get("disk_percent", 90))
                
                # Sleep for configured interval
                interval = self.monitoring_config.get("interval_sec", 30)
                time.sleep(interval)
            except Exception:
                time.sleep(30)

    def _is_quiet_hours(self):
        """Check if current time is within quiet hours"""
        try:
            quiet = self.monitoring_config.get("quiet_hours", {})
            start_str = quiet.get("start", "23:00")
            end_str = quiet.get("end", "07:00")
            
            now = datetime.now().time()
            start_time = datetime.strptime(start_str, "%H:%M").time()
            end_time = datetime.strptime(end_str, "%H:%M").time()
            
            if start_time <= end_time:
                return start_time <= now <= end_time
            else:  # Crosses midnight
                return now >= start_time or now <= end_time
        except Exception:
            return False

    def _check_and_alert(self, metric, value, threshold):
        """Check if metric exceeds threshold and send chat alert"""
        if value <= threshold:
            return
        
        # Check cooldown
        now = time.time()
        cooldown = self.proactive_config.get("cooldown_sec", 600)
        last_alert = self.last_alert_time.get(metric, 0)
        
        if now - last_alert < cooldown:
            return
        
        # Generate alert message
        alert_messages = {
            "cpu": f"Hey boss, your CPU is at {value:.0f}% - might want to close some apps.",
            "memory": f"Boss, memory usage is at {value:.0f}%. System's getting heavy.",
            "disk": f"Heads up - disk space is at {value:.0f}%. Time for some cleanup."
        }
        
        message = alert_messages.get(metric, f"{metric} is at {value:.0f}%")
        
        # Post to chat via UI queue
        self.enqueue_ui(self.add_message, "SOL", message, "system")
        self.last_alert_time[metric] = now

    def animate_glow(self):
        self.glow_phase += 0.15
        self.window.after(100, self.animate_glow)

    def process_ui_queue(self):
        try:
            # Process all pending items without blocking
            while True:
                try:
                    func, args, kwargs = self.ui_queue.get_nowait()
                    try:
                        func(*args, **kwargs)
                    except Exception as e:
                        print(f"UI Queue Error in {func.__name__}: {e}")
                except queue.Empty:
                    break
        except Exception as e:
            print(f"UI Queue Fatal Error: {e}")
        finally:
            # Always reschedule, even on error
            self.window.after(100, self.process_ui_queue)

    def enqueue_ui(self, func, *args, **kwargs):
        self.ui_queue.put((func, args, kwargs))

    def start_monitoring(self):
        self.update_time()
        self.update_system_monitor()
        self.check_connection_status()
        self.monitoring_config = self.brain.config.get("monitoring", {})
        self.proactive_config = self.brain.config.get("proactive_suggestions", {})
        self.last_alert_time = {}
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        if self.monitoring_config.get("enabled", True):
            self.monitoring_thread.start()

    def check_connection_status(self):
        thread = threading.Thread(target=self._check_connection)
        thread.daemon = True
        thread.start()

    def _check_connection(self):
        try:
            import requests
            response = requests.get("http://localhost:1234/v1/models", timeout=2)
            if response.status_code == 200:
                self.set_connection_status("ONLINE")
            else:
                self.set_connection_status("OFFLINE")
        except Exception:
            self.set_connection_status("OFFLINE")

        self.window.after(5000, self.check_connection_status)

    def run(self):
        self.window.mainloop()


def main():
    gui = SolGUI()
    gui.run()


if __name__ == "__main__":
    main()
