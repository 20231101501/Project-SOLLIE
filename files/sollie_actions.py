"""
Sollie PC Actions Module
Safe PC control operations with whitelist and approval system
"""

import os
import subprocess
import psutil
import json
from pathlib import Path
import webbrowser


class SollieActions:
    def __init__(self, config_path="config.json"):
        self.config = self.load_config(config_path)
        self.user_home = Path.home()
    
    def load_config(self, config_path):
        """Load configuration from JSON file"""
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def is_action_safe(self, action_type):
        """Check if an action is blocked by safety rules"""
        blocked = self.config['safety']['blocked_actions']
        return action_type.lower() not in blocked
    
    def is_app_allowed(self, app_name):
        """Check if an application is whitelisted"""
        allowed = self.config['safety']['allowed_applications']
        app_name_lower = app_name.lower()
        
        # Check if app is in whitelist (case-insensitive)
        return any(allowed_app.lower() in app_name_lower or app_name_lower in allowed_app.lower() 
                   for allowed_app in allowed)
    
    def is_directory_safe(self, directory):
        """Check if directory is in allowed list"""
        allowed_dirs = self.config['safety']['allowed_directories']
        dir_path = Path(directory)
        
        # Check if it's in user's home directory and in allowed subdirectories
        try:
            relative = dir_path.relative_to(self.user_home)
            first_part = str(relative).split(os.sep)[0]
            return first_part in allowed_dirs
        except ValueError:
            return False
    
    # ===== FILE OPERATIONS =====
    
    def create_file(self, filepath, content=""):
        """Create a new file with optional content"""
        try:
            path = Path(filepath)
            
            if not self.is_directory_safe(path.parent):
                return {"success": False, "error": "Directory not in safe list"}
            
            path.write_text(content)
            return {"success": True, "message": f"File created: {filepath}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def read_file(self, filepath):
        """Read file contents"""
        try:
            path = Path(filepath)
            
            if not self.is_directory_safe(path.parent):
                return {"success": False, "error": "Directory not in safe list"}
            
            content = path.read_text()
            return {"success": True, "content": content}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def list_directory(self, directory):
        """List files in a directory"""
        try:
            path = Path(directory)
            
            if not self.is_directory_safe(path):
                return {"success": False, "error": "Directory not in safe list"}
            
            files = [f.name for f in path.iterdir()]
            return {"success": True, "files": files}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ===== APPLICATION OPERATIONS =====
    
    def open_application(self, app_name):
        """Open an application"""
        try:
            if not self.is_app_allowed(app_name):
                return {"success": False, "error": f"{app_name} is not in the allowed applications list"}
            
            # Try to launch the application
            if os.name == 'nt':  # Windows
                subprocess.Popen(app_name, shell=True)
            else:
                subprocess.Popen([app_name])
            
            return {"success": True, "message": f"Opened {app_name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def close_application(self, app_name):
        """Close a running application"""
        try:
            if not self.is_app_allowed(app_name):
                return {"success": False, "error": f"{app_name} is not in the allowed applications list"}
            
            # Find and terminate the process
            killed = False
            for proc in psutil.process_iter(['name']):
                if app_name.lower() in proc.info['name'].lower():
                    proc.terminate()
                    killed = True
            
            if killed:
                return {"success": True, "message": f"Closed {app_name}"}
            else:
                return {"success": False, "error": f"{app_name} is not running"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def list_running_apps(self):
        """List currently running applications"""
        try:
            apps = []
            for proc in psutil.process_iter(['name', 'pid']):
                apps.append(f"{proc.info['name']} (PID: {proc.info['pid']})")
            
            return {"success": True, "apps": apps[:20]}  # Limit to 20 for readability
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ===== WEB OPERATIONS =====
    
    def open_url(self, url):
        """Open a URL in default browser"""
        try:
            webbrowser.open(url)
            return {"success": True, "message": f"Opened {url}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ===== SYSTEM INFO =====
    
    def get_system_info(self):
        """Get basic system information"""
        try:
            info = {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent
            }
            return {"success": True, "info": info}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ===== COMMAND EXECUTION =====
    
    def execute_safe_command(self, command):
        """Execute a safe system command"""
        # Very restricted - only allow specific safe commands
        safe_commands = ['dir', 'ls', 'echo', 'date', 'time']
        
        cmd_base = command.split()[0].lower()
        if cmd_base not in safe_commands:
            return {"success": False, "error": "Command not in safe list"}
        
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=5)
            return {"success": True, "output": result.stdout}
        except Exception as e:
            return {"success": False, "error": str(e)}
