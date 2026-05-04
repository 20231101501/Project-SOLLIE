"""
Sollie Memory System
Handles conversation history, user preferences, and learning
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path


class SollieMemory:
    def __init__(self, db_path="sollie_memory.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with necessary tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Conversation history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                action_taken TEXT
            )
        ''')
        
        # User preferences table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # Action log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action_type TEXT NOT NULL,
                action_details TEXT NOT NULL,
                approved BOOLEAN NOT NULL,
                result TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_message(self, role, content, action_taken=None):
        """Store a conversation message"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        cursor.execute(
            'INSERT INTO conversations (timestamp, role, content, action_taken) VALUES (?, ?, ?, ?)',
            (timestamp, role, content, action_taken)
        )
        
        conn.commit()
        conn.close()
    
    def get_conversation_history(self, limit=50):
        """Retrieve recent conversation history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?',
            (limit,)
        )
        
        messages = cursor.fetchall()
        conn.close()
        
        # Return in correct order (oldest first)
        return [{"role": role, "content": content} for role, content in reversed(messages)]

    def get_conversation_history_with_timestamps(self, limit=50):
        """Retrieve recent conversation history with timestamps"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            'SELECT timestamp, role, content FROM conversations ORDER BY id DESC LIMIT ?',
            (limit,)
        )

        messages = cursor.fetchall()
        conn.close()

        # Return in correct order (oldest first)
        return [
            {"timestamp": timestamp, "role": role, "content": content}
            for timestamp, role, content in reversed(messages)
        ]

    def get_conversation_count(self):
        """Get total conversation message count"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM conversations')
        count = cursor.fetchone()[0]
        conn.close()

        return count

    def get_messages_for_summary(self, keep_last=20):
        """Get older messages for summarization, excluding recent ones"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            'SELECT id FROM conversations ORDER BY id DESC LIMIT ?',
            (keep_last,)
        )
        recent_ids = [row[0] for row in cursor.fetchall()]

        if recent_ids:
            placeholders = ','.join('?' * len(recent_ids))
            cursor.execute(
                f'SELECT role, content FROM conversations WHERE id NOT IN ({placeholders}) ORDER BY id ASC',
                recent_ids
            )
        else:
            cursor.execute('SELECT role, content FROM conversations ORDER BY id ASC')

        messages = cursor.fetchall()
        conn.close()

        return [{"role": role, "content": content} for role, content in messages]
    
    def log_action(self, action_type, action_details, approved, result=None):
        """Log an action that Sollie attempted or executed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        cursor.execute(
            'INSERT INTO action_log (timestamp, action_type, action_details, approved, result) VALUES (?, ?, ?, ?, ?)',
            (timestamp, action_type, json.dumps(action_details), approved, result)
        )
        
        conn.commit()
        conn.close()
    
    def save_preference(self, key, value):
        """Save or update a user preference"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        cursor.execute(
            'INSERT OR REPLACE INTO preferences (key, value, updated_at) VALUES (?, ?, ?)',
            (key, json.dumps(value), timestamp)
        )
        
        conn.commit()
        conn.close()
    
    def get_preference(self, key, default=None):
        """Retrieve a user preference"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT value FROM preferences WHERE key = ?', (key,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return json.loads(result[0])
        return default

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
        return profile

    def add_conversation_summary(self, summary_text):
        """Store the latest conversation summary"""
        if not summary_text:
            return

        timestamp = datetime.now().isoformat()
        summaries = self.get_preference("conversation_summaries", default=[])
        summaries.append({"timestamp": timestamp, "summary": summary_text})

        self.save_preference("conversation_summaries", summaries)
        self.save_preference("conversation_summary", summary_text)

    def get_latest_summary(self):
        """Get the latest conversation summary"""
        return self.get_preference("conversation_summary", default="")
    
    def get_recent_actions(self, limit=10):
        """Get recent action log entries"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT timestamp, action_type, action_details, approved, result FROM action_log ORDER BY id DESC LIMIT ?',
            (limit,)
        )
        
        actions = cursor.fetchall()
        conn.close()
        
        return [
            {
                "timestamp": timestamp,
                "action_type": action_type,
                "details": json.loads(action_details),
                "approved": bool(approved),
                "result": result
            }
            for timestamp, action_type, action_details, approved, result in actions
        ]
    
    def clear_old_conversations(self, keep_last=100):
        """Clear old conversation history, keeping only recent messages"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'DELETE FROM conversations WHERE id NOT IN (SELECT id FROM conversations ORDER BY id DESC LIMIT ?)',
            (keep_last,)
        )
        
        conn.commit()
        conn.close()
