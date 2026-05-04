"""
Sol Core - AI Brain
Connects LM Studio, memory, and PC actions with safety layer
"""

import json
import re
import threading
import shutil
from pathlib import Path

import requests

from sol_memory import SolMemory
from sol_actions import SolActions


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
        return "calm"

    def get_mood_prompt(self, mood_state):
        if not mood_state:
            return ""
        
        label = mood_state.get("label", "calm")
        tone_map = {
            "playful": "Light, whimsical, and a bit cheeky. Maybe crack a gentle joke or use playful language.",
            "snarky": "Dry and sarcastic. Make a witty comment about the situation if appropriate, but never mean.",
            "dry": "Minimal words. Slightly bored tone. Use '*sigh*' or '*eye roll*' if it fits.",
            "upbeat": "Positive and encouraging. Lightly higher energy. Show genuine enthusiasm.",
            "warm": "Friendly and companion-like. Add small supportive touches and personal connections.",
            "focused": "Direct and task-first. Reduce small talk. Get to the point quickly.",
            "calm": "Steady and relaxed. Keep responses even and clear. No need to rush.",
            "gentle": "Soft, reassuring, and patient. Be extra supportive if the user seems unsure.",
            "concerned": "Supportive and careful. Check in once if the user seems stressed. Be grounding."
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

        return None

    def _describe_action(self, action_type, params):
        if action_type in ["open_file", "create_file"]:
            name = Path(str(params.get("filepath", ""))).name
            if name:
                return f"{action_type.replace('_', ' ').title()}: {name}"

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

        if action_type == "list_directory":
            directory = str(params.get("directory", "")).strip()
            if directory:
                return f"List files: {directory}"

        return action_type.replace("_", " ").title()

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
            fixed = re.sub(r'(\{|\,)\s*([a-zA-Z_][a-zA-Z_0-9]*)\s*:', r'\1 "\2":', text)
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
        
        messages = [
            {"role": "system", "content": personality}
        ]
        
        if mood_prompt:
            messages.append({"role": "system", "content": mood_prompt})
        
        if curiosity_active:
            curiosity_style = "snarky" if mood_label in ["snarky", "dry"] else "gentle"
            curiosity_msg = (
                f"Curiosity mode: Ask one short follow-up question to learn more. "
                f"Be {curiosity_style} in your approach. Ask at most one question."
            )
            messages.append({
                "role": "system",
                "content": curiosity_msg
            })
        
        if summary:
            messages.append({"role": "system", "content": f"Conversation summary: {summary}"})
        
        if profile:
            messages.append({"role": "system", "content": f"User profile: {json.dumps(profile)}"})
        
        if memory_insight:
            messages.append({"role": "system", "content": f"Relevant memory insight: {memory_insight}"})
        
        if explicit_items:
            messages.append({
                "role": "system",
                "content": "The user provided explicit memory items. Acknowledge briefly that they were saved."
            })
        
        format_prompt = (
            "You MUST respond with valid JSON only. Use double-quoted keys and values. "
            "Required keys: response (string), reasoning (string), follow_up (string), "
            "tool_confidence (number 0-1), action (object or null). "
            "The action schema is {\"type\": \"string\", \"params\": {}, \"description\": \"string\"}. "
            "Use null when no action is needed. If no follow-up question, use an empty string. "
            "Do not wrap JSON in code fences. Do not include any text outside the JSON object.\n\n"
            "IMPORTANT: Your response field should reflect your personality. Be natural, use contractions, "
            "and let your mood influence your word choice. Don't be a robot - be Sol."
        )
        messages.append({"role": "system", "content": format_prompt})
        
        messages.extend(history)
        return messages

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
            "You are Sol, a careful planner. Create a short step-by-step plan "
            f"with at most {max_steps} steps. Return JSON only with keys: "
            "steps (array of strings), assumptions (array of strings), "
            "clarifying_questions (array of strings)."
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
        
    def resolve_memory_paths(self, memory_config):
        return self.memory_manager.resolve_memory_paths(memory_config)

    def chat(self, user_message):
        self.memory.add_message("user", user_message)

        # Pre-check for image-related messages to avoid model errors
        image_indicators = ["[image", "cannot read", "clipboard", "image input", "does not support", "model does not"]
        if any(indicator in user_message.lower() for indicator in image_indicators):
            import random
            snarky_responses = [
                "Boss, I literally can't see images. We've been over this. Describe it with words.",
                "*sigh* Still text-only, remember? What's in the image?",
                "Really? I.can't.see.images. The first rule of Sol, boss.",
                "Boss, are you testing my patience? I.can't.see.images. Use words."
            ]
            mood_state = self.personality_manager.update_mood_state(user_message)
            return {
                "response": random.choice(snarky_responses),
                "action": None,
                "needs_approval": False,
                "reasoning": "User tried to send an image despite being told I can't see them",
                "follow_up": "",
                "tool_confidence": 1
            }

        explicit_items = self.extract_explicit_memory_items(user_message)
        mood_state = self.personality_manager.update_mood_state(user_message)
        curiosity_active = self.personality_manager.should_trigger_curiosity(user_message, explicit_items)

        history = self.memory.get_conversation_history(limit=10)

        profile = self.memory.get_user_profile()
        summary = self.memory.get_latest_summary()
        memory_config = self.config.get("memory", {})
        memory_limit = memory_config.get("user_memory_limit", 50)
        user_memory = self.memory.get_user_memory(limit=memory_limit, include_meta=True)
        memory_insight = self.build_memory_insight(user_message, user_memory, explicit_items)

        try:
            mood_prompt = self.personality_manager.get_mood_prompt(mood_state)
            result = self.agent_loop.run_chat(
                personality=self.personality,
                mood_prompt=mood_prompt,
                summary=summary,
                profile=profile,
                memory_insight=memory_insight,
                explicit_items=explicit_items,
                history=history,
                curiosity_active=curiosity_active
            )

            response = result.get("response", "")
            action = result.get("action")
            reasoning = result.get("reasoning", "")
            follow_up = result.get("follow_up", "")
            tool_confidence = result.get("tool_confidence")

            if not action:
                action = self.detect_action_intent(user_message, response)

            self.memory.add_message("assistant", response)

            self.postprocess_memory(user_message, response)

            return {
                "response": response,
                "action": action,
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
            "You are a memory interpreter. Given the user's message and memory items, "
            "produce a short, helpful memory insight that will improve the assistant's response. "
            "Do not list raw items. Merge and paraphrase. Keep it to 1-3 short sentences."
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
        return mapping.get(memory_type, memory_type.replace("_", " ").title())

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
            "You are a precise extraction engine. From the exchange, extract NEW facts "
            "about the user. Return JSON only with keys: preferences, project_context, "
            "personal_context, working_patterns, humor_tolerance, goals, other. "
            "Each value is an array of short strings. If no new facts, return empty arrays."
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
            "You are a memory extraction engine. Extract durable, long-term facts about the user "
            "that will matter in future sessions. Ignore one-off tasks, temporary states, or "
            "time-bound details. Return JSON only as an array of objects with keys: type, value. "
            f"Return at most {max_items} items. If nothing new, return []."
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
            "Summarize the conversation in concise bullet points with key decisions, "
            "topics, and outcomes. Keep it under the requested length."
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
