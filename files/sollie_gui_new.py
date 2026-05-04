"""
Sollie GUI - Simplified Practical Interface
Clean, minimalist design with better readability
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

# Modern, clean color scheme
COLORS = {
    "bg": "#1e1e1e",
    "panel": "#252526",
    "panel_alt": "#2d2d2d",
    "outline": "#3e3e42",
    "outline_bright": "#5a5a5f",
    "text": "#d4d4d4",
    "muted": "#a0a0a0",
    "accent": "#007acc",
    "accent_hover": "#0095f7",
    "accent_alt": "#4ec9b0",
    "warning": "#f1d000",
    "danger": "#f44747",
    "info": "#3aa5ff",
    "success": "#2d9d78",
}

# Larger, more readable fonts
FONTS = {
    "title": ("Segoe UI", 20, "bold"),
    "subtitle": ("Segoe UI", 14),
    "section": ("Segoe UI", 14, "bold"),
    "body": ("Segoe UI", 14),
    "body_bold": ("Segoe UI", 14, "bold"),
    "caption": ("Segoe UI", 12),
    "code": ("Consolas", 13)
}


class SollieGUI:
    def __init__(self):
        self.brain = SollieBrain()
        self.pending_action = None
        self.pending_actions = []
        self.connection_status = "UNKNOWN"
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.last_response_seconds = None
        self.last_tool_confidence = None

        agent_config = self.brain.config.get("agent", {})
        self.task_enabled = bool(agent_config.get("enabled", True))
        
        # Setup window
        self.window = ctk.CTk()
        self.window.title("SOLLIE - AI Assistant")
        self.window.geometry("1200x750")
        self.window.minsize(1200, 750)
        self.window.configure(fg_color=COLORS["bg"])

        self.ui_queue = queue.Queue()
        self.window.after(100, self.process_ui_queue)
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.setup_ui()
        self.start_monitoring()
        
    def setup_ui(self):
        """Setup clean, practical interface"""
        
        # Main container
        main_frame = ctk.CTkFrame(self.window, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=0, pady=0)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)
        
        # Header bar
        header = ctk.CTkFrame(
            main_frame,
            fg_color=COLORS["panel_alt"],
            corner_radius=0,
            height=60
        )
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(1, weight=1)
        
        title = ctk.CTkLabel(
            header,
            text="SOLLIE - Offline AI Assistant",
            font=FONTS["title"],
            text_color=COLORS["accent"]
        )
        title.grid(row=0, column=0, sticky="w", padx=20, pady=15)
        
        # Status info
        status_frame = ctk.CTkFrame(header, fg_color="transparent")
        status_frame.grid(row=0, column=1, sticky="e", padx=20, pady=15)
        
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="READY",
            font=FONTS["body_bold"],
            text_color=COLORS["success"]
        )
        self.status_label.pack(side="left", padx=(0, 15))
        
        self.connection_label = ctk.CTkLabel(
            status_frame,
            text="LM: UNKNOWN",
            font=FONTS["caption"],
            text_color=COLORS["muted"]
        )
        self.connection_label.pack(side="left", padx=(0, 15))
        
        self.time_label = ctk.CTkLabel(
            status_frame,
            text="00:00",
            font=FONTS["caption"],
            text_color=COLORS["muted"]
        )
        self.time_label.pack(side="left")
        
        # Main content area
        content = ctk.CTkFrame(main_frame, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)
        
        # Chat display (top)
        chat_label = ctk.CTkLabel(
            content,
            text="Chat History",
            font=FONTS["section"],
            text_color=COLORS["text"]
        )
        chat_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        chat_frame = ctk.CTkFrame(
            content,
            fg_color=COLORS["panel"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["outline"]
        )
        chat_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        
        self.chat_display = tk.Text(
            chat_frame,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Consolas", 12),
            wrap="word",
            relief="flat",
            borderwidth=0,
            padx=15,
            pady=15
        )
        self.chat_display.pack(fill="both", expand=True)
        self.chat_display.configure(state="disabled")
        
        # Tag configuration for formatting
        self.chat_display.tag_config("user_name", foreground=COLORS["accent"])
        self.chat_display.tag_config("user_msg", foreground=COLORS["text"])
        self.chat_display.tag_config("assistant_name", foreground=COLORS["accent_alt"])
        self.chat_display.tag_config("assistant_msg", foreground=COLORS["text"])
        self.chat_display.tag_config("system_name", foreground=COLORS["warning"])
        self.chat_display.tag_config("system_msg", foreground=COLORS["muted"])
        self.chat_display.tag_config("code_block", foreground=COLORS["info"])
        
        # Input area (bottom)
        input_frame = ctk.CTkFrame(content, fg_color="transparent")
        input_frame.grid(row=2, column=0, sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)
        
        input_label = ctk.CTkLabel(
            input_frame,
            text="Your Message",
            font=FONTS["section"],
            text_color=COLORS["text"]
        )
        input_label.pack(anchor="w", pady=(5, 0))
        
        input_container = ctk.CTkFrame(
            input_frame,
            fg_color=COLORS["panel"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["outline"]
        )
        input_container.pack(fill="x", pady=(5, 0))
        input_container.grid_columnconfigure(0, weight=1)
        
        self.input_box = ctk.CTkEntry(
            input_container,
            fg_color=COLORS["panel"],
            border_width=0,
            text_color=COLORS["text"],
            font=FONTS["body"],
            placeholder_text="Type your message here...",
            placeholder_text_color=COLORS["muted"]
        )
        self.input_box.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        self.input_box.bind("<Return>", lambda e: self.send_message())
        
        # Button bar
        button_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=(8, 0))
        button_frame.pack_propagate(False)
        
        send_btn = ctk.CTkButton(
            button_frame,
            text="Send",
            command=self.send_message,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color=COLORS["bg"],
            font=FONTS["body_bold"],
            height=40,
            width=100
        )
        send_btn.pack(side="left", padx=(0, 8))
        
        clear_btn = ctk.CTkButton(
            button_frame,
            text="Clear Chat",
            command=self.clear_chat,
            fg_color=COLORS["panel_alt"],
            hover_color=COLORS["outline"],
            text_color=COLORS["text"],
            font=FONTS["body_bold"],
            height=40,
            width=100
        )
        clear_btn.pack(side="left")
        
    def add_message(self, sender, message, msg_type="user"):
        """Add a message to chat display"""
        if threading.current_thread() is not threading.main_thread():
            self.enqueue_ui(self.add_message, sender, message, msg_type)
            return
        
        self.chat_display.configure(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if msg_type == "user":
            self.chat_display.insert("end", f"[{timestamp}] You: ", "user_name")
            self.chat_display.insert("end", f"{message}\n\n", "user_msg")
        elif msg_type == "assistant":
            self.chat_display.insert("end", f"[{timestamp}] Sollie: ", "assistant_name")
            self.chat_display.insert("end", f"{message}\n\n", "assistant_msg")
        elif msg_type == "system":
            self.chat_display.insert("end", f"[{timestamp}] System: ", "system_name")
            self.chat_display.insert("end", f"{message}\n\n", "system_msg")
        
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")
    
    def clear_chat(self):
        """Clear chat history"""
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        self.chat_display.configure(state="disabled")
    
    def send_message(self):
        """Send user message to Sollie"""
        message = self.input_box.get().strip()
        if not message:
            return
        
        self.input_box.delete(0, "end")
        self.add_message("You", message, "user")
        self.set_status("THINKING...", COLORS["warning"])
        
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
            self.add_message("Sollie", result['response'], "assistant")
            
            if result['action']:
                self.pending_action = result['action']
                if result['needs_approval']:
                    action_desc = f"Action: {result['action'].get('description', str(result['action']))}"
                    self.add_message("System", f"Approval needed:\n{action_desc}", "system")
            
            self.set_status("READY", COLORS["success"])
        
        except Exception as e:
            self.add_message("System", f"Error: {str(e)}", "system")
            self.set_status("ERROR", COLORS["danger"])
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
        self.connection_label.configure(text=f"LM: {status.upper()}")
    
    def update_time(self):
        """Update time display"""
        now = datetime.now().strftime("%H:%M")
        self.time_label.configure(text=now)
        self.window.after(1000, self.update_time)
    
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
