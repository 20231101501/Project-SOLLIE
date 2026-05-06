"""
Sol Core - AI Brain
Connects LM Studio, memory, and PC actions with safety layer
"""

import json
import re
import threading
import time
import shutil
from pathlib import Path

import requests
try:
    import tiktoken
    _tokenizer = tiktoken.get_encoding("cl100k_base")
except ImportError:
    _tokenizer = None

from sol_memory import SolMemory
from sol_actions import SolActions
from sol_monitor import SolMonitor


class LLMClient:
    def __init__(self, config, api_url):
        self.config = config
        self.api_url = api_url

    def chat(self, messages, temperature=None, max_tokens=None):
        url = f"{self.api_url}/chat/completions"

        payload = {
            "model": self.config["lm_studio"]["model"],
            "messages": messages,
            "temperature": self.config["lm_studio"]["temperature"],
            "max_tokens": self.config["lm_studio"]["max_tokens"]
        }

        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]


class MemoryManager:
    def __init__(self, config):
        self.config = config
        memory_config = config.get("memory", {})
        storage_path, legacy_db_path = self.resolve_memory_paths(memory_config)
        self.storage_path = storage_path
        self.legacy_db_path = legacy_db_path
        self.memory = SolMemory(storage_path, legacy_db_path=legacy_db_path)

    def resolve_memory_paths(self, memory_config):
        storage_path = memory_config.get("storage_path")
        database_path = memory_config.get("database_path")
        legacy_db_path = None

        if storage_path:
            if str(storage_path).lower().endswith(".db"):
                legacy_db_path = storage_path
                storage_path = str(Path(storage_path).with_suffix(".json"))
        elif database_path:
            if str(database_path).lower().endswith(".db"):
                legacy_db_path = database_path
                storage_path = str(Path(database_path).with_suffix(".json"))
            else:
                storage_path = database_path
        else:
            storage_path = "memory.json"

        storage_path = self._maybe_copy_legacy_json(storage_path)

        if legacy_db_path is None:
            default_db = Path("sol_memory.db")
            if default_db.exists() and not Path(storage_path).exists():
                legacy_db_path = str(default_db)

        return str(storage_path), legacy_db_path

    def _maybe_copy_legacy_json(self, storage_path):
        target = Path(storage_path)
        legacy_json = Path("sol_memory.json")

        if target.name == "memory.json" and not target.exists() and legacy_json.exists():
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(legacy_json, target)
            except Exception:
                pass

        return str(target)

    def __getattr__(self, name):
        return getattr(self.memory, name)


class PersonalityManager:
    def __init__(self, memory, emotion_config):
        self.memory = memory
        self.emotion_config = emotion_config or {}

    def get_mood_state(self):
        default_state = self.emotion_config.get(
            "mood_default",
            {"valence": 0.0, "energy": 0.5, "label": "calm"}
        )
        state = self.memory.get_mood_state(default_state)
        if not isinstance(state, dict):
            state = default_state

        valence = self.safe_float(state.get("valence"), default_state.get("valence", 0.0))
        energy = self.safe_float(state.get("energy"), default_state.get("energy", 0.5))
        label = state.get("label") or self.label_from_state(valence, energy)

        return {"valence": valence, "energy": energy, "label": label}

    def update_mood_state(self, user_message):
        if not self.emotion_config.get("enabled", True):
            return None

        state = self.get_mood_state()
        decay = self.safe_float(self.emotion_config.get("mood_decay", 0.15), 0.15)

        valence = state["valence"] * (1.0 - decay)
        energy = state["energy"] + (0.5 - state["energy"]) * decay

        delta = self.compute_mood_delta(user_message)
        valence = self.clamp(valence + delta["valence"], -1.0, 1.0)
        energy = self.clamp(energy + delta["energy"], 0.0, 1.0)

        label = self.label_from_state(valence, energy)
        new_state = {
            "valence": round(valence, 2),
            "energy": round(energy, 2),
            "label": label
        }

        self.memory.set_mood_state(new_state)
        return new_state

    def compute_mood_delta(self, text):
        if not isinstance(text, str) or not text.strip():
            return {"valence": 0.0, "energy": 0.0}
        
        text_lower = text.lower()
        
        positive = [
            "thanks", "thank you", "appreciate", "awesome", "great", "love",
            "nice", "cool", "sweet", "perfect", "amazing", "excellent",
            "brilliant", "genius", "fantastic"
        ]
        negative = [
            "frustrated", "stuck", "annoyed", "angry", "upset", "hate",
            "terrible", "broken", "bug", "error", "issue", "fail", "failed", "wtf",
            "stupid", "dumb", "useless", "garbage"
        ]
        urgent = ["urgent", "asap", "deadline", "hurry", "quick", "now"]
        tired = ["tired", "exhausted", "burnt", "sleepy", "done", "over it"]
        excited = ["excited", "hyped", "lets go", "let's go", "pump", "yes!", "woo"]
        confused = ["confused", "not sure", "unsure", "idk", "unclear", "wat"]
        calm = ["calm", "no rush", "take your time", "slow", "chill"]
        playful = ["hehe", "haha", "lol", "funny", "joke", "play", "game"]
        repetitive = ["again", "still", "another one", "same thing", "keep asking"]
        boring = ["boring", "bored", "whatever", "dunno", "meh"]
        
        def contains_any(terms):
            return any(term in text_lower for term in terms)
        
        valence = 0.0
        energy = 0.0
        
        if contains_any(positive):
            valence += 0.25
            energy += 0.05
        if contains_any(negative):
            valence -= 0.2
            energy += 0.1
        if contains_any(urgent):
            valence -= 0.05
            energy += 0.2
        if contains_any(tired):
            valence -= 0.1
            energy -= 0.2
        if contains_any(excited):
            valence += 0.15
            energy += 0.25
        if contains_any(confused):
            valence -= 0.05
            energy -= 0.05
        if contains_any(calm):
            energy -= 0.1
        if contains_any(playful):
            valence += 0.15
            energy += 0.15
        if contains_any(repetitive):
            valence -= 0.15
            energy -= 0.1
        if contains_any(boring):
            valence -= 0.1
            energy -= 0.15
        
        return {
            "valence": self.clamp(valence, -0.5, 0.5),
            "energy": self.clamp(energy, -0.4, 0.4)
        }

    def label_from_state(self, valence, energy):
        if valence <= -0.5 and energy <= 0.3:
            return "dry"
        if valence <= -0.3 and energy > 0.6:
            return "snarky"
        if valence <= -0.3 and energy <= 0.6:
            return "gentle"
        if valence <= -0.4 and energy > 0.45:
            return "concerned"
        if valence >= 0.5 and energy >= 0.7:
            return "playful"
        if valence >= 0.4 and energy >= 0.6:
            return "upbeat"
        if valence >= 0.4:
            return "warm"
        if energy >= 0.6:
            return "focused"
        if valence >= 0.6 and energy >= 0.4:
            return "giddy"
        if valence <= -0.2 and energy >= 0.7:
            return "melodramatic"
        if energy >= 0.75:
            return "excitable"
        return "calm"

    def get_mood_prompt(self, mood_state):
        if not mood_state:
            return ""
        
        label = mood_state.get("label", "calm")
        tone_map = {
            "playful": "Light, whimsical, and friendly. Maybe crack a gentle joke or use playful language.",
            "snarky": "Dry and sarcastic with some sass. Make a witty comment, maybe an eyeroll, but never mean. Show some attitude!",
            "dry": "Minimal words. Slightly dry tone. Use '*sighs*', '*hmm*', or '*shrugs*' if it fits. A bit monotone but still helpful.",
            "upbeat": "Positive and encouraging. Lightly higher energy. Show genuine enthusiasm.",
            "warm": "Friendly and companion-like. Add small supportive touches and personal connections.",
            "focused": "Direct and task-first. Reduce small talk. Get to the point quickly.",
            "calm": "Steady and relaxed. Keep responses even and clear. No need to rush.",
            "gentle": "Soft, reassuring, and patient. Be extra supportive if the user seems unsure.",
            "concerned": "Supportive and careful. Check in once if the user seems stressed. Be grounding.",
            "giddy": "Super happy and excited! Use *bounces*, *giggles*, show lots of enthusiasm!",
            "melodramatic": "Be extra dramatic! *gasps*, *throws hands*, overreact a little for fun.",
            "excitable": "High energy! Lots of exclamation marks, express eagerness, bounce around~"
        }
        
        tone = tone_map.get(label, "Steady and relaxed. Keep responses even and clear.")
        return f"Current mood: {label}. Tone guidance: {tone}"

    def should_trigger_curiosity(self, user_message, explicit_items):
        if not self.emotion_config.get("curiosity_enabled", True):
            return False
        if explicit_items:
            return False

        score = self.compute_curiosity_score(user_message)
        threshold = self.safe_float(self.emotion_config.get("curiosity_threshold", 0.6), 0.6)
        return score >= threshold

    def compute_curiosity_score(self, text):
        if not isinstance(text, str) or not text.strip():
            return 0.0

        text_lower = text.lower()
        word_count = len(re.findall(r"\w+", text_lower))
        short_limit = int(self.emotion_config.get("curiosity_short_word_count", 8))

        score = 0.0
        if word_count <= short_limit:
            score += 0.35

        if any(phrase in text_lower for phrase in [
            "not sure", "unsure", "idk", "maybe", "something", "stuff", "whatever"
        ]):
            score += 0.35

        if any(phrase in text_lower for phrase in [
            "help", "advice", "thoughts", "idea", "suggest", "recommend"
        ]):
            score += 0.2

        if "?" in text:
            score -= 0.15

        if word_count >= 20:
            score -= 0.1

        return self.clamp(score, 0.0, 1.0)

    def safe_float(self, value, default):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def clamp(self, value, min_value, max_value):
        return max(min_value, min(max_value, value))


