"""
Sol GUI - Cyberdeck Edition
Cyberpunk aesthetic with practical, clean layout
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

# Cyberpunk neon color scheme
COLORS = {
    "bg": "#0a0e27",
    "panel": "#0f1419",
    "panel_alt": "#151b2f",
    "outline": "#1a2847",
    "outline_bright": "#2a4a7f",
    "text": "#00ff88",
    "text_alt": "#e0e6ff",
    "muted": "#4a6fa0",
    "accent": "#00ff88",
    "accent_alt": "#ff006e",
    "accent_hover": "#00cc6a",
    "warning": "#ffff00",
    "danger": "#ff0044",
    "info": "#00ccff",
    "success": "#00ff88",
}

# Cyberpunk fonts
FONTS = {
    "title": ("Courier New", 24, "bold"),
    "subtitle": ("Courier New", 14),
    "section": ("Courier New", 16, "bold"),
    "body": ("Courier New", 14),
    "body_bold": ("Courier New", 14, "bold"),
    "body_italic": ("Courier New", 14, "italic"),
    "caption": ("Courier New", 12),
    "code": ("Consolas", 13)
}


class SolGUI:
    def __init__(self):
        # Initialize Sol brain
        self.brain = SolBrain()
        self.pending_action = None
        self.pending_actions = []
        self.last_suggestion_time = 0
        self.last_assistant_message = ""
        self.connection_status = "UNKNOWN"
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.scanline_y = 0
        self.scanline_speed = 1
        self.glow_phase = 0.0
        self.last_response_seconds = None
        self.last_tool_confidence = None
        self.last_gpu_refresh = 0.0
        self.gpu_name = "N/A"
        self.gpu_vram_gb = None
        self.flicker_targets = {}
        self.current_status_color = COLORS["success"]
        self.current_connection_color = COLORS["warning"]

        agent_config = self.brain.config.get("agent", {})
        monitoring_config = self.brain.config.get("monitoring", {})
        suggestions_config = self.brain.config.get("proactive_suggestions", {})

        self.task_enabled = bool(agent_config.get("enabled", True))
        self.monitoring_enabled = bool(monitoring_config.get("enabled", False))
        self.suggestions_enabled = bool(suggestions_config.get("enabled", False))
        self.auto_queue_enabled = bool(suggestions_config.get("auto_queue_actions", False))
        
        # Setup window
        self.window = ctk.CTk()
        self.window.title("⚡ Sol CYBERDECK ⚡")
        self.window.geometry("1400x850")
        self.window.minsize(1400, 850)
        self.window.configure(fg_color=COLORS["bg"])

        self.ui_queue = queue.Queue()
        self.window.after(100, self.process_ui_queue)
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.glow_phase = 0.0
        
        self.setup_ui()
        self.start_monitoring()
        self.animate_glow()
        
    def setup_ui(self):
        """Setup the user interface"""

        # Cyberdeck background
        self.background = tk.Canvas(
            self.window,
            highlightthickness=0,
            bg=COLORS["bg"]
        )
        self.background.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Main container (glass panel)
        main_frame = ctk.CTkFrame(
            self.window,
            fg_color="transparent",
            corner_radius=0
        )
        main_frame.pack(fill="both", expand=True)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        # Sidebar
        sidebar = ctk.CTkFrame(
            main_frame,
            width=230,
            fg_color=COLORS["panel_alt"],
            corner_radius=18,
            border_width=1,
            border_color=COLORS["outline_bright"]
        )
        sidebar.grid(row=0, column=0, sticky="nsw", padx=(12, 6), pady=12)

        brand = ctk.CTkLabel(
            sidebar,
            text="SOL",
            font=FONTS["title"],
            text_color=COLORS["accent"]
        )
        brand.pack(padx=16, pady=(18, 4), anchor="w")

        tagline = ctk.CTkLabel(
            sidebar,
            text="Offline neural assistant",
            font=FONTS["subtitle"],
            text_color=COLORS["muted"]
        )
        tagline.pack(padx=16, pady=(0, 12), anchor="w")

        status_frame = ctk.CTkFrame(
            sidebar,
            fg_color=COLORS["panel"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["outline"]
        )
        status_frame.pack(fill="x", padx=14, pady=(0, 12))
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="READY",
            font=FONTS["body_bold"],
            text_color=COLORS["success"]
        )
        self.status_label.pack(padx=12, pady=(10, 2), anchor="w")
        self.connection_label = ctk.CTkLabel(
            status_frame,
            text="LM: UNKNOWN",
            font=FONTS["caption"],
            text_color=COLORS["muted"]
        )
        self.connection_label.pack(padx=12, pady=(0, 10), anchor="w")

        quick_label = ctk.CTkLabel(
            sidebar,
            text="Quick Actions",
            font=FONTS["section"],
            text_color=COLORS["muted"]
        )
        quick_label.pack(padx=16, pady=(4, 6), anchor="w")

        def quick_button(title, message, alt=False):
            return ctk.CTkButton(
                sidebar,
                text=title,
                command=lambda: self.send_quick_message(message),
                fg_color=COLORS["accent_alt"] if alt else COLORS["accent"],
                hover_color=COLORS["accent_alt_hover"] if alt else COLORS["accent_hover"],
                text_color=COLORS["bg"],
                height=34
            )

        quick_button("List Desktop", "List my Desktop files").pack(padx=14, pady=4, fill="x")
        quick_button("Open Downloads", "Open Downloads folder", alt=True).pack(padx=14, pady=4, fill="x")
        quick_button("Open Documents", "Open Documents folder").pack(padx=14, pady=4, fill="x")
        quick_button("System Status", "What's my PC status?", alt=True).pack(padx=14, pady=4, fill="x")

        pulse_frame = ctk.CTkFrame(
            sidebar,
            fg_color=COLORS["panel"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["outline"]
        )
        pulse_frame.pack(fill="x", padx=14, pady=(12, 10))
        pulse_label = ctk.CTkLabel(
            pulse_frame,
            text="System Pulse",
            font=FONTS["section"],
            text_color=COLORS["accent"]
        )
        pulse_label.pack(padx=12, pady=(10, 6), anchor="w")

        def metric_row(parent, title, color):
            row = ctk.CTkFrame(parent, fg_color=COLORS["panel_alt"], corner_radius=0)
            row.pack(fill="x", padx=12, pady=(0, 8))
            label = ctk.CTkLabel(
                row,
                text=f"{title}: 0%",
                font=FONTS["caption"],
                text_color=COLORS["text"]
            )
            label.pack(anchor="w")
            bar = ctk.CTkProgressBar(
                row,
                height=8,
                fg_color=COLORS["panel"],
                progress_color=color
            )
            bar.pack(fill="x", pady=(4, 0))
            bar.set(0)
            return label, bar

        self.cpu_label, self.cpu_bar = metric_row(pulse_frame, "CPU", COLORS["accent"])
        self.mem_label, self.mem_bar = metric_row(pulse_frame, "Memory", COLORS["accent_alt"])
        self.disk_label, self.disk_bar = metric_row(pulse_frame, "Disk", COLORS["info"])

        telemetry_frame = ctk.CTkFrame(
            sidebar,
            fg_color=COLORS["panel"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["outline"]
        )
        telemetry_frame.pack(fill="x", padx=14, pady=(0, 10))
        telemetry_label = ctk.CTkLabel(
            telemetry_frame,
            text="Neural Telemetry",
            font=FONTS["section"],
            text_color=COLORS["accent"]
        )
        telemetry_label.pack(padx=12, pady=(10, 6), anchor="w")

        def telemetry_row(parent, title, value):
            row = ctk.CTkFrame(parent, fg_color=COLORS["panel_alt"], corner_radius=0)
            row.pack(fill="x", padx=12, pady=(0, 8))
            label = ctk.CTkLabel(
                row,
                text=f"{title}: {value}",
                font=FONTS["caption"],
                text_color=COLORS["text"]
            )
            label.pack(anchor="w")
            return label

        self.telemetry_labels = {
            "uplink": telemetry_row(telemetry_frame, "Uplink", "UNKNOWN"),
            "latency": telemetry_row(telemetry_frame, "Latency", "--"),
            "confidence": telemetry_row(telemetry_frame, "Tool Conf", "--"),
            "context": telemetry_row(telemetry_frame, "Context", "--"),
            "gpu": telemetry_row(telemetry_frame, "GPU", "N/A"),
            "vram": telemetry_row(telemetry_frame, "VRAM", "--")
        }

        deck_frame = ctk.CTkFrame(
            sidebar,
            fg_color=COLORS["panel"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["outline"]
        )
        deck_frame.pack(fill="x", padx=14, pady=(0, 10))
        deck_label = ctk.CTkLabel(
            deck_frame,
            text="Control Deck",
            font=FONTS["section"],
            text_color=COLORS["accent"]
        )
        deck_label.pack(padx=12, pady=(10, 4), anchor="w")

        self.task_var = tk.BooleanVar(value=self.task_enabled)
        self.monitor_var = tk.BooleanVar(value=self.monitoring_enabled)
        self.suggest_var = tk.BooleanVar(value=self.suggestions_enabled)
        self.auto_queue_var = tk.BooleanVar(value=self.auto_queue_enabled)

        switch_style = {
            "fg_color": COLORS["outline"],
            "progress_color": COLORS["accent"],
            "button_color": COLORS["panel_glow"],
            "button_hover_color": COLORS["accent_hover"],
            "text_color": COLORS["text"]
        }

        ctk.CTkSwitch(
            deck_frame,
            text="Task Mode",
            variable=self.task_var,
            command=self.toggle_task_mode,
            **switch_style
        ).pack(padx=12, pady=4, anchor="w")
        ctk.CTkSwitch(
            deck_frame,
            text="Monitoring",
            variable=self.monitor_var,
            command=self.toggle_monitoring,
            **switch_style
        ).pack(padx=12, pady=4, anchor="w")
        ctk.CTkSwitch(
            deck_frame,
            text="Suggestions",
            variable=self.suggest_var,
            command=self.toggle_suggestions,
            **switch_style
        ).pack(padx=12, pady=4, anchor="w")
        ctk.CTkSwitch(
            deck_frame,
            text="Auto-Queue",
            variable=self.auto_queue_var,
            command=self.toggle_auto_queue,
            **switch_style
        ).pack(padx=12, pady=(4, 10), anchor="w")

        queue_frame = ctk.CTkFrame(
            sidebar,
            fg_color=COLORS["panel"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["outline"]
        )
        queue_frame.pack(fill="x", padx=14, pady=(0, 10))
        queue_label = ctk.CTkLabel(
            queue_frame,
            text="Action Queue",
            font=FONTS["section"],
            text_color=COLORS["accent"]
        )
        queue_label.pack(padx=12, pady=(10, 4), anchor="w")
        self.queue_status = ctk.CTkLabel(
            queue_frame,
            text="No pending actions.",
            font=FONTS["caption"],
            text_color=COLORS["muted"],
            justify="left"
        )
        self.queue_status.pack(padx=12, pady=(0, 10), anchor="w")

        spacer = ctk.CTkFrame(sidebar, fg_color=COLORS["panel"], corner_radius=0)
        spacer.pack(fill="both", expand=True)

        settings_btn = ctk.CTkButton(
            sidebar,
            text="Settings",
            command=self.show_settings,
            fg_color=COLORS["panel_alt"],
            hover_color=COLORS["outline"],
            text_color=COLORS["text"],
            height=38
        )
        settings_btn.pack(padx=14, pady=(0, 16), fill="x")

        # Content
        content_frame = ctk.CTkFrame(main_frame, fg_color="transparent", corner_radius=0)
        content_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(2, weight=1)

        # Compact cyberdeck header (3-row layout)
        header_frame = ctk.CTkFrame(
            content_frame,
            fg_color=COLORS["panel_alt"],
            corner_radius=0,
            border_width=0
        )
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=0)

        # Row 1: Title + Clock
        title_frame = ctk.CTkFrame(header_frame, fg_color=COLORS["panel_alt"], corner_radius=0)
        title_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=0, pady=0)
        title_frame.grid_columnconfigure(0, weight=1)
        title_frame.grid_columnconfigure(1, weight=0)

        header_title = ctk.CTkLabel(
            title_frame,
            text="CYBERDECK A9-X // SOL CORE",
            font=FONTS["title"],
            text_color=COLORS["accent"]
        )
        header_title.grid(row=0, column=0, sticky="w", padx=18, pady=(8, 0))

        clock_frame = ctk.CTkFrame(title_frame, fg_color=COLORS["panel_alt"], corner_radius=0)
        clock_frame.grid(row=0, column=1, sticky="e", padx=18, pady=(8, 0))

        self.clock_label = ctk.CTkLabel(
            clock_frame,
            text="00:00:00",
            font=FONTS["body_bold"],
            text_color=COLORS["accent"]
        )
        self.clock_label.pack(anchor="e")

        self.date_label = ctk.CTkLabel(
            clock_frame,
            text="MON 00 JAN",
            font=FONTS["caption"],
            text_color=COLORS["muted"]
        )
        self.date_label.pack(anchor="e")

        # Row 2: Sync bar
        sync_row = ctk.CTkFrame(header_frame, fg_color=COLORS["panel_alt"], corner_radius=0)
        sync_row.grid(row=1, column=0, columnspan=2, sticky="ew", padx=18, pady=(4, 0))
        sync_row.grid_columnconfigure(1, weight=1)

        self.sync_label = ctk.CTkLabel(
            sync_row,
            text="SYNCING",
            font=FONTS["caption"],
            text_color=COLORS["muted"]
        )
        self.sync_label.pack(side="left", padx=(0, 8))

        self.sync_bar = ctk.CTkProgressBar(
            sync_row,
            progress_color=COLORS["accent"],
            fg_color=COLORS["panel"],
            height=4,
            corner_radius=2
        )
        self.sync_bar.pack(side="left", fill="x", expand=True)
        self.sync_bar.set(0.35)

        # Row 3: 6-column HUD dock
        hud_frame = ctk.CTkFrame(header_frame, fg_color=COLORS["panel_alt"], corner_radius=0)
        hud_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=18, pady=(6, 10))
        for idx in range(6):
            hud_frame.grid_columnconfigure(idx, weight=1)

        def hud_chip(parent, title, value, color, column):
            chip = ctk.CTkFrame(
                parent,
                fg_color=COLORS["panel"],
                corner_radius=8,
                border_width=1,
                border_color=COLORS["outline"]
            )
            chip.grid(row=0, column=column, padx=3, pady=4, sticky="ew")
            label = ctk.CTkLabel(
                chip,
                text=f"{title}: {value}",
                font=FONTS["caption"],
                text_color=color
            )
            label.pack(padx=6, pady=4, anchor="center")
            return label

        self.hud_labels = {}
        self.hud_labels["model"] = hud_chip(
            hud_frame,
            "MODEL",
            self.brain.config.get("lm_studio", {}).get("model", "local"),
            COLORS["accent"],
            0
        )
        self.hud_labels["mood"] = hud_chip(hud_frame, "MOOD", "CALM", COLORS["accent_alt"], 1)
        self.hud_labels["memory"] = hud_chip(hud_frame, "MEM", "0", COLORS["info"], 2)
        self.hud_labels["task"] = hud_chip(
            hud_frame,
            "TASK",
            "ON" if self.task_enabled else "OFF",
            COLORS["success"] if self.task_enabled else COLORS["danger"],
            3
        )
        self.hud_labels["lm"] = hud_chip(hud_frame, "LM", self.connection_status, COLORS["warning"], 4)
        self.hud_labels["temp"] = hud_chip(hud_frame, "TEMP", "0.7", COLORS["accent"], 5)

        accent_bar = ctk.CTkFrame(header_frame, fg_color=COLORS["accent"], corner_radius=0, height=2)
        accent_bar.grid(row=3, column=0, columnspan=2, sticky="ew", padx=0, pady=(0, 0))
        self.accent_bar = accent_bar

        # Action approval frame (hidden by default)
        self.approval_frame = ctk.CTkFrame(
            content_frame,
            fg_color=COLORS["panel"],
            corner_radius=16,
            border_width=1,
            border_color=COLORS["outline_bright"]
        )
        self.approval_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.approval_frame.grid_remove()

        approval_title = ctk.CTkLabel(
            self.approval_frame,
            text="ACTION GATE",
            font=FONTS["section"],
            text_color=COLORS["accent"]
        )
        approval_title.pack(pady=(10, 0))

        self.approval_label = ctk.CTkLabel(
            self.approval_frame,
            text="",
            font=FONTS["body_bold"],
            text_color=COLORS["text"]
        )
        self.approval_label.pack(pady=(6, 6))

        approval_buttons = ctk.CTkFrame(self.approval_frame, fg_color=COLORS["panel_alt"], corner_radius=12)
        approval_buttons.pack(pady=(0, 10))

        self.approve_btn = ctk.CTkButton(
            approval_buttons,
            text="Approve",
            command=self.approve_action,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color=COLORS["bg"],
            width=140
        )
        self.approve_btn.pack(side="left", padx=6)

        self.deny_btn = ctk.CTkButton(
            approval_buttons,
            text="Deny",
            command=self.deny_action,
            fg_color=COLORS["danger"],
            hover_color="#e14f63",
            text_color=COLORS["bg"],
            width=140
        )
        self.deny_btn.pack(side="left", padx=6)

        # Chat display area
        chat_frame = ctk.CTkFrame(
            content_frame,
            fg_color=COLORS["panel_alt"],
            corner_radius=18,
            border_width=1,
            border_color=COLORS["outline_bright"]
        )
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
            border_width=1,
            border_color=COLORS["outline"],
            scrollbar_button_color=COLORS["outline"],
            scrollbar_button_hover_color=COLORS["accent_hover"]
        )
        self.chat_display.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.configure_chat_tags()

        # Input area
        input_frame = ctk.CTkFrame(
            content_frame,
            fg_color=COLORS["panel_alt"],
            corner_radius=18,
            border_width=1,
            border_color=COLORS["outline_bright"]
        )
        input_frame.grid(row=3, column=0, sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)

        self.input_box = ctk.CTkEntry(
            input_frame,
            placeholder_text="Type your message to Sol...",
            font=FONTS["body"],
            height=42,
            fg_color=COLORS["panel_alt"],
            text_color=COLORS["text"],
            placeholder_text_color=COLORS["muted"],
            border_color=COLORS["accent"],
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

        utility_frame = ctk.CTkFrame(input_frame, fg_color=COLORS["panel"], corner_radius=0)
        utility_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 10))
        utility_frame.grid_columnconfigure(0, weight=1)

        self.copy_btn = ctk.CTkButton(
            utility_frame,
            text="Copy Last",
            command=self.copy_last_response,
            height=28,
            fg_color=COLORS["panel_alt"],
            hover_color=COLORS["outline"],
            text_color=COLORS["text"]
        )
        self.copy_btn.grid(row=0, column=0, padx=(0, 8), sticky="w")

        self.export_btn = ctk.CTkButton(
            utility_frame,
            text="Export Chat",
            command=self.export_chat_history,
            height=28,
            fg_color=COLORS["panel_alt"],
            hover_color=COLORS["outline"],
            text_color=COLORS["text"]
        )
        self.export_btn.grid(row=0, column=1, padx=(0, 8), sticky="w")
        
        self.update_queue_status()
        self.set_connection_status(self.connection_status)
        self.refresh_gpu_info()
        self.refresh_hud()
        self.update_system_pulse()
        self.animate_cyberdeck()
        self.animate_flicker()
        self.show_hud_dock()

        # Add welcome message
        self.add_message("Sol", "Hello! I'm Sol, your AI assistant. I'm here to help you with tasks on your PC. What can I do for you today?", "assistant")
    
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
            prefix = f"\n[{timestamp}] Sol: "
            self.chat_display.insert("end", prefix, "assistant_name")
            self.insert_markdown(message, "assistant_msg")
            self.chat_display.insert("end", "\n")
            self.last_assistant_message = message
        elif msg_type == "system":
            self.chat_display.insert("end", f"\n[{timestamp}] SYSTEM: ", "system_name")
            self.insert_markdown(message, "system_msg")
            self.chat_display.insert("end", "\n")
        elif msg_type == "action":
            self.chat_display.insert("end", f"\n[{timestamp}] ⚡ ACTION: ", "action_name")
            self.insert_markdown(message, "action_msg")
            self.chat_display.insert("end", "\n")

        if hasattr(self, "hud_dock_status"):
            try:
                self.hud_dock_status.configure(text=self.status_label.cget("text"), text_color=self.current_status_color)
            except Exception:
                pass
        
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    def configure_chat_tags(self):
        text_widget = getattr(self.chat_display, "_textbox", self.chat_display)

        for name, color in [
            ("user_name", COLORS["accent_alt"]),
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
        self.current_status_color = color
        self.status_label.configure(text=text, text_color=color)
        self.refresh_flicker_targets()

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

    def draw_cyberdeck_background(self):
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        if width <= 1 or height <= 1:
            return

        self.background.delete("all")

        # Base gradient blocks
        self.background.create_rectangle(0, 0, width, height, fill=COLORS["bg"], outline="")

        # Grid pattern
        grid_size = 40
        for x in range(0, width, grid_size):
            self.background.create_line(x, 0, x, height, fill=COLORS["grid"])
        for y in range(0, height, grid_size):
            self.background.create_line(0, y, width, y, fill=COLORS["grid"])

        # Glass panel silhouettes
        left_x1, left_y1 = 8, 70
        left_x2, left_y2 = 252, height - 18
        right_x1, right_y1 = 264, 70
        right_x2, right_y2 = width - 18, height - 18
        self.background.create_rectangle(
            left_x1,
            left_y1,
            left_x2,
            left_y2,
            fill=COLORS["panel"],
            outline=COLORS["outline_bright"]
        )
        self.background.create_rectangle(
            right_x1,
            right_y1,
            right_x2,
            right_y2,
            fill=COLORS["panel_alt"],
            outline=COLORS["outline"]
        )
        self.background.create_line(left_x1, left_y1, left_x1 + 120, left_y1, fill=COLORS["accent"])
        self.background.create_line(right_x1, right_y1, right_x1 + 160, right_y1, fill=COLORS["accent_alt"])

        # Neon header strip
        self.background.create_rectangle(0, 0, width, 48, fill=COLORS["scanline_glow"], outline="")
        self.background.create_rectangle(0, 48, width, 50, fill=COLORS["accent"], outline="")

        # Scanline
        self.background.create_rectangle(
            0,
            self.scanline_y,
            width,
            self.scanline_y + 12,
            fill=COLORS["scanline"],
            outline=""
        )

    def animate_cyberdeck(self):
        height = max(1, self.window.winfo_height())
        self.scanline_y = (self.scanline_y + self.scanline_speed) % (height + 20)
        self.glow_phase += 0.08

        glow = 0.5 + 0.5 * math.sin(self.glow_phase)
        accent = COLORS["accent"]
        alt = COLORS["accent_alt"]

        # Update clock every frame
        try:
            now = datetime.now()
            self.clock_label.configure(text=now.strftime("%H:%M:%S"))
            self.date_label.configure(text=now.strftime("%a %d %b").upper())
        except Exception:
            pass

        if self.current_status_color == COLORS["success"]:
            glow_color = accent if glow > 0.5 else alt
            try:
                self.status_label.configure(text_color=glow_color)
            except Exception:
                pass

        try:
            if glow > 0.5:
                self.accent_bar.configure(fg_color=COLORS["accent"])
            else:
                self.accent_bar.configure(fg_color=COLORS["accent_alt"])
        except Exception:
            pass

        self.draw_cyberdeck_background()
        self.window.after(50, self.animate_cyberdeck)

    def create_hud_dock(self):
        if self.hud_dock and self.hud_dock.winfo_exists():
            return

        dock = ctk.CTkToplevel(self.window)
        dock.title("SOL HUD")
        dock.geometry("280x240+18+80")
        dock.configure(fg_color=COLORS["panel"])
        dock.attributes("-topmost", True)
        dock.protocol("WM_DELETE_WINDOW", self.hide_hud_dock)
        self.hud_dock = dock

        header = ctk.CTkFrame(dock, fg_color=COLORS["panel_alt"], corner_radius=12)
        header.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(
            header,
            text="CYBER HUD",
            font=FONTS["section"],
            text_color=COLORS["accent"]
        ).pack(padx=10, pady=(8, 0), anchor="w")
        self.hud_dock_status = ctk.CTkLabel(
            header,
            text="READY",
            font=FONTS["caption"],
            text_color=COLORS["success"]
        )
        self.hud_dock_status.pack(padx=10, pady=(0, 8), anchor="w")

        dock_body = ctk.CTkFrame(dock, fg_color=COLORS["panel_alt"], corner_radius=12)
        dock_body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        def dock_row(title, value):
            row = ctk.CTkFrame(dock_body, fg_color=COLORS["panel"], corner_radius=8)
            row.pack(fill="x", padx=10, pady=(8, 0))
            label = ctk.CTkLabel(
                row,
                text=f"{title}: {value}",
                font=FONTS["caption"],
                text_color=COLORS["text"]
            )
            label.pack(padx=8, pady=6, anchor="w")
            return label

        self.hud_dock_labels = {
            "model": dock_row("Model", "local"),
            "task": dock_row("Task", "OFF"),
            "queue": dock_row("Queue", "0"),
            "latency": dock_row("Latency", "--"),
            "gpu": dock_row("GPU", "N/A")
        }

        self.refresh_flicker_targets()

    def show_hud_dock(self):
        if not hasattr(self, "hud_dock"):
            self.hud_dock = None
        self.create_hud_dock()
        try:
            self.hud_dock.deiconify()
        except Exception:
            pass

    def hide_hud_dock(self):
        if self.hud_dock and self.hud_dock.winfo_exists():
            self.hud_dock.withdraw()

    def toggle_hud_dock(self):
        if self.hud_dock and self.hud_dock.winfo_exists() and self.hud_dock.winfo_viewable():
            self.hide_hud_dock()
        else:
            self.show_hud_dock()

    def save_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as handle:
                json.dump(self.brain.config, handle, ensure_ascii=True, indent=2)
        except Exception as e:
            self.add_message("System", f"Config save failed: {str(e)}", "system")

    def refresh_flicker_targets(self):
        targets = {}
        if hasattr(self, "status_label"):
            targets[self.status_label] = self.current_status_color
        if hasattr(self, "connection_label"):
            targets[self.connection_label] = self.current_connection_color

        if hasattr(self, "hud_labels"):
            for key, label in self.hud_labels.items():
                base = COLORS["text"]
                if key == "model":
                    base = COLORS["accent"]
                elif key == "mood":
                    base = COLORS["accent_alt"]
                elif key == "memory":
                    base = COLORS["info"]
                elif key == "task":
                    base = COLORS["success"] if self.task_enabled else COLORS["danger"]
                elif key == "lm":
                    base = self.current_connection_color
                elif key == "temp":
                    base = COLORS["accent"]
                elif key == "tokens":
                    base = COLORS["info"]
                elif key == "endpoint":
                    base = COLORS["accent_alt"]
                targets[label] = base

        if hasattr(self, "telemetry_labels"):
            for label in self.telemetry_labels.values():
                targets[label] = COLORS["text"]

        if hasattr(self, "hud_dock_labels"):
            for label in self.hud_dock_labels.values():
                targets[label] = COLORS["text"]
        if hasattr(self, "hud_dock_status"):
            targets[self.hud_dock_status] = self.current_status_color

        self.flicker_targets = targets

    def animate_flicker(self):
        if not self.flicker_targets:
            self.refresh_flicker_targets()

        for label, color in self.flicker_targets.items():
            try:
                label.configure(text_color=color)
            except Exception:
                continue

        if random.random() < 0.22:
            count = min(len(self.flicker_targets), random.randint(1, 4))
            for label in random.sample(list(self.flicker_targets.keys()), count):
                try:
                    label.configure(text_color=COLORS["muted"])
                except Exception:
                    pass

        self.window.after(120, self.animate_flicker)

    def update_hud_fields(self):
        if threading.current_thread() is not threading.main_thread():
            self.enqueue_ui(self.update_hud_fields)
            return

        mood = self.brain.get_mood_state() or {}
        mood_label = str(mood.get("label", "calm")).upper()

        memory_items = self.brain.memory.get_user_memory(limit=None)
        memory_count = len(memory_items) if memory_items else 0

        model_name = self.brain.config.get("lm_studio", {}).get("model", "local")
        lm_config = self.brain.config.get("lm_studio", {})
        temperature = lm_config.get("temperature", 0.7)
        max_tokens = lm_config.get("max_tokens", 0)
        endpoint = lm_config.get("api_url", "")
        if isinstance(endpoint, str) and endpoint:
            endpoint = endpoint.replace("http://", "").replace("https://", "")
            endpoint = endpoint.split("/")[0]
        else:
            endpoint = "local"
        task_state = "ON" if self.task_enabled else "OFF"
        task_color = COLORS["success"] if self.task_enabled else COLORS["danger"]

        lm_status = self.connection_status.upper()
        if lm_status == "ONLINE":
            lm_color = COLORS["success"]
        elif lm_status == "OFFLINE":
            lm_color = COLORS["danger"]
        else:
            lm_color = COLORS["warning"]

        self.hud_labels["model"].configure(text=f"MODEL: {model_name}")
        self.hud_labels["mood"].configure(text=f"MOOD: {mood_label}")
        self.hud_labels["memory"].configure(text=f"MEM: {memory_count}")
        self.hud_labels["task"].configure(text=f"TASK: {task_state}", text_color=task_color)
        self.hud_labels["lm"].configure(text=f"LM: {lm_status}", text_color=lm_color)
        self.hud_labels["temp"].configure(text=f"TEMP: {temperature}")

        latency = "--"
        if isinstance(self.last_response_seconds, (int, float)):
            latency = f"{self.last_response_seconds:.2f}s"

        confidence = "--"
        if isinstance(self.last_tool_confidence, (int, float)):
            confidence = f"{self.last_tool_confidence * 100:.0f}%"

        context_count = self.brain.memory.get_conversation_count()
        rag_enabled = self.brain.config.get("memory", {}).get("rag_enabled", True)
        rag_label = "ON" if rag_enabled else "OFF"
        vram_label = "--"
        if isinstance(self.gpu_vram_gb, (int, float)):
            vram_label = f"{self.gpu_vram_gb} GB"

        if hasattr(self, "telemetry_labels"):
            self.telemetry_labels["uplink"].configure(text=f"Uplink: {lm_status}")
            self.telemetry_labels["latency"].configure(text=f"Latency: {latency}")
            self.telemetry_labels["confidence"].configure(text=f"Tool Conf: {confidence}")
            self.telemetry_labels["context"].configure(text=f"Context: {context_count} | RAG {rag_label}")
            self.telemetry_labels["gpu"].configure(text=f"GPU: {self.gpu_name}")
            self.telemetry_labels["vram"].configure(text=f"VRAM: {vram_label}")

        if hasattr(self, "hud_dock_labels"):
            queue_total = (1 if self.pending_action else 0) + len(self.pending_actions)
            self.hud_dock_labels["model"].configure(text=f"Model: {model_name}")
            self.hud_dock_labels["task"].configure(text=f"Task: {task_state}")
            self.hud_dock_labels["queue"].configure(text=f"Queue: {queue_total}")
            self.hud_dock_labels["latency"].configure(text=f"Latency: {latency}")
            self.hud_dock_labels["gpu"].configure(text=f"GPU: {self.gpu_name}")

        if hasattr(self, "hud_dock_status"):
            self.hud_dock_status.configure(text=self.status_label.cget("text"), text_color=self.current_status_color)

        self.refresh_flicker_targets()

    def refresh_hud(self):
        self.update_hud_fields()
        self.window.after(2000, self.refresh_hud)

    def update_queue_status(self):
        if threading.current_thread() is not threading.main_thread():
            self.enqueue_ui(self.update_queue_status)
            return

        queue_items = []
        if self.pending_action:
            queue_items.append(self.pending_action.get("description", "Pending action"))
        queue_items.extend([
            item.get("description", "Pending action")
            for item in self.pending_actions[:2]
        ])

        total = (1 if self.pending_action else 0) + len(self.pending_actions)
        if total == 0:
            text = "No pending actions."
            color = COLORS["muted"]
        else:
            lines = [f"{total} pending action(s):"]
            for item in queue_items:
                lines.append(f"- {item}")
            text = "\n".join(lines)
            color = COLORS["text"]

        self.queue_status.configure(text=text, text_color=color)

    def update_system_pulse(self):
        metrics = self.get_system_metrics(interval=0)
        cpu = metrics.get("cpu_percent", 0.0)
        memory = metrics.get("memory_percent", 0.0)
        disk = metrics.get("disk_percent", 0.0)

        now = time.monotonic()
        if now - self.last_gpu_refresh >= 30:
            self.refresh_gpu_info()
            self.last_gpu_refresh = now

        self.cpu_label.configure(text=f"CPU: {cpu:.0f}%")
        self.cpu_bar.set(min(max(cpu / 100.0, 0.0), 1.0))

        self.mem_label.configure(text=f"Memory: {memory:.0f}%")
        self.mem_bar.set(min(max(memory / 100.0, 0.0), 1.0))

        self.disk_label.configure(text=f"Disk: {disk:.0f}%")
        self.disk_bar.set(min(max(disk / 100.0, 0.0), 1.0))

        self.window.after(2000, self.update_system_pulse)

    def refresh_gpu_info(self):
        self.gpu_name = "N/A"
        self.gpu_vram_gb = None

        if os.name != "nt":
            return

        try:
            import win32com.client
        except Exception:
            return

        try:
            wmi = win32com.client.GetObject("winmgmts:")
            adapters = wmi.InstancesOf("Win32_VideoController")
        except Exception:
            return

        best = None
        for adapter in adapters:
            name = getattr(adapter, "Name", None)
            ram = getattr(adapter, "AdapterRAM", None)
            if name:
                best = (name, ram)
                if ram:
                    break

        if best:
            self.gpu_name = best[0]
            try:
                if best[1]:
                    self.gpu_vram_gb = round(int(best[1]) / (1024 ** 3), 1)
            except Exception:
                self.gpu_vram_gb = None

    def set_connection_status(self, status):
        if threading.current_thread() is not threading.main_thread():
            self.enqueue_ui(self.set_connection_status, status)
            return

        self.connection_status = status.upper()
        if self.connection_status == "ONLINE":
            color = COLORS["success"]
        elif self.connection_status == "OFFLINE":
            color = COLORS["danger"]
        else:
            color = COLORS["warning"]

        self.current_connection_color = color
        self.connection_label.configure(text=f"LM: {self.connection_status}", text_color=color)
        self.update_hud_fields()
        self.refresh_flicker_targets()

    def toggle_task_mode(self):
        self.task_enabled = bool(self.task_var.get())
        self.brain.config.setdefault("agent", {})["enabled"] = self.task_enabled
        self.save_config()
        self.update_hud_fields()
        state = "enabled" if self.task_enabled else "disabled"
        self.add_message("System", f"Task mode {state}.", "system")

    def toggle_monitoring(self):
        self.monitoring_enabled = bool(self.monitor_var.get())
        self.brain.config.setdefault("monitoring", {})["enabled"] = self.monitoring_enabled
        self.save_config()
        self.add_message("System", f"Monitoring {'enabled' if self.monitoring_enabled else 'disabled'}.", "system")

    def toggle_suggestions(self):
        self.suggestions_enabled = bool(self.suggest_var.get())
        self.brain.config.setdefault("proactive_suggestions", {})["enabled"] = self.suggestions_enabled
        self.save_config()
        self.add_message("System", f"Suggestions {'enabled' if self.suggestions_enabled else 'disabled'}.", "system")

    def toggle_auto_queue(self):
        self.auto_queue_enabled = bool(self.auto_queue_var.get())
        self.brain.config.setdefault("proactive_suggestions", {})["auto_queue_actions"] = self.auto_queue_enabled
        self.save_config()
        self.add_message("System", f"Auto-queue {'enabled' if self.auto_queue_enabled else 'disabled'}.", "system")

    def copy_last_response(self):
        if not self.last_assistant_message:
            self.add_message("System", "No assistant response to copy yet.", "system")
            return

        self.window.clipboard_clear()
        self.window.clipboard_append(self.last_assistant_message)
        self.add_message("System", "Copied last response to clipboard.", "system")

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
            with open(file_path, "w", encoding="utf-8") as handle:
                for item in messages:
                    timestamp = item.get("timestamp", "")
                    role = item.get("role", "").capitalize()
                    content = item.get("content", "")
                    handle.write(f"[{timestamp}] {role}: {content}\n")
        except Exception as e:
            self.add_message("System", f"Export failed: {str(e)}", "system")
            return

        self.add_message("System", f"Chat exported to: {file_path}", "system")

    def show_memory_vault(self):
        vault = ctk.CTkToplevel(self.window)
        vault.title("Memory Vault")
        vault.geometry("720x520")
        vault.configure(fg_color=COLORS["bg"])

        tabs = ctk.CTkTabview(vault, fg_color=COLORS["panel"])
        tabs.pack(fill="both", expand=True, padx=12, pady=12)

        profile_tab = tabs.add("Profile")
        memory_tab = tabs.add("Memory")
        summary_tab = tabs.add("Summaries")

        def make_box(parent):
            box = ctk.CTkTextbox(
                parent,
                fg_color=COLORS["panel_alt"],
                text_color=COLORS["text"],
                font=FONTS["body"],
                wrap="word"
            )
            box.pack(fill="both", expand=True, padx=12, pady=12)
            return box

        profile_box = make_box(profile_tab)
        memory_box = make_box(memory_tab)
        summary_box = make_box(summary_tab)

        profile = self.brain.memory.get_user_profile()
        profile_lines = ["User Profile:"]
        for key, values in profile.items():
            label = key.replace("_", " ").title()
            profile_lines.append(f"\n{label}:")
            if values:
                for value in values:
                    profile_lines.append(f"- {value}")
            else:
                profile_lines.append("- None")

        profile_box.insert("end", "\n".join(profile_lines))
        profile_box.configure(state="disabled")

        memory_items = self.brain.memory.get_user_memory(limit=200, include_meta=True)
        memory_lines = ["Long-term Memory:"]
        if memory_items:
            for item in memory_items:
                memory_lines.append(
                    f"- [{item.get('type')}] {item.get('value')} (used {item.get('use_count', 0)}x)"
                )
        else:
            memory_lines.append("- No long-term memory items yet.")
        memory_box.insert("end", "\n".join(memory_lines))
        memory_box.configure(state="disabled")

        summaries = self.brain.memory.get_preference("conversation_summaries", default=[])
        summary_lines = ["Conversation Summaries:"]
        if summaries:
            for item in summaries[-5:]:
                summary_lines.append(f"\n[{item.get('timestamp', '')}]\n{item.get('summary', '')}")
        else:
            summary_lines.append("- No summaries yet.")
        summary_box.insert("end", "\n".join(summary_lines))
        summary_box.configure(state="disabled")
    
    def send_message(self):
        """Send user message to Sol"""
        message = self.input_box.get().strip()
        if not message:
            return
        
        # Clear input
        self.input_box.delete(0, "end")
        
        # Display user message
        self.add_message("You", message, "user")
        
        # Update status
        self.set_status("THINKING...", COLORS["warning"])
        
        # Process in background thread to keep UI responsive
        thread = threading.Thread(target=self.process_message, args=(message,))
        thread.daemon = True
        thread.start()
    
    def process_message(self, message):
        """Process message with Sol brain"""
        try:
            normalized = message.strip().lower()
            if normalized in ["/stop", "/cancel", "stop task"]:
                self.clear_pending_task()
                self.add_message("System", "Task cancelled.", "system")
                self.set_status("READY", COLORS["success"])
                return

            if self.is_task_command(message):
                if not self.brain.config.get("agent", {}).get("enabled", True):
                    self.add_message("System", "Task mode is disabled in config.json.", "system")
                else:
                    self.process_task_message(message)
                self.set_status("READY", COLORS["success"])
                return

            start_time = time.monotonic()
            result = self.brain.chat(message)
            self.last_response_seconds = time.monotonic() - start_time
            tool_conf = result.get("tool_confidence")
            self.last_tool_confidence = tool_conf if isinstance(tool_conf, (int, float)) else None
            self.set_connection_status("ONLINE")
            
            # Display Sol's response
            self.add_message("Sol", result['response'], "assistant")

            follow_up = result.get("follow_up")
            if isinstance(follow_up, str) and follow_up.strip():
                self.add_message("Sol", follow_up.strip(), "assistant")
            
            # Check if action needed
            if result['action']:
                self.pending_action = result['action']
                if result['needs_approval']:
                    self.show_approval_request(result['action'])
                else:
                    # Auto-execute if approval not required
                    self.execute_pending_action()
            
            # Update status
            self.set_status("READY", COLORS["success"])
            self.update_hud_fields()
        
        except Exception as e:
            self.add_message("System", f"Error: {str(e)}", "system")
            self.set_status("ERROR", COLORS["danger"])
            self.set_connection_status("OFFLINE")

    def send_quick_message(self, message):
        self.input_box.delete(0, "end")
        self.input_box.insert(0, message)
        self.send_message()
    
    def show_approval_request(self, action):
        """Show action approval UI"""
        if threading.current_thread() is not threading.main_thread():
            self.enqueue_ui(self.show_approval_request, action)
            return
        self.approval_label.configure(text=f"⚠ Sol wants to: {action['description']}")
        self.approval_frame.grid()
        self.update_queue_status()
    
    def approve_action(self):
        """User approves the action"""
        if self.pending_action:
            self.add_message("System", f"Executing: {self.pending_action['description']}", "action")
            self.execute_pending_action()
        self.update_queue_status()
    
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
        self.update_queue_status()
    
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
        self.update_queue_status()
    
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
        self.update_queue_status()

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

        self.add_message("Sol", plan["plan_text"], "assistant")
        if plan.get("clarifying_questions"):
            self.add_message("Sol", "Please answer the questions above.", "assistant")
            return

        actions = plan.get("actions") or []
        if not actions:
            self.add_message("System", "No safe actions detected for that plan.", "system")
            return

        self.pending_actions = actions
        self.pending_action = self.pending_actions.pop(0)
        self.show_approval_request(self.pending_action)
        self.update_queue_status()

    def start_monitoring(self):
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

    def get_system_metrics(self, interval=1):
        cpu_percent = psutil.cpu_percent(interval=interval)
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
        while True:
            config = self.brain.config.get("monitoring", {})
            suggestions_config = self.brain.config.get("proactive_suggestions", {})
            interval = max(5, int(config.get("interval_sec", 30)))
            cooldown = suggestions_config.get("cooldown_sec", 600)
            suggestions_enabled = self.suggestions_enabled and suggestions_config.get("enabled", False)
            auto_queue = self.auto_queue_enabled and suggestions_config.get("auto_queue_actions", False)

            if self.monitoring_enabled and not self.is_quiet_hours(config):
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
                                self.add_message("Sol", suggestion, "assistant")

                            if auto_queue and actions and not self.pending_action and not self.pending_actions:
                                self.pending_actions = actions
                                self.pending_action = self.pending_actions.pop(0)
                                self.show_approval_request(self.pending_action)

                            self.last_suggestion_time = now

            time.sleep(interval)
    
    def show_settings(self):
        """Show settings window"""
        settings_window = ctk.CTkToplevel(self.window)
        settings_window.title("Sol Settings")
        settings_window.geometry("520x520")
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

        history_btn = ctk.CTkButton(
            settings_window,
            text="View Chat History",
            command=self.show_chat_history,
            fg_color=COLORS["panel_alt"],
            hover_color=COLORS["outline"],
            text_color=COLORS["text"]
        )
        history_btn.pack(pady=10)

        memory_btn = ctk.CTkButton(
            settings_window,
            text="Open Memory Vault",
            command=self.show_memory_vault,
            fg_color=COLORS["panel_alt"],
            hover_color=COLORS["outline"],
            text_color=COLORS["text"]
        )
        memory_btn.pack(pady=10)

        export_btn = ctk.CTkButton(
            settings_window,
            text="Export Chat History",
            command=self.export_chat_history,
            fg_color=COLORS["panel_alt"],
            hover_color=COLORS["outline"],
            text_color=COLORS["text"]
        )
        export_btn.pack(pady=10)

        dock_btn = ctk.CTkButton(
            settings_window,
            text="Toggle HUD Dock",
            command=self.toggle_hud_dock,
            fg_color=COLORS["panel_alt"],
            hover_color=COLORS["outline"],
            text_color=COLORS["text"]
        )
        dock_btn.pack(pady=10)
        
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
                self.set_connection_status("ONLINE")
            else:
                self.add_message("System", f"✗ Connection failed: {result['error']}", "system")
                self.set_connection_status("OFFLINE")
        
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

    def show_chat_history(self):
        """Show recent chat history"""
        history_window = ctk.CTkToplevel(self.window)
        history_window.title("Chat History")
        history_window.geometry("700x500")
        history_window.configure(fg_color=COLORS["bg"])

        ctk.CTkLabel(
            history_window,
            text="Chat History",
            font=FONTS["section"],
            text_color=COLORS["text"]
        ).pack(pady=12)

        history_box = ctk.CTkTextbox(
            history_window,
            fg_color=COLORS["panel_alt"],
            text_color=COLORS["text"],
            font=FONTS["body"],
            wrap="word"
        )
        history_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        messages = self.brain.memory.get_conversation_history_with_timestamps(limit=200)
        if not messages:
            history_box.insert("end", "No messages found.")
        else:
            for item in messages:
                timestamp = item.get("timestamp", "")
                role = item.get("role", "")
                content = item.get("content", "")

                try:
                    time_label = datetime.fromisoformat(timestamp).strftime("%H:%M")
                except Exception:
                    time_label = "--:--"

                role_label = role.capitalize() if role else "Unknown"
                history_box.insert("end", f"[{time_label}] {role_label}: {content}\n\n")

        history_box.configure(state="disabled")
    
    def clear_memory(self):
        """Clear conversation history"""
        self.brain.memory.clear_old_conversations(keep_last=0)
        self.add_message("System", "Conversation history cleared.", "system")
    
    def run(self):
        """Start the GUI"""
        self.window.mainloop()


if __name__ == "__main__":
    app = SolGUI()
    app.run()
