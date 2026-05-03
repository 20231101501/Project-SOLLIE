"""
Sollie GUI - Graphical User Interface
Modern chat interface with approval system
"""

import customtkinter as ctk
from tkinter import scrolledtext
import threading
from sollie_core import SollieBrain
from datetime import datetime


class SollieGUI:
    def __init__(self):
        # Initialize Sollie brain
        self.brain = SollieBrain()
        self.pending_action = None
        
        # Setup window
        self.window = ctk.CTk()
        self.window.title("Sollie - Your AI Assistant")
        self.window.geometry("900x700")
        
        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface"""
        
        # Main container
        main_frame = ctk.CTkFrame(self.window)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Header
        header = ctk.CTkLabel(
            main_frame, 
            text="🤖 Sollie - AI Assistant", 
            font=("Arial", 24, "bold")
        )
        header.pack(pady=10)
        
        # Status indicator
        self.status_label = ctk.CTkLabel(
            main_frame,
            text="● Ready",
            font=("Arial", 12),
            text_color="green"
        )
        self.status_label.pack(pady=5)
        
        # Chat display area
        chat_frame = ctk.CTkFrame(main_frame)
        chat_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.chat_display = ctk.CTkTextbox(
            chat_frame,
            font=("Arial", 12),
            wrap="word",
            state="disabled"
        )
        self.chat_display.pack(fill="both", expand=True)
        
        # Action approval frame (hidden by default)
        self.approval_frame = ctk.CTkFrame(main_frame)
        self.approval_frame.pack(fill="x", padx=10, pady=5)
        self.approval_frame.pack_forget()  # Hide initially
        
        self.approval_label = ctk.CTkLabel(
            self.approval_frame,
            text="",
            font=("Arial", 12, "bold")
        )
        self.approval_label.pack(pady=5)
        
        approval_buttons = ctk.CTkFrame(self.approval_frame)
        approval_buttons.pack(pady=5)
        
        self.approve_btn = ctk.CTkButton(
            approval_buttons,
            text="✓ Approve",
            command=self.approve_action,
            fg_color="green",
            hover_color="darkgreen",
            width=120
        )
        self.approve_btn.pack(side="left", padx=5)
        
        self.deny_btn = ctk.CTkButton(
            approval_buttons,
            text="✗ Deny",
            command=self.deny_action,
            fg_color="red",
            hover_color="darkred",
            width=120
        )
        self.deny_btn.pack(side="left", padx=5)
        
        # Input area
        input_frame = ctk.CTkFrame(main_frame)
        input_frame.pack(fill="x", padx=10, pady=10)
        
        self.input_box = ctk.CTkEntry(
            input_frame,
            placeholder_text="Type your message to Sollie...",
            font=("Arial", 14),
            height=40
        )
        self.input_box.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.input_box.bind("<Return>", lambda e: self.send_message())
        
        self.send_btn = ctk.CTkButton(
            input_frame,
            text="Send",
            command=self.send_message,
            width=100,
            height=40,
            font=("Arial", 14, "bold")
        )
        self.send_btn.pack(side="right")
        
        # Settings button
        settings_btn = ctk.CTkButton(
            main_frame,
            text="⚙ Settings",
            command=self.show_settings,
            width=100
        )
        settings_btn.pack(pady=5)
        
        # Add welcome message
        self.add_message("Sollie", "Hello! I'm Sollie, your AI assistant. I'm here to help you with tasks on your PC. What can I do for you today?", "assistant")
    
    def add_message(self, sender, message, msg_type="user"):
        """Add a message to the chat display"""
        self.chat_display.configure(state="normal")
        
        timestamp = datetime.now().strftime("%H:%M")
        
        if msg_type == "user":
            prefix = f"\n[{timestamp}] You: "
            self.chat_display.insert("end", prefix, "user_name")
            self.chat_display.insert("end", f"{message}\n", "user_msg")
        elif msg_type == "assistant":
            prefix = f"\n[{timestamp}] Sollie: "
            self.chat_display.insert("end", prefix, "assistant_name")
            self.chat_display.insert("end", f"{message}\n", "assistant_msg")
        elif msg_type == "system":
            self.chat_display.insert("end", f"\n[{timestamp}] SYSTEM: {message}\n", "system_msg")
        elif msg_type == "action":
            self.chat_display.insert("end", f"\n[{timestamp}] ⚡ ACTION: {message}\n", "action_msg")
        
        # Configure tags for styling
        self.chat_display.tag_config("user_name", foreground="#5DADE2")
        self.chat_display.tag_config("assistant_name", foreground="#52BE80")
        self.chat_display.tag_config("system_msg", foreground="#F39C12")
        self.chat_display.tag_config("action_msg", foreground="#E74C3C")
        
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")
    
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
        self.status_label.configure(text="● Thinking...", text_color="orange")
        
        # Process in background thread to keep UI responsive
        thread = threading.Thread(target=self.process_message, args=(message,))
        thread.daemon = True
        thread.start()
    
    def process_message(self, message):
        """Process message with Sollie brain"""
        try:
            result = self.brain.chat(message)
            
            # Display Sollie's response
            self.add_message("Sollie", result['response'], "assistant")
            
            # Check if action needed
            if result['action'] and result['needs_approval']:
                self.pending_action = result['action']
                self.show_approval_request(result['action'])
            elif result['action'] and not result['needs_approval']:
                # Auto-execute if approval not required
                self.execute_pending_action()
            
            # Update status
            self.status_label.configure(text="● Ready", text_color="green")
        
        except Exception as e:
            self.add_message("System", f"Error: {str(e)}", "system")
            self.status_label.configure(text="● Error", text_color="red")
    
    def show_approval_request(self, action):
        """Show action approval UI"""
        self.approval_label.configure(text=f"⚠ Sollie wants to: {action['description']}")
        self.approval_frame.pack(fill="x", padx=10, pady=5)
    
    def approve_action(self):
        """User approves the action"""
        if self.pending_action:
            self.add_message("System", f"Executing: {self.pending_action['description']}", "action")
            self.execute_pending_action()
        self.hide_approval_ui()
    
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
        self.hide_approval_ui()
        self.pending_action = None
    
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
    
    def hide_approval_ui(self):
        """Hide the approval UI"""
        self.approval_frame.pack_forget()
    
    def show_settings(self):
        """Show settings window"""
        settings_window = ctk.CTkToplevel(self.window)
        settings_window.title("Sollie Settings")
        settings_window.geometry("500x400")
        
        ctk.CTkLabel(
            settings_window,
            text="Settings",
            font=("Arial", 20, "bold")
        ).pack(pady=20)
        
        # Connection test
        test_btn = ctk.CTkButton(
            settings_window,
            text="Test LM Studio Connection",
            command=self.test_lm_studio
        )
        test_btn.pack(pady=10)
        
        # View action log
        log_btn = ctk.CTkButton(
            settings_window,
            text="View Action Log",
            command=self.show_action_log
        )
        log_btn.pack(pady=10)
        
        # Clear memory
        clear_btn = ctk.CTkButton(
            settings_window,
            text="Clear Conversation History",
            command=self.clear_memory,
            fg_color="orange"
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
