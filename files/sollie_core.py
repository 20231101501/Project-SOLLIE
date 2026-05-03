"""
Sollie Core - AI Brain
Connects LM Studio, memory, and PC actions with safety layer
"""

import requests
import json
from sollie_memory import SollieMemory
from sollie_actions import SollieActions


class SollieBrain:
    def __init__(self, config_path="config.json"):
        self.config = self.load_config(config_path)
        self.memory = SollieMemory(self.config['memory']['database_path'])
        self.actions = SollieActions(config_path)
        self.lm_studio_url = self.config['lm_studio']['api_url']
        self.personality = self.config['sollie']['personality']
        self.approval_required = self.config['sollie']['approval_required']
    
    def load_config(self, config_path):
        """Load configuration"""
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def chat(self, user_message):
        """
        Main chat function
        1. Process user message
        2. Get AI response from LM Studio
        3. Detect if action is needed
        4. Return response and any action proposals
        """
        # Save user message to memory
        self.memory.add_message("user", user_message)
        
        # Get conversation history for context
        history = self.memory.get_conversation_history(limit=10)
        
        # Build messages for LM Studio
        messages = [
            {"role": "system", "content": self.personality}
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        
        # Call LM Studio
        try:
            response = self.call_lm_studio(messages)
            
            # Save assistant response to memory
            self.memory.add_message("assistant", response)
            
            # Detect if response contains action intent
            action = self.detect_action_intent(user_message, response)
            
            return {
                "response": response,
                "action": action,
                "needs_approval": action is not None and self.approval_required
            }
        
        except Exception as e:
            return {
                "response": f"I apologize, but I'm having trouble connecting to my AI brain. Error: {str(e)}",
                "action": None,
                "needs_approval": False
            }
    
    def call_lm_studio(self, messages):
        """Call LM Studio API"""
        url = f"{self.lm_studio_url}/chat/completions"
        
        payload = {
            "model": self.config['lm_studio']['model'],
            "messages": messages,
            "temperature": self.config['lm_studio']['temperature'],
            "max_tokens": self.config['lm_studio']['max_tokens']
        }
        
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        return data['choices'][0]['message']['content']
    
    def detect_action_intent(self, user_message, ai_response):
        """
        Detect if user wants Sollie to perform an action
        Returns action dict or None
        """
        user_lower = user_message.lower()
        
        # File operations
        if any(keyword in user_lower for keyword in ['create file', 'make file', 'new file']):
            # Extract filename (simple heuristic)
            words = user_message.split()
            for i, word in enumerate(words):
                if word.lower() in ['file', 'document'] and i + 1 < len(words):
                    filename = words[i + 1].strip('",.')
                    return {
                        "type": "create_file",
                        "params": {"filepath": filename, "content": ""},
                        "description": f"Create file: {filename}"
                    }
        
        # Open application
        if any(keyword in user_lower for keyword in ['open', 'launch', 'start']):
            # Try to detect app name
            for app in self.config['safety']['allowed_applications']:
                app_base = app.replace('.exe', '').lower()
                if app_base in user_lower:
                    return {
                        "type": "open_application",
                        "params": {"app_name": app},
                        "description": f"Open {app_base}"
                    }
        
        # Close application
        if any(keyword in user_lower for keyword in ['close', 'quit', 'stop']):
            for app in self.config['safety']['allowed_applications']:
                app_base = app.replace('.exe', '').lower()
                if app_base in user_lower:
                    return {
                        "type": "close_application",
                        "params": {"app_name": app},
                        "description": f"Close {app_base}"
                    }
        
        # Open URL
        if 'http://' in user_lower or 'https://' in user_lower or '.com' in user_lower:
            # Extract URL
            words = user_message.split()
            for word in words:
                if 'http' in word or '.com' in word:
                    return {
                        "type": "open_url",
                        "params": {"url": word.strip('",.')},
                        "description": f"Open {word}"
                    }
        
        # List files
        if 'list files' in user_lower or 'show files' in user_lower:
            # Default to Desktop
            return {
                "type": "list_directory",
                "params": {"directory": str(self.actions.user_home / "Desktop")},
                "description": "List Desktop files"
            }
        
        # System info
        if 'system info' in user_lower or 'pc status' in user_lower or 'computer status' in user_lower:
            return {
                "type": "get_system_info",
                "params": {},
                "description": "Get system information"
            }
        
        return None
    
    def execute_action(self, action):
        """
        Execute an action with safety checks
        """
        action_type = action['type']
        params = action['params']
        
        # Double-check safety
        if not self.actions.is_action_safe(action_type):
            result = {"success": False, "error": "Action blocked by safety system"}
        else:
            # Execute the action
            action_method = getattr(self.actions, action_type, None)
            if action_method:
                result = action_method(**params)
            else:
                result = {"success": False, "error": "Unknown action type"}
        
        # Log the action
        self.memory.log_action(
            action_type=action_type,
            action_details=params,
            approved=True,
            result=json.dumps(result)
        )
        
        return result
    
    def test_connection(self):
        """Test connection to LM Studio"""
        try:
            response = self.call_lm_studio([
                {"role": "user", "content": "Hello! Just testing the connection. Please respond with 'Connection successful!'"}
            ])
            return {"success": True, "response": response}
        except Exception as e:
            return {"success": False, "error": str(e)}