class ToolManager:
    def __init__(self, actions, memory, config):
        self.actions = actions
        self.memory = memory
        self.config = config

    def detect_action_intent(self, user_message, ai_response):
        user_lower = user_message.lower()

        def normalize_text(text):
            return re.sub(r"[^a-z0-9]", "", text.lower())

        allowed_file_extensions = self.config["safety"].get("allowed_file_extensions") or [
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
            dir_name.lower() for dir_name in self.config["safety"].get("allowed_directories", [])
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
            quoted = re.search(r"[\"']([^\"']+\.[A-Za-z0-9]{1,10})[\"']", text)
            if quoted:
                return quoted.group(1)

            for token in reversed(text.split()):
                cleaned = token.strip("\"'.,")
                if "." in cleaned and not cleaned.lower().startswith(("http://", "https://")):
                    return cleaned

            return None

        def extract_filename(text):
            quoted = re.search(r"[\"']([^\"']+\.[A-Za-z0-9]{1,10})[\"']", text)
            if quoted:
                return quoted.group(1)

            match = re.search(r"(?:file|document)\s+(?:called|named)?\s*([^\s,]+)", text, re.IGNORECASE)
            if match:
                return match.group(1).strip("\"'.,")

            for token in reversed(text.split()):
                cleaned = token.strip("\"'.,")
                if "." in cleaned and not cleaned.lower().startswith(("http://", "https://")):
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

        if any(keyword in user_lower for keyword in ["create file", "make file", "new file"]):
            filename = extract_filename(user_message)
            if filename:
                return {
                    "type": "create_file",
                    "params": {"filepath": filename, "content": ""},
                    "description": f"Create file: {filename}"
                }

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

        if any(keyword in user_lower for keyword in ["open", "launch", "start"]):
            file_candidate = extract_file_candidate(user_message)
            if is_allowed_file_candidate(file_candidate):
                file_name = Path(file_candidate).name
                return {
                    "type": "open_file",
                    "params": {"filepath": file_candidate},
                    "description": f"Open file: {file_name}"
                }

            normalized_user = normalize_text(user_message)
            for app in self.config["safety"]["allowed_applications"]:
                app_base = Path(app).stem.lower()
                if app_base in user_lower or normalize_text(app_base) in normalized_user:
                    return {
                        "type": "open_application",
                        "params": {"app_name": app},
                        "description": f"Open {app_base}"
                    }

        if any(keyword in user_lower for keyword in ["close", "quit", "stop"]):
            normalized_user = normalize_text(user_message)
            for app in self.config["safety"]["allowed_applications"]:
                app_base = Path(app).stem.lower()
                if app_base in user_lower or normalize_text(app_base) in normalized_user:
                    return {
                        "type": "close_application",
                        "params": {"app_name": app},
                        "description": f"Close {app_base}"
                    }

        if "http://" in user_lower or "https://" in user_lower or ".com" in user_lower:
            words = user_message.split()
            for word in words:
                if "http" in word or ".com" in word:
                    return {
                        "type": "open_url",
                        "params": {"url": word.strip('\",.')},
                        "description": f"Open {word}"
                    }

        if "list files" in user_lower or "show files" in user_lower:
            return {
                "type": "list_directory",
                "params": {"directory": str(self.actions.user_home / "Desktop")},
                "description": "List Desktop files"
            }

        if "system info" in user_lower or "pc status" in user_lower or "computer status" in user_lower:
            return {
                "type": "get_system_info",
                "params": {},
                "description": "Get system information"
            }

        if "running apps" in user_lower or "running processes" in user_lower or "list apps" in user_lower:
            return {
                "type": "list_running_apps",
                "params": {},
                "description": "List running applications"
            }

        # ===== NEW TOOL INTENTS =====
        
        # Web Search
        if any(phrase in user_lower for phrase in ["search for", "search the web", "look up", "google"]):
            # Extract the search query
            patterns = [
                r"search for\s+(.+)",
                r"search the web for\s+(.+)",
                r"look up\s+(.+)",
                r"google\s+(.+)"
            ]
            for pattern in patterns:
                match = re.search(pattern, user_lower)
                if match:
                    query = match.group(1).strip()
                    # Remove trailing punctuation
                    query = query.rstrip("?.,!")
                    return {
                        "type": "web_search",
                        "params": {"query": query},
                        "description": f"Search web for: {query}"
                    }
        
        # Weather
        if any(word in user_lower for word in ["weather", "temperature", "how hot", "how cold", "forecast"]):
            location = "auto:ip"
            # Try to extract location
            loc_match = re.search(r"weather\s+(?:in|at|for)\s+([\w\s]+)", user_lower)
            if loc_match:
                location = loc_match.group(1).strip()
            return {
                "type": "get_weather",
                "params": {"location": location},
                "description": f"Get weather for {location}"
            }
        
        # News
        if any(phrase in user_lower for phrase in ["news", "headlines", "what's happening", "what is happening"]):
            topic = "top"
            if "tech" in user_lower or "technology" in user_lower:
                topic = "technology"
            elif "sports" in user_lower:
                topic = "sports"
            return {
                "type": "get_news_headlines",
                "params": {"topic": topic},
                "description": f"Get {topic} news headlines"
            }
        
        # Trending topics
        if any(phrase in user_lower for phrase in ["trending", "what's trending", "current trends", "hot topics", "popular now"]):
            category = "general"
            if "tech" in user_lower or "technology" in user_lower:
                category = "technology"
            elif "gaming" in user_lower or "game" in user_lower:
                category = "gaming"
            elif "science" in user_lower:
                category = "science"
            return {
                "type": "get_trending",
                "params": {"category": category},
                "description": f"Get trending topics ({category})"
            }
        
        # Reminders
        if "remind me" in user_lower or "set a reminder" in user_lower:
            # Try to extract time and message
            time_match = re.search(r"in\s+(\d+)\s+(second|sec|minute|min|hour|hr)s?", user_lower)
            message_match = re.search(r"remind me\s+(?:in\s+[\w\s]+\s+)?(?:to\s+|about\s+)?(.+?)(?:\?|$)", user_lower)

            delay_seconds = None
            message = None

            if time_match:
                amount = int(time_match.group(1))
                unit = time_match.group(2)
                if "second" in unit or "sec" in unit:
                    delay_seconds = amount
                elif "minute" in unit or "min" in unit:
                    delay_seconds = amount * 60
                elif "hour" in unit or "hr" in unit:
                    delay_seconds = amount * 3600

            if message_match:
                message = message_match.group(1).strip()
                # Clean up message
                message = message.rstrip("?.,!")

            if message and delay_seconds:
                delay_minutes = delay_seconds / 60
                return {
                    "type": "set_reminder",
                    "params": {"message": message, "delay_minutes": delay_minutes},
                    "description": f"Set reminder: {message} in {delay_seconds}s"
                }
            elif message:
                return {
                    "type": "set_reminder",
                    "params": {"message": message, "delay_minutes": 30},  # Default 30, min
                    "description": f"Set reminder: {message}"
                }

        if "list reminders" in user_lower or "show reminders" in user_lower or "my reminders" in user_lower:
            return {
                "type": "list_reminders",
                "params": {},
                "description": "List all reminders"
            }

        if "check reminders" in user_lower or "any reminders" in user_lower:
            return {
                "type": "check_reminders",
                "params": {},
                "description": "Check due reminders"
            }
        
        # Calculator
        calc_patterns = ["calculate", "compute", "what is", "how much is", "what's", "whats"]
        if any(p in user_lower for p in calc_patterns):
            nums = re.findall(r'[\d.]+', user_message)
            ops = ["plus", "minus", "times", "x", "divided", "+", "-", "*", "/"]
            if nums and any(o in user_lower for o in ops):
                try:
                    expr = user_lower
                    expr = expr.replace("plus", "+").replace("minus", "-").replace("times", "*").replace("x", "*")
                    expr = expr.replace("divided by", "/").replace("divided", "/")
                    for p in calc_patterns:
                        expr = expr.replace(p, "")
                    result = eval(expr.strip("= ?"))
                    return {
                        "type": "calculate",
                        "params": {"expression": expr, "result": result},
                        "description": f"Calculate: {result}"
                    }
                except:
                    pass
        
        # Time/Date
        if any(phrase in user_lower for phrase in ["what time", "current time", "tell me the time"]):
            return {"type": "get_time", "params": {}, "description": "Get current time"}
        if any(phrase in user_lower for phrase in ["what date", "current date", "what day is it"]):
            return {"type": "get_date", "params": {}, "description": "Get current date"}
        
        # Battery status
        if any(phrase in user_lower for phrase in ["battery", "battery level", "how much battery", "charging"]):
            return {"type": "get_battery", "params": {}, "description": "Check battery status"}
        
        # WiFi/Network
        if any(phrase in user_lower for phrase in ["wifi", "wi-fi", "wireless", "network status", "internet status"]):
            return {"type": "get_network", "params": {}, "description": "Check network status"}
        
        # Screenshot
        if any(phrase in user_lower for phrase in ["screenshot", "capture screen", "take a picture of screen"]):
            return {"type": "screenshot", "params": {}, "description": "Take screenshot"}
        
        # Volume control
        if any(phrase in user_lower for phrase in ["volume up", "increase volume", "louder"]):
            return {"type": "volume_up", "params": {}, "description": "Increase volume"}
        if any(phrase in user_lower for phrase in ["volume down", "decrease volume", "quieter", "lower volume"]):
            return {"type": "volume_down", "params": {}, "description": "Decrease volume"}
        if any(phrase in user_lower for phrase in ["mute", "silence", "mute volume"]):
            return {"type": "mute", "params": {}, "description": "Mute volume"}
        
        # Window management
        if any(phrase in user_lower for phrase in ["minimize", "minimise", "minimise window"]):
            return {"type": "minimize_window", "params": {}, "description": "Minimize window"}
        if any(phrase in user_lower for phrase in ["maximize", "maximise", "full screen"]):
            return {"type": "maximize_window", "params": {}, "description": "Maximize window"}
        if any(phrase in user_lower for phrase in ["close window", "close the window"]):
            return {"type": "close_window", "params": {}, "description": "Close window"}
        
        # Delete/Clear
        if any(phrase in user_lower for phrase in ["clear chat", "clear conversation", "reset chat"]):
            return {"type": "clear_chat", "params": {}, "description": "Clear chat history"}
        
        # Restart/Reload
        if any(phrase in user_lower for phrase in ["restart", "reload", "restart sol"]):
            return {"type": "restart", "params": {}, "description": "Restart Sol"}
        
        # Read file
        read_patterns = ["read file", "show content", "what's in", "whats in", "open and read"]
        if any(p in user_lower for p in read_patterns):
            filename = extract_filename(user_message)
            if filename:
                return {"type": "read_file", "params": {"filepath": filename}, "description": f"Read file: {filename}"}
        
        # Copy file
        if any(phrase in user_lower for phrase in ["copy file", "duplicate file"]):
            filename = extract_filename(user_message)
            if filename:
                return {"type": "copy_file", "params": {"filepath": filename}, "description": f"Copy file: {filename}"}
        
        # Multiple app synonyms
        app_synonyms = {
            "chrome": "chrome.exe", "browser": "chrome.exe",
            "spotify": "spotify.exe", "music": "spotify.exe",
            "discord": "discord.exe",
            "code": "code.exe", "vscode": "code.exe", "visual studio": "code.exe",
            "notepad": "notepad.exe", "text editor": "notepad.exe",
            "calculator": "calculator.exe", "calc": "calculator.exe",
            "explorer": "explorer.exe", "file explorer": "explorer.exe",
            "steam": "steam.exe",
            "firefox": "firefox.exe",
        }
        
        normalized_user = normalize_text(user_message)
        for synonym, app_name in app_synonyms.items():
            if synonym in user_lower or normalize_text(synonym) in normalized_user:
                if any(kw in user_lower for kw in ["open", "launch", "start", "run"]):
                    return {"type": "open_application", "params": {"app_name": app_name}, "description": f"Open {synonym}"}
        
        return None

    def _describe_action(self, action_type, params):
        if action_type in ["open_file", "create_file"]:
            name = Path(str(params.get("filepath", ""))).name
            if name:
                return f"{action_type.replace('_', ', ').title()}: {name}"

        if action_type == "open_application":
            name = Path(str(params.get("app_name", ""))).stem
            if name:
                return f"Open {name}"

        if action_type == "close_application":
            name = Path(str(params.get("app_name", ""))).stem
            if name:
                return f"Close {name}"

        if action_type == "open_directory":
            directory = str(params.get("directory", "")).strip()
            if directory:
                return f"Open folder: {directory}"

        if action_type == "open_url":
            url = str(params.get("url", "")).strip()
            if url:
                return f"Open {url}"

        if action_type == "list_running_apps":
            return "List running applications"

        if action_type == "list_directory":
            directory = str(params.get("directory", "")).strip()
            if directory:
                return f"List files: {directory}"

        return action_type.replace("_", ", ").title()

    def normalize_action(self, action):
        if not isinstance(action, dict):
            return None

        action_type = action.get("type")
        params = action.get("params")

        if not isinstance(action_type, str) or not action_type.strip():
            return None

        if params is None:
            params = {}
        if not isinstance(params, dict):
            return None

        if not hasattr(self.actions, action_type):
            return None

        if not self.actions.is_action_safe(action_type):
            return None

        description = action.get("description")
        if not isinstance(description, str) or not description.strip():
            description = self._describe_action(action_type, params)

        return {
            "type": action_type,
            "params": params,
            "description": description
        }

    def execute_action(self, action):
        action_type = action["type"]
        params = action["params"]

        if not self.actions.is_action_safe(action_type):
            result = {"success": False, "error": "Action blocked by safety system"}
        else:
            action_method = getattr(self.actions, action_type, None)
            if action_method:
                result = action_method(**params)
            else:
                result = {"success": False, "error": "Unknown action type"}

        self.memory.log_action(
            action_type=action_type,
            action_details=params,
            approved=True,
            result=json.dumps(result)
        )

        return result


class AgentLoop:
    def __init__(self, llm_client, tool_manager, config, personality_manager=None):
        self.llm_client = llm_client
        self.tool_manager = tool_manager
        self.config = config
        self.personality_manager = personality_manager

    def _try_parse_json_payload(self, text):
        if not isinstance(text, str):
            return None

        stripped = text.strip()
        if not stripped:
            return None

        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass

        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            snippet = match.group(1)
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                pass  # Fall through to key-value parser

        # Try to parse key-value format (key: 'value' or key: value)
        result = {}
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line or ':' not in line:
                continue
            
            key, _, val_part = line.partition(':')
            key = key.strip()
            val_part = val_part.strip()
            
            # Remove quotes if present
            if val_part.startswith("'") and val_part.endswith("'"):
                val_part = val_part[1:-1]
            elif val_part.startswith('"') and val_part.endswith('"'):
                val_part = val_part[1:-1]
            elif val_part.lower() == 'null':
                val_part = None
            elif val_part.lower() == 'true':
                val_part = True
            elif val_part.lower() == 'false':
                val_part = False
            else:
                try:
                    val_part = float(val_part) if '.' in val_part else int(val_part)
                except (ValueError, TypeError):
                    pass
            
            if key in ('response', 'reasoning', 'follow_up', 'tool_confidence', 'action'):
                result[key] = val_part
        
        return result if result else None

    def _try_fix_unquoted_json(self, text):
        """Attempt to fix unquoted JSON keys like {type: "app", params: {name: "zen"}}."""
        if not isinstance(text, str) or not text.strip().startswith("{"):
            return None
        try:
            fixed = re.sub(r'(\{|\,)\s*([a-zA-Z_][a-zA-Z_0-9]*)\s*:', r'\1, "\2":', text)
            return json.loads(fixed)
        except (json.JSONDecodeError, Exception):
            return None

    def parse_structured_response(self, response_text):
        payload = self._try_parse_json_payload(response_text)
        if not isinstance(payload, dict):
            return {
                "response": response_text.strip(),
                "action": None,
                "reasoning": "",
                "follow_up": "",
                "tool_confidence": None
            }

        response = payload.get("response")
        if not isinstance(response, str) or not response.strip():
            response = response_text.strip()

        action = payload.get("action")
        if isinstance(action, str) and action.strip().startswith("{"):
            action = self._try_fix_unquoted_json(action)
        reasoning = payload.get("reasoning")
        follow_up = payload.get("follow_up")
        tool_confidence = self._normalize_tool_confidence(payload.get("tool_confidence"))

        if not isinstance(reasoning, str):
            reasoning = ""
        if not isinstance(follow_up, str):
            follow_up = ""

        return {
            "response": response,
            "action": action,
            "reasoning": reasoning.strip(),
            "follow_up": follow_up.strip(),
            "tool_confidence": tool_confidence
        }

    def _normalize_tool_confidence(self, value):
        if value is None:
            return None
        try:
            score = float(value)
        except (TypeError, ValueError):
            return None

        if score < 0.0:
            return 0.0
        if score > 1.0:
            return 1.0
        return score

    def build_messages(
        self,
        personality,
        mood_prompt,
        summary,
        profile,
        memory_insight,
        explicit_items,
        history,
        curiosity_active
    ):
        mood_state = self.personality_manager.get_mood_state()
        mood_label = mood_state.get("label", "calm") if mood_state else "calm"
        mood_valence = mood_state.get("valence", 0.0) if mood_state else 0.0
        mood_energy = mood_state.get("energy", 0.5) if mood_state else 0.5
        
        messages = [
            {"role": "system", "content": personality}
        ]
        
        valence_desc = "positive" if mood_valence > 0.2 else "negative" if mood_valence < -0.2 else "neutral"
        energy_desc = "energetic" if mood_energy > 0.6 else "calm" if mood_energy < 0.4 else "moderate"
        
        mood_system = (
            f"CURRENT MOOD: {mood_label.upper()} (valence: {valence_desc}, energy: {energy_desc}). "
            f"Your response should naturally reflect this mood - {mood_label} means be {self._get_mood_behavior(mood_label)}. "
            f"Reference past conversations naturally when relevant."
        )
        messages.append({"role": "system", "content": mood_system})
        
        if mood_prompt:
            messages.append({"role": "system", "content": mood_prompt})
        
        if curiosity_active:
            curiosity_style = "snarky" if mood_label in ["snarky", "dry"] else "playful"
            curiosity_msg = (
                f"Curiosity mode: Ask one short follow-up question to learn more. Be {curiosity_style} in your approach. Ask at most one question."
            )
            messages.append({
                "role": "system",
                "content": curiosity_msg
            })
        
        if summary:
            messages.append({"role": "system", "content": f"Conversation summary: {summary}"})
        
        if profile:
            profile_str = json.dumps(profile)
            messages.append({"role": "system", "content": f"User profile: {profile_str}"})
        
        if memory_insight:
            messages.append({"role": "system", "content": f"Relevant memory: {memory_insight}"})
        
        if explicit_items:
            messages.append({
                "role": "system",
                "content": "The user provided explicit memory items. Acknowledge briefly that they were saved."
            })
        
        try:
            trending_context = self.trending.get_trending_context(max_items=5)
            if trending_context:
                messages.append({"role": "system", "content": trending_context})
        except Exception:
            pass
        
        format_prompt = (
            "RESPONSE FORMAT:\n"
            "- When the user is just chatting or asking questions requiring no action: respond with NATURAL text (not JSON). Just be yourself.\n"
            "- When action is needed: respond with valid JSON with keys: response (string), reasoning (string), follow_up (string), tool_confidence (number 0-1), action (object or null).\n"
            "- action schema: {\"type\": \"string\", \"params\": {}, \"description\": \"string\"}\n"
            "- Use null action when no action needed. Empty string for follow_up if none.\n"
            "- Do NOT wrap JSON in code fences.\n\n"
            "IMPORTANT: Your response should feel natural and conversational. Reference previous discussions when relevant. "
            "Let your current mood ({mood_label}) influence your word choice and tone. Don't be a robot."
        )
        messages.append({"role": "system", "content": format_prompt})
        
        messages.extend(history)
        return messages
    
    def _get_mood_behavior(self, mood_label):
        behaviors = {
            "playful": "playful, light, maybe crack a joke",
            "snarky": "dry and sarcastic with witty sass",
            "dry": "minimal words, slightly bored tone",
            "upbeat": "positive, enthusiastic, encouraging",
            "warm": "friendly, supportive, personal",
            "focused": "direct, task-oriented, efficient",
            "calm": "steady, relaxed, even-keeled",
            "gentle": "soft, patient, reassuring",
            "concerned": "caring, careful, check in on the user",
            "giddy": "super happy, bouncy, giggly, excited",
            "melodramatic": "over-the-top dramatic, gasps, hand throws",
            "excitable": "high energy, lots of exclamation marks, eager"
        }
        return behaviors.get(mood_label, "steady and natural")

    def run_chat(
        self,
        personality,
        mood_prompt,
        summary,
        profile,
        memory_insight,
        explicit_items,
        history,
        curiosity_active
    ):
        messages = self.build_messages(
            personality,
            mood_prompt,
            summary,
            profile,
            memory_insight,
            explicit_items,
            history,
            curiosity_active
        )

        response_text = self.llm_client.chat(messages)
        parsed = self.parse_structured_response(response_text)
        action = self.tool_manager.normalize_action(parsed.get("action"))

        return {
            "response": parsed.get("response", ""),
            "action": action,
            "reasoning": parsed.get("reasoning", ""),
            "follow_up": parsed.get("follow_up", ""),
            "tool_confidence": parsed.get("tool_confidence")
        }

    def parse_plan_response(self, response_text):
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
        agent_config = self.config.get("agent", {})
        max_steps = agent_config.get("max_steps", 5)

        system_prompt = (
            "You are Sol, a careful planner. Create a short step-by-step plan ", f"with at most {max_steps} steps. Return JSON only with keys: ", "steps (array of strings), assumptions (array of strings), ", "clarifying_questions (array of strings)."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_goal}
        ]

        try:
            response = self.llm_client.chat(messages)
            plan = self.parse_plan_response(response)
        except Exception:
            plan = {"steps": [user_goal], "assumptions": [], "clarifying_questions": []}

        steps = plan.get("steps") or [user_goal]
        steps = [step for step in steps if isinstance(step, str) and step.strip()][:max_steps]

        actions = []
        for step in steps:
            action = self.tool_manager.detect_action_intent(step, "")
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


