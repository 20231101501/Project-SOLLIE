"""
Sollie GUI - Cyberdeck Edition
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
from sollie_core import SollieBrain

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


class SollieGUI:
    def __init__(self):
        self.brain = SollieBrain()
        self.pending_action = None
        self.connection_status = "UNKNOWN"
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.last_response_seconds = None
        self.last_tool_confidence = None
        self.glow_phase = 0.0

        agent_config = self.brain.config.get("agent", {})
        self.task_enabled = bool(agent_config.get("enabled", True))
        
        # Setup window
        self.window = ctk.CTk()
        self.window.title("⚡ SOLLIE CYBERDECK ⚡")
        self.window.geometry("1400x850")
        self.window.minsize(1400, 850)
        self.window.configure(fg_color=COLORS["bg"])

        self.ui_queue = queue.Queue()
        self.window.after(100, self.process_ui_queue)
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.setup_ui()
        self.start_monitoring()
        self.animate_glow()
        
    def setup_ui(self):
        """Setup cyberdeck interface"""
        
        # Main container with grid background
        main_frame = ctk.CTkFrame(self.window, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=0, pady=0)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)
        
        # ===== HEADER SECTION =====
        header = ctk.CTkFrame(
            main_frame,
            fg_color=COLORS["panel_alt"],
            corner_radius=0,
            border_width=2,
            border_color=COLORS["accent"]
        )
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(1, weight=1)
        
        # Header left side - Title with scanline effect
        header_left = ctk.CTkFrame(header, fg_color="transparent")
        header_left.grid(row=0, column=0, sticky="w", padx=20, pady=10)
        
        title = ctk.CTkLabel(
            header_left,
            text="⚡ SOLLIE CYBERDECK A9-X ⚡",
            font=FONTS["title"],
            text_color=COLORS["accent"]
        )
        title.pack(side="left")
        
        # Header right side - Status indicators
        header_right = ctk.CTkFrame(header, fg_color="transparent")
        header_right.grid(row=0, column=1, sticky="e", padx=20, pady=10)
        
        # Status indicators frame
        indicators = ctk.CTkFrame(header_right, fg_color="transparent")
        indicators.pack(side="left", padx=(0, 20))
        
        self.status_label = ctk.CTkLabel(
            indicators,
            text="● READY",
            font=FONTS["body_bold"],
            text_color=COLORS["success"]
        )
        self.status_label.pack(side="left", padx=10)
        
        self.connection_label = ctk.CTkLabel(
            indicators,
            text="◆ LM: OFFLINE",
            font=FONTS["caption"],
            text_color=COLORS["danger"]
        )
        self.connection_label.pack(side="left", padx=10)
        
        self.time_label = ctk.CTkLabel(
            indicators,
            text="[00:00:00]",
            font=FONTS["caption"],
            text_color=COLORS["info"]
        )
        self.time_label.pack(side="left", padx=10)
        
        # Accent line under header
        accent_line = ctk.CTkFrame(
            header,
            fg_color=COLORS["accent"],
            height=3
        )
        accent_line.grid(row=1, column=0, columnspan=2, sticky="ew")
        
        # ===== MAIN CONTENT =====
        content = ctk.CTkFrame(main_frame, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=15, pady=15)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)
        
        # Chat display panel with neon border
        chat_title = ctk.CTkLabel(
            content,
            text=">>> SIGNAL LOG <<<",
            font=FONTS["section"],
            text_color=COLORS["accent"]
        )
        chat_title.grid(row=0, column=0, sticky="w", pady=(0, 8))
        
        chat_frame = ctk.CTkFrame(
            content,
            fg_color=COLORS["panel"],
            corner_radius=0,
            border_width=2,
            border_color=COLORS["info"]
        )
        chat_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 15))
        
        # Chat text widget with custom styling
        self.chat_display = tk.Text(
            chat_frame,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Courier New", 13),
            wrap="word",
            relief="flat",
            borderwidth=0,
            padx=15,
            pady=15,
            insertbackground=COLORS["accent"]
        )
        self.chat_display.pack(fill="both", expand=True)
        self.chat_display.configure(state="disabled")
        
        # Tag configuration for formatting
        self.chat_display.tag_config("user_name", foreground=COLORS["accent_alt"], font=("Courier New", 13, "bold"))
        self.chat_display.tag_config("user_msg", foreground=COLORS["text_alt"])
        self.chat_display.tag_config("assistant_name", foreground=COLORS["accent"], font=("Courier New", 13, "bold"))
        self.chat_display.tag_config("assistant_msg", foreground=COLORS["text"])
        self.chat_display.tag_config("system_name", foreground=COLORS["warning"], font=("Courier New", 13, "bold"))
        self.chat_display.tag_config("system_msg", foreground=COLORS["info"])
        self.chat_display.tag_config("code_block", foreground=COLORS["info"], font=("Consolas", 12))
        
        # ===== INPUT SECTION =====
        input_title = ctk.CTkLabel(
            content,
            text=">>> INPUT TERMINAL <<<",
            font=FONTS["section"],
            text_color=COLORS["accent"]
        )
        input_title.grid(row=2, column=0, sticky="w", pady=(0, 8))
        
        input_container = ctk.CTkFrame(
            content,
            fg_color=COLORS["panel_alt"],
            corner_radius=0,
            border_width=2,
            border_color=COLORS["accent_alt"]
        )
        input_container.grid(row=3, column=0, sticky="ew")
        input_container.grid_columnconfigure(0, weight=1)
        
        # Input entry
        self.input_box = ctk.CTkEntry(
            input_container,
            fg_color=COLORS["panel"],
            border_width=1,
            border_color=COLORS["muted"],
            text_color=COLORS["text"],
            font=FONTS["body"],
            placeholder_text=">> ENTER COMMAND...",
            placeholder_text_color=COLORS["muted"]
        )
        self.input_box.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        self.input_box.bind("<Return>", lambda e: self.send_message())
        
        # Control buttons with cyberpunk styling
        button_frame = ctk.CTkFrame(input_container, fg_color="transparent")
        button_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        button_frame.grid_columnconfigure(4, weight=1)
        
        send_btn = ctk.CTkButton(
            button_frame,
            text="▶ SEND",
            command=self.send_message,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color=COLORS["bg"],
            font=FONTS["body_bold"],
            height=40,
            width=120
        )
        send_btn.grid(row=0, column=0, padx=(0, 10))
        
        clear_btn = ctk.CTkButton(
            button_frame,
            text="⟲ CLEAR",
            command=self.clear_chat,
            fg_color=COLORS["panel"],
            hover_color=COLORS["outline_bright"],
            text_color=COLORS["accent"],
            border_width=1,
            border_color=COLORS["accent"],
            font=FONTS["body_bold"],
            height=40,
            width=120
        )
        clear_btn.grid(row=0, column=1, padx=(0, 10))
        
        export_btn = ctk.CTkButton(
            button_frame,
            text="⬇ EXPORT",
            command=self.export_chat,
            fg_color=COLORS["panel"],
            hover_color=COLORS["outline_bright"],
            text_color=COLORS["info"],
            border_width=1,
            border_color=COLORS["info"],
            font=FONTS["body_bold"],
            height=40,
            width=120
        )
        export_btn.grid(row=0, column=2, padx=(0, 10))
        
        # Add welcome message
        self.add_message("SYSTEM", "⚡ SOLLIE CYBERDECK INITIALIZED ⚡\nReady for neural input...", "system")
        
    def add_message(self, sender, message, msg_type="user"):
        """Add a message to chat display"""
        if threading.current_thread() is not threading.main_thread():
            self.enqueue_ui(self.add_message, sender, message, msg_type)
            return
        
        self.chat_display.configure(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if msg_type == "user":
            self.chat_display.insert("end", f"[{timestamp}] YOU: ", "user_name")
            self.chat_display.insert("end", f"{message}\n\n", "user_msg")
        elif msg_type == "assistant":
            self.chat_display.insert("end", f"[{timestamp}] SOLLIE: ", "assistant_name")
            self.chat_display.insert("end", f"{message}\n\n", "assistant_msg")
        elif msg_type == "system":
            self.chat_display.insert("end", f"[{timestamp}] {sender}: ", "system_name")
            self.chat_display.insert("end", f"{message}\n\n", "system_msg")
        
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")
    
    def clear_chat(self):
        """Clear chat history"""
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        self.add_message("SYSTEM", "⚡ SIGNAL LOG CLEARED ⚡", "system")
    
    def export_chat(self):
        """Export chat to file"""
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"sollie_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.chat_display.get("1.0", "end"))
                self.add_message("SYSTEM", f"✓ Chat exported to: {file_path}", "system")
        except Exception as e:
            self.add_message("SYSTEM", f"✗ Export failed: {str(e)}", "system")
    
    def send_message(self):
        """Send user message to Sollie"""
        message = self.input_box.get().strip()
        if not message:
            return
        
        self.input_box.delete(0, "end")
        self.add_message("YOU", message, "user")
        self.set_status("⟳ THINKING...", COLORS["warning"])
        
        thread = threading.Thread(target=self.process_message, args=(message,))
        thread.daemon = True
        thread.start()
    
    def process_message(self, message):
        """Process message with Sollie brain"""
        try:
            start_time = time.monotonic()
            result = self.brain.chat(message)
            self.last_response_seconds = time.monotonic() - start_time
            tool_conf = result.get("tool_confidence")
            self.last_tool_confidence = tool_conf if isinstance(tool_conf, (int, float)) else None
            
            self.set_connection_status("ONLINE")
            self.add_message("SOLLIE", result['response'], "assistant")
            
            if result.get('follow_up'):
                self.add_message("SOLLIE", f"[Follow-up: {result['follow_up']}]", "system")
            
            if result['action']:
                self.pending_action = result['action']
                if result['needs_approval']:
                    action_desc = result['action'].get('description', str(result['action']))
                    self.add_message("SYSTEM", f"⚠ ACTION PENDING APPROVAL:\n{action_desc}", "system")
            
            self.set_status("● READY", COLORS["success"])
        
        except Exception as e:
            self.add_message("SYSTEM", f"✗ ERROR: {str(e)}", "system")
            self.set_status("✗ ERROR", COLORS["danger"])
            self.set_connection_status("OFFLINE")
    
    def set_status(self, text, color):
        """Update status label"""
        if threading.current_thread() is not threading.main_thread():
            self.enqueue_ui(self.set_status, text, color)
            return
        self.status_label.configure(text=text, text_color=color)
    
    def set_connection_status(self, status):
        """Update connection status"""
        if threading.current_thread() is not threading.main_thread():
            self.enqueue_ui(self.set_connection_status, status)
            return
        self.connection_status = status
        color = COLORS["success"] if status == "ONLINE" else COLORS["danger"]
        symbol = "◆" if status == "ONLINE" else "◇"
        self.connection_label.configure(text=f"{symbol} LM: {status.upper()}", text_color=color)
    
    def update_time(self):
        """Update time display with glow effect"""
        now = datetime.now().strftime("%H:%M:%S")
        self.time_label.configure(text=f"[{now}]")
        self.window.after(1000, self.update_time)
    
    def animate_glow(self):
        """Animate glow effect on headers"""
        self.glow_phase += 0.15
        glow = 0.5 + 0.5 * math.sin(self.glow_phase)
        
        # Smoothly transition between accent colors
        if glow > 0.5:
            color = COLORS["accent"]
        else:
            color = COLORS["info"]
        
        try:
            # Could update accent colors here for pulsing effect
            pass
        except Exception:
            pass
        
        self.window.after(100, self.animate_glow)
    
    def process_ui_queue(self):
        """Process UI queue"""
        try:
            while True:
                func, args, kwargs = self.ui_queue.get_nowait()
                func(*args, **kwargs)
        except queue.Empty:
            pass
        self.window.after(100, self.process_ui_queue)
    
    def enqueue_ui(self, func, *args, **kwargs):
        """Queue UI operation"""
        self.ui_queue.put((func, args, kwargs))
    
    def start_monitoring(self):
        """Start monitoring tasks"""
        self.update_time()
        self.check_connection_status()
    
    def check_connection_status(self):
        """Check LM Studio connection"""
        thread = threading.Thread(target=self._check_connection)
        thread.daemon = True
        thread.start()
    
    def _check_connection(self):
        """Background thread to check connection"""
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
        """Start the GUI"""
        self.window.mainloop()


def main():
    gui = SollieGUI()
    gui.run()


if __name__ == "__main__":
    main()
