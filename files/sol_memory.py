"""
Sol Memory System
JSON-backed storage for conversation history, user profile, and memory.
"""

import json
import threading
from datetime import datetime
from pathlib import Path


class SolMemory:
    def __init__(self, storage_path="sol_memory.json", legacy_db_path=None):
        self.storage_path = Path(storage_path)
        self.legacy_db_path = Path(legacy_db_path) if legacy_db_path else None
        self._lock = threading.RLock()
        self._store = self._load_or_initialize()

    def _now(self):
        return datetime.now().isoformat()

    def _default_store(self):
        now = self._now()
        return {
            "version": 1,
            "created_at": now,
            "updated_at": now,
            "preferences": {},
            "conversations": [],
            "user_memory": [],
            "action_log": [],
            "sessions": [],
            "next_ids": {
                "conversation": 1,
                "user_memory": 1,
                "action_log": 1
            }
        }

    def _load_or_initialize(self):
        if self.storage_path.exists():
            return self._load_store()

        store = None
        if self.legacy_db_path and self.legacy_db_path.is_file():
            store = self._migrate_from_sqlite(self.legacy_db_path)

        if not store:
            store = self._default_store()

        self._write_store(store)
        return store

    def _load_store(self):
        try:
            with self.storage_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            data = self._default_store()
        return self._normalize_store(data)

    def _normalize_store(self, data):
        if not isinstance(data, dict):
            data = self._default_store()

        data.setdefault("version", 1)
        data.setdefault("created_at", self._now())
        data.setdefault("updated_at", self._now())
        data.setdefault("preferences", {})
        data.setdefault("conversations", [])
        data.setdefault("user_memory", [])
        data.setdefault("action_log", [])
        data.setdefault("next_ids", {})

        next_ids = data.get("next_ids", {})
        next_ids.setdefault("conversation", self._infer_next_id(data.get("conversations", [])))
        next_ids.setdefault("user_memory", self._infer_next_id(data.get("user_memory", [])))
        next_ids.setdefault("action_log", self._infer_next_id(data.get("action_log", [])))
        data["next_ids"] = next_ids
        return data

    def _infer_next_id(self, items):
        max_id = 0
        for item in items:
            if isinstance(item, dict):
                try:
                    max_id = max(max_id, int(item.get("id", 0)))
                except (TypeError, ValueError):
                    pass
        return max_id + 1 if max_id > 0 else 1

    def _write_store(self, data):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.storage_path.with_name(self.storage_path.name + ".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=True, indent=2)
        temp_path.replace(self.storage_path)

    def _save_store(self):
        self._store["updated_at"] = self._now()
        self._write_store(self._store)

    def _next_id(self, category):
        next_ids = self._store.setdefault("next_ids", {})
        next_value = int(next_ids.get(category, 1))
        next_ids[category] = next_value + 1
        return next_value

    def _migrate_from_sqlite(self, db_path):
        try:
            import sqlite3
        except Exception:
            return None

        store = self._default_store()
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
        except Exception:
            return None

        try:
            cursor.execute(
                "SELECT id, timestamp, role, content, action_taken FROM conversations ORDER BY id ASC"
            )
            rows = cursor.fetchall()
            for row in rows:
                store["conversations"].append({
                    "id": row[0],
                    "timestamp": row[1],
                    "role": row[2],
                    "content": row[3],
                    "action_taken": row[4]
                })
        except Exception:
            pass

        try:
            cursor.execute("SELECT key, value FROM preferences")
            for key, value in cursor.fetchall():
                parsed = value
                if isinstance(value, str):
                    try:
                        parsed = json.loads(value)
                    except json.JSONDecodeError:
                        parsed = value
                store["preferences"][key] = parsed
        except Exception:
            pass

        try:
            cursor.execute(
                "SELECT id, memory_type, value, created_at, source FROM user_memory ORDER BY id ASC"
            )
            rows = cursor.fetchall()
            for row in rows:
                store["user_memory"].append({
                    "id": row[0],
                    "type": row[1],
                    "value": row[2],
                    "created_at": row[3],
                    "source": row[4] or "explicit",
                    "last_used_at": None,
                    "use_count": 0
                })
        except Exception:
            pass

        try:
            cursor.execute(
                "SELECT id, timestamp, action_type, action_details, approved, result "
                "FROM action_log ORDER BY id ASC"
            )
            rows = cursor.fetchall()
            for row in rows:
                details = row[3]
                if isinstance(details, str):
                    try:
                        details = json.loads(details)
                    except json.JSONDecodeError:
                        details = {"raw": details}
                store["action_log"].append({
                    "id": row[0],
                    "timestamp": row[1],
                    "action_type": row[2],
                    "action_details": details,
                    "approved": bool(row[4]),
                    "result": row[5]
                })
        except Exception:
            pass

        conn.close()
        store = self._normalize_store(store)
        store["next_ids"]["conversation"] = self._infer_next_id(store.get("conversations", []))
        store["next_ids"]["user_memory"] = self._infer_next_id(store.get("user_memory", []))
        store["next_ids"]["action_log"] = self._infer_next_id(store.get("action_log", []))
        return store

    def _get_preference_unlocked(self, key, default=None):
        preferences = self._store.get("preferences", {})
        return preferences.get(key, default)

    def _set_preference_unlocked(self, key, value):
        self._store.setdefault("preferences", {})[key] = value

    def add_message(self, role, content, action_taken=None):
        """Store a conversation message"""
        if not isinstance(role, str) or not isinstance(content, str):
            return

        with self._lock:
            entry = {
                "id": self._next_id("conversation"),
                "timestamp": self._now(),
                "role": role,
                "content": content,
                "action_taken": action_taken
            }
            self._store["conversations"].append(entry)
            self._save_store()

    def get_conversation_history(self, limit=50):
        """Retrieve recent conversation history"""
        with self._lock:
            messages = list(self._store.get("conversations", []))

        if limit is not None:
            messages = messages[-limit:]

        return [
            {"role": item.get("role"), "content": item.get("content")}
            for item in messages
        ]

    def get_conversation_history_with_timestamps(self, limit=50):
        """Retrieve recent conversation history with timestamps"""
        with self._lock:
            messages = list(self._store.get("conversations", []))

        if limit is not None:
            messages = messages[-limit:]

        return [
            {
                "timestamp": item.get("timestamp"),
                "role": item.get("role"),
                "content": item.get("content")
            }
            for item in messages
        ]

    def get_conversation_count(self):
        """Get total conversation message count"""
        with self._lock:
            return len(self._store.get("conversations", []))

    def get_messages_for_summary(self, keep_last=20):
        """Get older messages for summarization, excluding recent ones"""
        with self._lock:
            messages = list(self._store.get("conversations", []))

        if keep_last is None or keep_last <= 0:
            trimmed = messages
        else:
            trimmed = messages[:-keep_last]

        return [
            {"role": item.get("role"), "content": item.get("content")}
            for item in trimmed
        ]

    def log_action(self, action_type, action_details, approved, result=None):
        """Log an action that Sol attempted or executed"""
        details = action_details
        try:
            json.dumps(details)
        except TypeError:
            details = str(details)

        with self._lock:
            entry = {
                "id": self._next_id("action_log"),
                "timestamp": self._now(),
                "action_type": action_type,
                "action_details": details,
                "approved": bool(approved),
                "result": result
            }
            self._store["action_log"].append(entry)
            self._save_store()

    def save_preference(self, key, value):
        """Save or update a user preference"""
        with self._lock:
            self._set_preference_unlocked(key, value)
            self._save_store()

    def get_preference(self, key, default=None):
        """Retrieve a user preference"""
        with self._lock:
            return self._get_preference_unlocked(key, default)

    def get_mood_state(self, default_state=None):
        """Retrieve stored mood state"""
        if default_state is None:
            default_state = {"valence": 0.0, "energy": 0.5, "label": "calm"}
        return self.get_preference("mood_state", default_state)

    def set_mood_state(self, state):
        """Save mood state"""
        if not isinstance(state, dict):
            return
        self.save_preference("mood_state", state)

    def add_memory_item(self, memory_type, value, source="explicit"):
        """Store a user memory item (type/value)"""
        if not isinstance(memory_type, str) or not isinstance(value, str):
            return False

        memory_type = memory_type.strip()
        value = value.strip()
        if not memory_type or not value:
            return False

        with self._lock:
            for item in self._store.get("user_memory", []):
                if item.get("type") == memory_type and item.get("value") == value:
                    return False

            entry = {
                "id": self._next_id("user_memory"),
                "type": memory_type,
                "value": value,
                "created_at": self._now(),
                "source": source,
                "last_used_at": None,
                "use_count": 0
            }
            self._store["user_memory"].append(entry)
            self._save_store()

        return True

    def add_memory_items(self, items, source="explicit"):
        """Store multiple user memory items"""
        if not items:
            return 0

        inserted = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            memory_type = item.get("type")
            value = item.get("value")
            if self.add_memory_item(memory_type, value, source=source):
                inserted += 1

        return inserted

    def add_memory_items_from_profile(self, updates, source="extracted"):
        """Store profile updates as memory items"""
        if not isinstance(updates, dict):
            return 0

        items = []
        for key, values in updates.items():
            if not isinstance(values, list):
                continue
            for value in values:
                if isinstance(value, str) and value.strip():
                    items.append({"type": key, "value": value.strip()})

        return self.add_memory_items(items, source=source)

    def get_user_memory(self, limit=100, include_meta=False):
        """Retrieve stored user memory items"""
        with self._lock:
            items = list(self._store.get("user_memory", []))

        if limit is not None:
            items = items[-limit:]

        if include_meta:
            return [
                {
                    "id": item.get("id"),
                    "type": item.get("type"),
                    "value": item.get("value"),
                    "created_at": item.get("created_at"),
                    "source": item.get("source"),
                    "last_used_at": item.get("last_used_at"),
                    "use_count": item.get("use_count", 0)
                }
                for item in items
            ]

        return [
            {"type": item.get("type"), "value": item.get("value")}
            for item in items
        ]

    def mark_memory_used(self, records):
        """Update usage stats for retrieved memory items"""
        if not records:
            return 0

        ids = {
            record.get("id")
            for record in records
            if isinstance(record, dict) and record.get("id") is not None
        }
        if not ids:
            return 0

        now = self._now()
        updated = 0
        with self._lock:
            for item in self._store.get("user_memory", []):
                if item.get("id") in ids:
                    item["last_used_at"] = now
                    item["use_count"] = int(item.get("use_count", 0)) + 1
                    updated += 1

            if updated:
                self._save_store()

        return updated

    def get_user_profile(self):
        """Get stored user profile data"""
        default_profile = {
            "preferences": [],
            "project_context": [],
            "personal_context": [],
            "working_patterns": [],
            "humor_tolerance": [],
            "goals": [],
            "other": []
        }
        return self.get_preference("user_profile", default_profile)

    def update_user_profile(self, updates):
        """Merge new profile facts into stored profile"""
        profile = self.get_user_profile()

        for key, values in updates.items():
            if not isinstance(values, list):
                continue

            existing = profile.get(key, [])
            existing_lower = {
                item.lower() for item in existing if isinstance(item, str)
            }

            for item in values:
                if not isinstance(item, str):
                    continue
                if item.lower() not in existing_lower:
                    existing.append(item)
                    existing_lower.add(item.lower())

            profile[key] = existing

        self.save_preference("user_profile", profile)
        self.add_memory_items_from_profile(updates, source="extracted")
        return profile

    def add_conversation_summary(self, summary_text):
        """Store the latest conversation summary"""
        if not summary_text:
            return

        timestamp = self._now()
        with self._lock:
            summaries = self._get_preference_unlocked("conversation_summaries", default=[])
            if not isinstance(summaries, list):
                summaries = []
            summaries.append({"timestamp": timestamp, "summary": summary_text})
            self._set_preference_unlocked("conversation_summaries", summaries)
            self._set_preference_unlocked("conversation_summary", summary_text)
            self._save_store()

    def get_latest_summary(self):
        """Get the latest conversation summary"""
        return self.get_preference("conversation_summary", default="")

    def get_recent_actions(self, limit=10):
        """Get recent action log entries"""
        with self._lock:
            actions = list(self._store.get("action_log", []))

        if limit is not None:
            actions = actions[-limit:]

        actions.reverse()

        return [
            {
                "timestamp": action.get("timestamp"),
                "action_type": action.get("action_type"),
                "details": action.get("action_details"),
                "approved": bool(action.get("approved")),
                "result": action.get("result")
            }
            for action in actions
        ]

    def clear_old_conversations(self, keep_last=100):
        """Clear old conversation history, keeping only recent messages"""
        with self._lock:
            conversations = list(self._store.get("conversations", []))

            if keep_last is None or keep_last <= 0:
                self._store["conversations"] = []
            else:
                self._store["conversations"] = conversations[-keep_last:]

            self._save_store()

    def start_new_session(self, session_name=None):
        """Start a new chat session, preserving user memory and profile.
        Archives current conversations to sessions history and clears chat history.
        Returns the new session ID."""
        with self._lock:
            now = self._now()

            # Save current conversations as a session
            current_conversations = list(self._store.get("conversations", []))
            if current_conversations:
                session_data = {
                    "id": len(self._store.get("sessions", [])) + 1,
                    "timestamp": now,
                    "name": session_name or f"Session {len(self._store.get('sessions', [])) + 1}",
                    "messages": current_conversations
                }
                self._store.setdefault("sessions", []).append(session_data)

            # Clear conversation history but keep user_memory and profile
            self._store["conversations"] = []
            self._store["next_ids"]["conversation"] = 1

            self._save_store()
            return len(self._store.get("sessions", []))

    def get_sessions(self):
        """Get all archived sessions"""
        with self._lock:
            return list(self._store.get("sessions", []))

    def load_session(self, session_id):
        """Load a previous session's conversations (replaces current history)"""
        with self._lock:
            sessions = self._store.get("sessions", [])
            session = next((s for s in sessions if s.get("id") == session_id), None)
            if session:
                self._store["conversations"] = session.get("messages", [])
                self._save_store()
                return True
            return False