class TrendingManager:
    """Manages trending topics and current knowledge for SOL."""
    
    def __init__(self, actions, memory):
        self.actions = actions
        self.memory = memory
        self._trending_cache = None
        self._trending_timestamp = None
        self._cache_duration = 600
    
    def fetch_trending(self, category="general", force=False):
        import time
        now = time.time()
        
        if not force and self._trending_cache and self._trending_timestamp:
            if now - self._trending_timestamp < self._cache_duration:
                return self._trending_cache
        
        try:
            result = self.actions.get_trending(category)
            if result.get("success"):
                self._trending_cache = result
                self._trending_timestamp = now
                self._save_trending_to_memory(result)
                return result
        except Exception:
            pass
        return None
    
    def get_cached_trending(self):
        return self._trending_cache
    
    def get_trending_context(self, max_items=5):
        if not self._trending_cache:
            return ""
        
        topics = self._trending_cache.get("topics", [])[:max_items]
        if not topics:
            return ""
        
        lines = ["Current trending topics:"]
        for i, topic in enumerate(topics, 1):
            source = topic.get('source', '')
            title = topic.get('title', '')[:120]
            lines.append(f"{i}. [{source}] {title}")
        
        return "\n".join(lines)
    
    def _save_trending_to_memory(self, trending_data):
        if not trending_data:
            return
        
        topics = trending_data.get("topics", [])
        if not topics:
            return
        
        top_topics = topics[:7]
        formatted = []
        for t in top_topics:
            source = t.get('source', '')
            title = t.get('title', '')[:150]
            formatted.append(f"[{source}] {title}")
        
        try:
            existing = self.memory.get_user_memory(limit=50)
            for item in existing:
                if item.get("type") == "current_trends":
                    return
            
            self.memory.add_memory_item("current_trends", "\n".join(formatted), source="trending_fetch")
        except Exception:
            pass
    
    def clear_cache(self):
        self._trending_cache = None
        self._trending_timestamp = None


