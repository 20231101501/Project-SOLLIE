"""
Sollie Core - AI Brain
Connects LM Studio, memory, and PC actions with safety layer
"""

import requests
import json
import re
from pathlib import Path
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

    def parse_plan_response(self, response_text):
        """Parse JSON plan response, fall back to a minimal plan"""
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return {"steps": [], "assumptions": [], "clarifying_questions": []}

    def plan_task(self, user_goal):
        """Create a short plan and map steps to safe actions"""
        agent_config = self.config.get("agent", {})
        max_steps = agent_config.get("max_steps", 5)

        system_prompt = (
            "You are Sollie, a careful planner. Create a short step-by-step plan "
            f"with at most {max_steps} steps. Return JSON only with keys: "
            "steps (array of strings), assumptions (array of strings), "
            "clarifying_questions (array of strings)."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_goal}
        ]

        try:
            response = self.call_lm_studio(messages)
            plan = self.parse_plan_response(response)
        except Exception:
            plan = {"steps": [user_goal], "assumptions": [], "clarifying_questions": []}

        steps = plan.get("steps") or [user_goal]
        steps = [step for step in steps if isinstance(step, str) and step.strip()][:max_steps]

        actions = []
        for step in steps:
            action = self.detect_action_intent(step, "")
            if action:
                actions.append(action)

        plan_lines = ["Here is a plan:"]
        for i, step in enumerate(steps, start=1):
            plan_lines.append(f"{i}. {step}")

        assumptions = plan.get("assumptions") or []
        if assumptions:
            plan_lines.append("Assumptions:")
            for item in assumptions:
                plan_lines.append(f"- {item}")

        clarifying_questions = plan.get("clarifying_questions") or []
        if clarifying_questions:
            plan_lines.append("Questions:")
            for item in clarifying_questions:
                plan_lines.append(f"- {item}")

        return {
            "plan_text": "\n".join(plan_lines),
            "actions": actions,
            "clarifying_questions": clarifying_questions
        }
    
    def detect_action_intent(self, user_message, ai_response):
        """
        Detect if user wants Sollie to perform an action
        Returns action dict or None
        """
        user_lower = user_message.lower()

        def normalize_text(text):
            return re.sub(r"[^a-z0-9]", "", text.lower())

        allowed_file_extensions = self.config['safety'].get('allowed_file_extensions') or [
            ".txt",
            ".md",
            ".pdf",
            ".docx",
            ".xlsx",
            ".pptx",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".bmp",
            ".mp4",
            ".mkv",
            ".mov",
            ".avi",
            ".mp3",
            ".wav",
            ".flac",
        ]
        allowed_file_extensions = {ext.lower() for ext in allowed_file_extensions}

        allowed_dir_names = [
            dir_name.lower() for dir_name in self.config['safety'].get('allowed_directories', [])
        ]

        image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
        video_extensions = {".mp4", ".mkv", ".mov", ".avi"}
        audio_extensions = {".mp3", ".wav", ".flac"}

        def is_allowed_file_candidate(candidate):
            if not candidate:
                return False
            suffix = Path(candidate).suffix.lower()
            if not suffix:
                return False
            return suffix in allowed_file_extensions

        def extract_file_candidate(text):
            quoted = re.search(r'["\']([^"\']+\.[A-Za-z0-9]{1,10})["\']', text)
            if quoted:
                return quoted.group(1)

            for token in reversed(text.split()):
                cleaned = token.strip("\"'.,")
                if '.' in cleaned and not cleaned.lower().startswith(('http://', 'https://')):
                    return cleaned

            return None

        def extract_filename(text):
            quoted = re.search(r'["\']([^"\']+\.[A-Za-z0-9]{1,10})["\']', text)
            if quoted:
                return quoted.group(1)

            match = re.search(r'(?:file|document)\s+(?:called|named)?\s*([^\s,]+)', text, re.IGNORECASE)
            if match:
                return match.group(1).strip("\"'.,")

            for token in reversed(text.split()):
                cleaned = token.strip("\"'.,")
                if '.' in cleaned and not cleaned.lower().startswith(('http://', 'https://')):
                    return cleaned

            return None

        def extract_directory_candidate(text):
            match = re.search(
                r"(?:open|show|browse)\s+(?:the|my)?\s*([\w\s\-_.]+?)(?:\s+(?:folder|directory|file))?\s*$",
                text,
                re.IGNORECASE
            )
            if not match:
                return None

            candidate = match.group(1).strip(" \"'.,")
            candidate = re.sub(r"\b(folder|directory|file)\b$", "", candidate, flags=re.IGNORECASE).strip()
            return candidate or None

        def normalize_extensions(exts):
            return sorted({ext for ext in exts if ext in allowed_file_extensions})
        
        # File operations
        if any(keyword in user_lower for keyword in ['create file', 'make file', 'new file']):
            filename = extract_filename(user_message)
            if filename:
                return {
                    "type": "create_file",
                    "params": {"filepath": filename, "content": ""},
                    "description": f"Create file: {filename}"
                }

        # Random file operations
        if "random" in user_lower:
            if any(word in user_lower for word in ["image", "photo", "picture", "jpg", "jpeg", "png", "gif", "webp", "bmp"]):
                exts = normalize_extensions(image_extensions)
                return {
                    "type": "open_random_file",
                    "params": {"file_extensions": exts},
                    "description": "Open random image"
                }

            if any(word in user_lower for word in ["video", "movie", "mp4", "mkv", "mov", "avi"]):
                exts = normalize_extensions(video_extensions)
                return {
                    "type": "open_random_file",
                    "params": {"file_extensions": exts},
                    "description": "Open random video"
                }

            if any(word in user_lower for word in ["audio", "music", "song", "mp3", "wav", "flac"]):
                exts = normalize_extensions(audio_extensions)
                return {
                    "type": "open_random_file",
                    "params": {"file_extensions": exts},
                    "description": "Open random audio file"
                }

            if "random file" in user_lower or "random document" in user_lower:
                return {
                    "type": "open_random_file",
                    "params": {"file_extensions": sorted(allowed_file_extensions)},
                    "description": "Open random file"
                }
        
        # Open folder
        folder_signal = (
            any(word in user_lower for word in ["folder", "directory"]) or
            any(dir_name in user_lower for dir_name in allowed_dir_names) or
            "camera roll" in user_lower
        )
        if folder_signal and "open" in user_lower:
            candidate = extract_directory_candidate(user_message)
            if candidate:
                return {
                    "type": "open_directory",
                    "params": {"directory": candidate},
                    "description": f"Open folder: {candidate}"
                }

        # Open application
        if any(keyword in user_lower for keyword in ['open', 'launch', 'start']):
            # Try to detect app name
            file_candidate = extract_file_candidate(user_message)
            if is_allowed_file_candidate(file_candidate):
                file_name = Path(file_candidate).name
                return {
                    "type": "open_file",
                    "params": {"filepath": file_candidate},
                    "description": f"Open file: {file_name}"
                }

            normalized_user = normalize_text(user_message)
            for app in self.config['safety']['allowed_applications']:
                app_base = Path(app).stem.lower()
                if app_base in user_lower or normalize_text(app_base) in normalized_user:
                    return {
                        "type": "open_application",
                        "params": {"app_name": app},
                        "description": f"Open {app_base}"
                    }
        
        # Close application
        if any(keyword in user_lower for keyword in ['close', 'quit', 'stop']):
            normalized_user = normalize_text(user_message)
            for app in self.config['safety']['allowed_applications']:
                app_base = Path(app).stem.lower()
                if app_base in user_lower or normalize_text(app_base) in normalized_user:
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