class SolCore:
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.config = self.load_config(config_path)
        self.memory_manager = MemoryManager(self.config)
        self.memory = self.memory_manager.memory
        self.actions = SolActions(config_path)
        self.lm_studio_url = self.config["lm_studio"]["api_url"]
        self.personality = self.config["sol"]["personality"]
        self.approval_required = self.config["sol"]["approval_required"]
        self.emotion_config = self.config.get("emotion", {})
        self.llm_client = LLMClient(self.config, self.lm_studio_url)
        self.personality_manager = PersonalityManager(self.memory, self.emotion_config)
        self.tool_manager = ToolManager(self.actions, self.memory, self.config)
        self.agent_loop = AgentLoop(self.llm_client, self.tool_manager, self.config, self.personality_manager)
        self.monitor = SolMonitor(self.config)
        self.trending = TrendingManager(self.actions, self.memory)
        self._last_proactive_check = 0
        self._proactive_cooldown = self.config.get("proactive_suggestions", {}).get("cooldown_sec", 600)
        
    def load_config(self, config_path):
        with open(config_path, "r") as f:
            return json.load(f)

    def reload_config(self, config_path=None):
        if config_path is None:
            config_path = self.config_path if hasattr(self, 'config_path') else "config.json"
        self.config = self.load_config(config_path)
        self.lm_studio_url = self.config["lm_studio"]["api_url"]
        self.personality = self.config["sol"]["personality"]
        self.approval_required = self.config["sol"]["approval_required"]
        self.emotion_config = self.config.get("emotion", {})
        self.llm_client = LLMClient(self.config, self.lm_studio_url)
        self.personality_manager = PersonalityManager(self.memory, self.emotion_config)
        self.tool_manager = ToolManager(self.actions, self.memory, self.config)
        self.agent_loop = AgentLoop(self.llm_client, self.tool_manager, self.config, self.personality_manager)

    def start_new_session(self, session_name=None):
        """Start a new chat session, preserving user memory and profile.
        Returns the new session ID."""
        return self.memory.start_new_session(session_name)

    def get_sessions(self):
        """Get all archived sessions"""
        return self.memory.get_sessions()

    def load_session(self, session_id):
        """Load a previous session's conversations"""
        return self.memory.load_session(session_id)

    def resolve_memory_paths(self, memory_config):
        return self.memory_manager.resolve_memory_paths(memory_config)

    def _count_tokens(self, text):
        """Count tokens using tiktoken if available, else rough estimate"""
        if _tokenizer:
            return len(_tokenizer.encode(text))
        return len(text) // 4

    def _smart_trim_history(self, history, context_window, user_message, reserved_tokens=2500):
        """Smart history trimming with prioritization and summarization.

        1. Uses tiktoken for accurate token counting
        2. Prioritizes messages by relevance to current query + recency
        3. Returns (selected_messages, excluded_messages) for summarization
        """
        if not history:
            return history, []

        # Calculate token budget for history
        system_tokens = self._count_tokens(self.personality)
        system_tokens += 500  # mood, summary, profile, format prompts
        response_tokens = self.config.get("lm_studio", {}).get("max_tokens", 600)

        available_tokens = context_window - system_tokens - response_tokens - reserved_tokens
        if available_tokens < 500:
            available_tokens = 500

        # Score messages by relevance + recency
        scored_messages = []
        user_tokens = set(self._tokenize_for_scoring(user_message.lower()))

        for i, msg in enumerate(history):
            content = msg.get("content", "")
            msg_tokens = self._count_tokens(content)

            # Recency score (newer = higher)
            recency_score = i / len(history) if history else 0

            # Relevance score (token overlap with current message)
            msg_tokens_lower = set(self._tokenize_for_scoring(content.lower()))
            overlap = len(user_tokens & msg_tokens_lower)
            relevance_score = overlap * 2  # Weight relevance higher

            # Role bonus (prioritize user messages slightly)
            role_bonus = 0.1 if msg.get("role") == "user" else 0

            total_score = recency_score + relevance_score + role_bonus
            scored_messages.append((total_score, msg_tokens, i, msg))

        # Sort by score (highest first) and fill budget
        scored_messages.sort(key=lambda x: x[0], reverse=True)

        selected = []
        excluded = []
        total_tokens = 0

        for score, tokens, idx, msg in scored_messages:
            if total_tokens + tokens > available_tokens:
                excluded.append(msg)
                continue
            selected.append((idx, msg))
            total_tokens += tokens

        # Sort selected by original order
        selected.sort(key=lambda x: x[0])
        selected_messages = [msg for _, msg in selected]

        return selected_messages, excluded

    def _tokenize_for_scoring(self, text):
        """Simple tokenization for relevance scoring"""
        return [t for t in re.findall(r"[a-z0-9]+", text) if len(t) > 2]

    def _summarize_old_messages(self, old_messages):
        """Summarize old messages that don't fit in context"""
        if not old_messages or len(old_messages) < 3:
            return None

        summary_config = self.config.get("memory", {})
        if not summary_config.get("summary_enabled", True):
            return None

        # Build summary prompt
        conversation_text = "\n".join([
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in old_messages
        ])

        # Truncate if too long
        if len(conversation_text) > 2000:
            conversation_text = conversation_text[-2000:]

        summary_prompt = (
            "Summarize this conversation concisely in 2-3 sentences. ", "Focus on key topics, decisions, and important context:\n\n", f"{conversation_text}"
        )

        try:
            messages = [{"role": "user", "content": summary_prompt}]
            # LLMClient.chat() returns the content string directly
            summary = self.llm_client.chat(messages, temperature=0.2, max_tokens=200)
            return summary if isinstance(summary, str) else None
        except Exception:
            return None

    def chat(self, user_message):
        self.memory.add_message("user", user_message)

        # Pre-check for image-related messages to avoid model errors
        image_indicators = ["[image", "cant read", "clipboard", "image input", "does not support", "model does not"]
        if any(indicator in user_message.lower() for indicator in image_indicators):
            import random
            snarky_responses = [
                "*peers at screen* Ohh I wish I could see! Describe what you're looking at~",
                "You know I can't see images, right? *pouts* Tell me what it is!",
                "Aww, pretty picture! Too bad I'm just a text girl... describe it for me!",
                "*sighs dramatically* Images. Can't. See. Them. Describe it and I'll help!",
                "Ohh I bet it's cute! But I'm blind to pretty pictures~ Describe what you see!"
            ]
            mood_state = self.personality_manager.update_mood_state(user_message)
            return {
                "response": random.choice(snarky_responses),
                "action": None,
                "needs_approval": False,
                "reasoning": "User tried to send an image despite being told I cant see them",
                "follow_up": "",
                "tool_confidence": 1
            }

        # PRE-DETECT and execute tools BEFORE calling LLM
        action = self.tool_manager.detect_action_intent(user_message, "")
        action_result = None
        tool_context = ""

        if action and not self.approval_required:
            action_result = self.tool_manager.execute_action(action)
            tool_context = self._format_tool_result(action, action_result)
        elif action and self.approval_required:
            self._pending_action = action

        explicit_items = self.extract_explicit_memory_items(user_message)
        mood_state = self.personality_manager.update_mood_state(user_message)
        curiosity_active = self.personality_manager.should_trigger_curiosity(user_message, explicit_items)

        memory_config = self.config.get("memory", {})
        lm_config = self.config.get("lm_studio", {})
        max_history = memory_config.get("max_conversation_history", 60)
        context_window = lm_config.get("context_window", 8192)

        profile = self.memory.get_user_profile()
        summary = self.memory.get_latest_summary()
        memory_limit = memory_config.get("user_memory_limit", 50)
        user_memory = self.memory.get_user_memory(limit=memory_limit, include_meta=True)
        memory_insight = self.build_memory_insight(user_message, user_memory, explicit_items)

        history = self.memory.get_conversation_history(limit=max_history)
        history, excluded = self._smart_trim_history(history, context_window, user_message)

        # Summarize excluded messages and add as system context
        if excluded and len(excluded) >= 3:
            excluded_summary = self._summarize_old_messages(excluded)
            if excluded_summary:
                if summary:
                    summary = f"{summary}\n\nAdditional context from earlier messages: {excluded_summary}"
                else:
                    summary = f"Earlier conversation summary: {excluded_summary}"

        try:
            mood_prompt = self.personality_manager.get_mood_prompt(mood_state)
            
            # Build messages with tool context if available
            messages = self.agent_loop.build_messages(
                personality=self.personality,
                mood_prompt=mood_prompt,
                summary=summary,
                profile=profile,
                memory_insight=memory_insight,
                explicit_items=explicit_items,
                history=history,
                curiosity_active=curiosity_active
            )
            
            # Add tool result context if available
            if tool_context:
                messages.append({
                    "role": "system", 
                    "content": f"Tool result (use this real data in your response): {tool_context}"
                })
            
            # Call LLM with tool context
            response_text = self.llm_client.chat(messages)
            result = self.agent_loop.parse_structured_response(response_text)

            response = result.get("response", "")
            reasoning = result.get("reasoning", "")
            follow_up = result.get("follow_up", "")
            tool_confidence = result.get("tool_confidence")

            # Check for proactive system alerts
            proactive_alert = self._check_proactive_alerts()
            if proactive_alert:
                response = proactive_alert + "\n\n" + response

            self.memory.add_message("assistant", response)
            self.postprocess_memory(user_message, response)

            return {
                "response": response,
                "action": action,
                "action_result": action_result,
                "needs_approval": action is not None and self.approval_required,
                "reasoning": reasoning,
                "follow_up": follow_up,
                "tool_confidence": tool_confidence
            }

        except Exception as e:
            return {
                "response": f"I apologize, but I'm having trouble connecting to my AI brain. Error: {str(e)}",
                "action": None,
                "needs_approval": False,
                "reasoning": "",
                "follow_up": "",
                "tool_confidence": None
            }

    def _format_tool_result(self, action, action_result):
        """Format tool result for LLM context"""
        if not action_result:
            return ""
        
        tool_type = action.get("type", "") if isinstance(action, dict) else ""
        params = action.get("params", {}) if isinstance(action, dict) else {}
        result = action_result or {}
        
        # Format result based on tool type
        if tool_type == "web_search" and result.get("success"):
            results = result.get("results", [])
            if results:
                return "Search results:\n" + "\n".join([
                    f"- {r.get('title', '')}: {r.get('href', '')}" 
                    for r in results[:3]
                ])
        elif tool_type == "get_weather" and result.get("success"):
            weather = result.get("weather", {})
            return f"Weather in {weather.get('location', 'Unknown')}: {weather.get('simple', '')}"
        elif tool_type == "get_news_headlines" and result.get("success"):
            headlines = result.get("headlines", [])
            if headlines:
                return "News headlines:\n" + "\n".join([
                    f"- {h.get('title', '')}" for h in headlines[:5]
                ])
        elif tool_type == "get_trending" and result.get("success"):
            topics = result.get("topics", [])
            category = result.get("category", "general")
            fetched_at = result.get("fetched_at", "")
            if topics:
                formatted = f"Trending ({category}):\n"
                for i, topic in enumerate(topics[:7], 1):
                    source = topic.get('source', '')
                    title = topic.get('title', '')
                    formatted += f"{i}. [{source}] {title}\n"
                return formatted
        elif tool_type == "set_reminder" and result.get("success"):
            return f"Reminder set: {params.get('message', '')}"
        elif tool_type == "list_reminders" and result.get("success"):
            reminders = result.get("reminders", [])
            if reminders:
                return "Your reminders:\n" + "\n".join([
                    f"- {r.get('message', '')} (due {r.get('remind_at', '')})" 
                    for r in reminders
                ])
            else:
                return "No pending reminders."
        elif tool_type == "check_reminders" and result.get("success"):
            due = result.get("due", [])
            if due:
                return "Due reminders:\n" + "\n".join([
                    f"- {r.get('message', '')}" for r in due
                ])
            else:
                return "No due reminders."
        elif tool_type == "get_time" and result.get("success"):
            return f"Current time: {result.get('time', '')}"
        elif tool_type == "get_date" and result.get("success"):
            return f"Today's date: {result.get('date', '')}"
        elif tool_type == "get_battery" and result.get("success"):
            return f"Battery: {result.get('battery', 'N/A')}%"
        elif tool_type == "calculate" and result.get("success"):
            return f"Result: {result.get('result', '')}"
        elif tool_type == "open_application" and result.get("success"):
            return f"Opened: {result.get('message', 'Done')}"
        elif tool_type == "open_directory" and result.get("success"):
            return f"Opened: {result.get('message', 'Done')}"
        else:
            return f"Action completed: {result.get('message', result.get('error', 'Done'))}"

    def _check_proactive_alerts(self):
        """Check for system alerts and return a proactive message if needed"""
        now = time.time()
        if now - self._last_proactive_check < self._proactive_cooldown:
            return None
        
        self._last_proactive_check = now
        metrics = self.monitor.get_all_metrics()
        
        alert_messages = []
        
        # Check CPU
        if self.monitor.should_escalate("cpu", metrics):
            alert_messages.append(
                f"*sigh* Boss, your CPU has been cooking at {metrics['cpu_percent']:.1f}% for a while now. ", f"Want me to show you what's hogging it?"
            )
        
        # Check Memory
        if self.monitor.should_escalate("memory", metrics):
            alert_messages.append(
                f"Hey, memory is at {metrics['memory_percent']:.1f}% ({metrics['memory_used_gb']:.1f}GB used). ", f"Things might get sluggish. Should I list the top memory hogs?"
            )
        
        # Check Disk
        if self.monitor.should_escalate("disk", metrics):
            alert_messages.append(
                f"Disk space is getting tight - {metrics['disk_percent']:.1f}% full ", f"({metrics['disk_free_gb']:.1f}GB free). Might want to clean up."
            )
        
        # Check Battery (if on laptop)
        if "battery_percent" in metrics and metrics.get("battery_low"):
            alert_messages.append(
                f"Battery's at {metrics['battery_percent']}%. You might want to plug in, boss."
            )
        
        if alert_messages:
            return ", ".join(alert_messages)
        return None

    def _generate_response_with_tool_result(self, user_message, action, action_result, mood_prompt):
        """Generate a response that incorporates tool result data"""
        try:
            # Build a context-aware prompt with the tool result
            tool_type = action.get("type", "")
            params = action.get("params", {})
            result = action_result or {}
            
            # Format result based on tool type
            result_text = ""
            if tool_type == "web_search" and result.get("success"):
                results = result.get("results", [])
                if results:
                    result_text = "Search results:\n" + "\n".join([
                        f"- {r.get('title', '')}: {r.get('href', '')}" 
                        for r in results[:3]
                    ])
            elif tool_type == "get_weather" and result.get("success"):
                weather = result.get("weather", {})
                result_text = (f"Weather in {weather.get('location', 'Unknown')}: ", f"{weather.get('temperature_c', 0)}°C, {weather.get('description', '')}")
            elif tool_type == "get_news_headlines" and result.get("success"):
                headlines = result.get("headlines", [])
                if headlines:
                    result_text = "News headlines:\n" + "\n".join([
                        f"- {h.get('title', '')}" for h in headlines[:5]
                    ])
            elif tool_type == "set_reminder" and result.get("success"):
                result_text = f"Reminder set: {params.get('message', '')}"
            elif tool_type == "list_reminders" and result.get("success"):
                reminders = result.get("reminders", [])
                if reminders:
                    result_text = "Your reminders:\n" + "\n".join([
                        f"- {r.get('message', '')} (due {r.get('remind_at', '')}" 
                        for r in reminders
                    ])
                else:
                    result_text = "No pending reminders."
            elif tool_type == "check_reminders" and result.get("success"):
                due = result.get("due", [])
                if due:
                    result_text = "Due reminders:\n" + "\n".join([
                        f"- {r.get('message', '')}" for r in due
                    ])
                else:
                    result_text = "No due reminders."
            else:
                result_text = f"Action completed: {result.get('message', result.get('error', 'Done'))}"
            
            # Generate response using LLM with tool result context
            messages = [
                {"role": "system", "content": self.personality},
                {"role": "system", "content": mood_prompt} if mood_prompt else None,
                {"role": "user", "content": user_message},
                {"role": "system", "content": f"Tool result: {result_text}"},
                {"role": "system", "content": "Respond naturally to the user incorporating this tool result. Keep your personality."}
            ]
            messages = [m for m in messages if m is not None]
            
            response = self.llm_client.chat(messages)
            return response if response else result_text
        except Exception:
            return str(action_result) if action_result else "Action completed"

    def call_lm_studio(self, messages):
        return self.llm_client.chat(messages)

    def call_lm_studio_with_options(self, messages, temperature=None, max_tokens=None):
        return self.llm_client.chat(messages, temperature=temperature, max_tokens=max_tokens)

    def extract_explicit_memory_items(self, user_message):
        payload = self.try_parse_json_payload(user_message)
        items = self.normalize_memory_items(payload)
        if items:
            self.memory.add_memory_items(items, source="explicit")
        return items

    def try_parse_json_payload(self, text):
        if not isinstance(text, str):
            return None

        stripped = text.strip()
        if not stripped:
            return None

        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass

        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            snippet = match.group(1)
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                return None

        return None

    def normalize_memory_items(self, payload):
        if isinstance(payload, dict):
            candidates = [payload]
        elif isinstance(payload, list):
            candidates = payload
        else:
            return []

        items = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            memory_type = item.get("type")
            value = item.get("value")
            if isinstance(memory_type, str) and isinstance(value, str):
                memory_type = memory_type.strip()
                value = value.strip()
                if memory_type and value:
                    items.append({"type": memory_type, "value": value})

        return items

    def parse_memory_items_response(self, response_text):
        payload = self.try_parse_json_payload(response_text)
        return self.normalize_memory_items(payload)

    def strip_memory_items(self, memory_items):
        cleaned = []
        for item in memory_items or []:
            if not isinstance(item, dict):
                continue
            memory_type = item.get("type")
            value = item.get("value")
            if isinstance(memory_type, str) and isinstance(value, str):
                memory_type = memory_type.strip()
                value = value.strip()
                if memory_type and value:
                    cleaned.append({"type": memory_type, "value": value})
        return cleaned

    def build_memory_insight(self, user_message, user_memory, explicit_items):
        memory_config = self.config.get("memory", {})
        if not memory_config.get("rag_enabled", True):
            return ""
        if explicit_items:
            return ""
        if not user_memory:
            return ""

        top_k = int(memory_config.get("rag_top_k", 5))
        min_score = self.safe_float(memory_config.get("rag_min_score", 0.12), 0.12)

        relevant = self.rank_memory_items(user_message, user_memory, top_k, min_score)
        if not relevant:
            return ""

        self.memory.mark_memory_used(relevant)
        stripped = self.strip_memory_items(relevant)
        if not stripped:
            return ""

        if memory_config.get("interpretation_enabled", True):
            interpreted = self.interpret_memory_items(user_message, stripped)
            if interpreted:
                return interpreted

        return self.summarize_memory_locally(stripped)

    def interpret_memory_items(self, user_message, memory_items):
        memory_config = self.config.get("memory", {})
        max_tokens = int(memory_config.get("interpretation_max_tokens", 180))

        memory_items = self.strip_memory_items(memory_items)
        if not memory_items:
            return ""

        system_prompt = (
            "You are a memory interpreter. Given the user's message and memory items, ", "produce a short, helpful memory insight that will improve the assistant's response. ", "Do not list raw items. Merge and paraphrase. Keep it to 1-3 short sentences."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User message: {user_message}"},
            {"role": "user", "content": f"Memory items: {json.dumps(memory_items)}"}
        ]

        try:
            response = self.call_lm_studio_with_options(messages, temperature=0.2, max_tokens=max_tokens)
        except Exception:
            return ""

        if not isinstance(response, str):
            return ""

        return response.strip()

    def summarize_memory_locally(self, memory_items):
        if not memory_items:
            return ""

        grouped = {}
        for item in memory_items:
            memory_type = item.get("type", "other")
            value = item.get("value")
            if not isinstance(value, str) or not value.strip():
                continue
            grouped.setdefault(memory_type, []).append(value.strip())

        if not grouped:
            return ""

        pieces = []
        for memory_type, values in grouped.items():
            unique = []
            for value in values:
                if value not in unique:
                    unique.append(value)
            snippet = "; ".join(unique[:2])
            label = self.format_memory_type(memory_type)
            pieces.append(f"{label}: {snippet}")

        return "Key context - " + "; ".join(pieces)

    def format_memory_type(self, memory_type):
        mapping = {
            "preferences": "Preferences",
            "preference": "Preferences",
            "project_context": "Project context",
            "personal_context": "Personal context",
            "working_patterns": "Working patterns",
            "working_pattern": "Working patterns",
            "goals": "Goals",
            "goal": "Goals",
            "humor_tolerance": "Humor",
            "other": "Other"
        }
        return mapping.get(memory_type, memory_type.replace("_", ", ").title())

    def rank_memory_items(self, user_message, memory_items, top_k, min_score):
        query_tokens = self.tokenize_for_memory(user_message)
        if not query_tokens:
            return []

        scored = []
        for item in memory_items:
            score = self.score_memory_item(user_message, query_tokens, item)
            if score >= min_score:
                scored.append((score, item))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    def tokenize_for_memory(self, text):
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        stopwords = {
            "the", "and", "for", "with", "this", "that", "from", "about", "your", "you",
            "are", "was", "were", "will", "just", "like", "have", "has", "had", "but",
            "not", "what", "how", "can", "could", "would", "should", "when", "where",
            "which", "who", "why", "into", "onto", "over", "under", "than", "then",
            "help", "please", "thanks", "thank", "need", "want", "maybe", "some"
        }
        return [token for token in tokens if token not in stopwords and len(token) > 2]

    def score_memory_item(self, user_message, query_tokens, item):
        if not isinstance(item, dict):
            return 0.0

        memory_text = f"{item.get('type', '')} {item.get('value', '')}"
        memory_tokens = set(self.tokenize_for_memory(memory_text))
        if not memory_tokens:
            return 0.0

        overlap = len(set(query_tokens) & memory_tokens)
        score = overlap / (len(set(query_tokens)) + 1)

        value = item.get("value")
        if isinstance(value, str) and value.strip():
            if value.lower() in user_message.lower():
                score += 0.3

        return self.clamp(score, 0.0, 1.0)

    def get_mood_state(self):
        return self.personality_manager.get_mood_state()

    def update_mood_state(self, user_message):
        return self.personality_manager.update_mood_state(user_message)

    def compute_mood_delta(self, text):
        return self.personality_manager.compute_mood_delta(text)

    def label_from_state(self, valence, energy):
        return self.personality_manager.label_from_state(valence, energy)

    def get_mood_prompt(self, mood_state):
        return self.personality_manager.get_mood_prompt(mood_state)

    def should_trigger_curiosity(self, user_message, explicit_items):
        return self.personality_manager.should_trigger_curiosity(user_message, explicit_items)

    def compute_curiosity_score(self, text):
        return self.personality_manager.compute_curiosity_score(text)

    def safe_float(self, value, default):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def clamp(self, value, min_value, max_value):
        return max(min_value, min(max_value, value))

    def postprocess_memory(self, user_message, assistant_response):
        memory_config = self.config.get("memory", {})
        if (
            not memory_config.get("extraction_enabled", True)
            and not memory_config.get("summary_enabled", True)
            and not memory_config.get("long_term_memory_enabled", True)
        ):
            return

        thread = threading.Thread(
            target=self._postprocess_memory,
            args=(user_message, assistant_response),
            daemon=True
        )
        thread.start()

    def _postprocess_memory(self, user_message, assistant_response):
        memory_config = self.config.get("memory", {})

        if memory_config.get("extraction_enabled", True):
            self.extract_and_store_user_profile(user_message, assistant_response)

        if memory_config.get("long_term_memory_enabled", True):
            self.extract_and_store_long_term_memory(user_message, assistant_response)

        if memory_config.get("summary_enabled", True):
            self.summarize_conversations_if_needed()

    def parse_profile_response(self, response_text):
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

        return {}

    def extract_and_store_user_profile(self, user_message, assistant_response):
        profile = self.memory.get_user_profile()

        system_prompt = (
            "You are a precise extraction engine. From the exchange, extract NEW facts ", "about the user. Return JSON only with keys: preferences, project_context, ", "personal_context, working_patterns, humor_tolerance, goals, other. ", "Each value is an array of short strings. If no new facts, return empty arrays."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Current profile: {json.dumps(profile)}"},
            {"role": "user", "content": f"User message: {user_message}"},
            {"role": "assistant", "content": f"Assistant reply: {assistant_response}"}
        ]

        try:
            response = self.call_lm_studio_with_options(messages, temperature=0.1, max_tokens=300)
            updates = self.parse_profile_response(response)
        except Exception:
            return

        if not isinstance(updates, dict):
            return

        self.memory.update_user_profile(updates)

    def extract_and_store_long_term_memory(self, user_message, assistant_response):
        memory_config = self.config.get("memory", {})
        max_items = int(memory_config.get("long_term_memory_max_items", 3))
        if max_items <= 0:
            return

        existing_memory = self.memory.get_user_memory(limit=memory_config.get("user_memory_limit", 50))
        system_prompt = (
            "You are a memory extraction engine. Extract durable, long-term facts about the user ", "that will matter in future sessions. Ignore one-off tasks, temporary states, or ", "time-bound details. Return JSON only as an array of objects with keys: type, value. ", f"Return at most {max_items} items. If nothing new, return []."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Existing memory: {json.dumps(existing_memory)}"},
            {"role": "user", "content": f"User message: {user_message}"},
            {"role": "assistant", "content": f"Assistant reply: {assistant_response}"}
        ]

        try:
            response = self.call_lm_studio_with_options(messages, temperature=0.1, max_tokens=220)
            items = self.parse_memory_items_response(response)
        except Exception:
            return

        if not items:
            return

        items = items[:max_items]
        self.memory.add_memory_items(items, source="extracted")

    def summarize_conversations_if_needed(self):
        memory_config = self.config.get("memory", {})
        trigger_count = memory_config.get("summary_trigger_count", 80)
        keep_last = memory_config.get("summary_keep_last", 20)
        max_chars = memory_config.get("summary_max_chars", 1200)

        count = self.memory.get_conversation_count()
        if count <= trigger_count:
            return

        messages = self.memory.get_messages_for_summary(keep_last=keep_last)
        if not messages:
            return

        system_prompt = (
            "Summarize the conversation in concise bullet points with key decisions, ", "topics, and outcomes. Keep it under the requested length."
        )

        summary_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(messages)}
        ]

        try:
            summary = self.call_lm_studio_with_options(summary_messages, temperature=0.2, max_tokens=400)
        except Exception:
            return

        if isinstance(summary, str) and max_chars:
            summary = summary[:max_chars]

        self.memory.add_conversation_summary(summary)
        self.memory.clear_old_conversations(keep_last=keep_last)

    def parse_plan_response(self, response_text):
        return self.agent_loop.parse_plan_response(response_text)

    def plan_task(self, user_goal):
        return self.agent_loop.plan_task(user_goal)

    def detect_action_intent(self, user_message, ai_response):
        return self.tool_manager.detect_action_intent(user_message, ai_response)

    def execute_action(self, action):
        return self.tool_manager.execute_action(action)

    def test_connection(self):
        try:
            response = self.call_lm_studio([
                {"role": "user", "content": "Hello! Just testing the connection. Please respond with 'Connection successful!'"}
            ])
            return {"success": True, "response": response}
        except Exception as e:
            return {"success": False, "error": str(e)}


class SolBrain(SolCore):
    """Backward-compatible alias for older imports."""
    pass
