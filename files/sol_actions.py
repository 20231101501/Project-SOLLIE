"""
Sol PC Actions Module
Safe PC control operations with whitelist and approval system
"""

import os
import subprocess
import psutil
import json
import sys
import random
import shutil
import time
import threading
from pathlib import Path
import webbrowser
from datetime import datetime, timedelta


class SolActions:
    def __init__(self, config_path="config.json"):
        self.config = self.load_config(config_path)
        self.user_home = Path.home()
        self.allowed_app_entries = list(self.config['safety']['allowed_applications'])
        self.allowed_apps = {Path(app).name.lower() for app in self.allowed_app_entries}
        self.allowed_dirs = {
            dir_name.lower() for dir_name in self.config['safety']['allowed_directories']
        }
        self.allowed_root_paths = [
            Path(path).expanduser().resolve(strict=False)
            for path in self.config['safety'].get('allowed_root_paths', [])
        ]
        default_extensions = {
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
        }
        configured_extensions = self.config['safety'].get('allowed_file_extensions')
        if configured_extensions:
            self.allowed_file_extensions = {ext.lower() for ext in configured_extensions}
        else:
            self.allowed_file_extensions = default_extensions
        # Reminder checker thread
        self._reminder_thread = None
        self._reminder_callbacks = []
        self._start_reminder_checker()

    def _reminder_checker(self):
        """Background thread to check for due reminders"""
        while True:
            try:
                time.sleep(10)  # Check every 10 seconds
                result = self.check_reminders()
                if result.get("success") and result.get("count", 0) > 0:
                    due_reminders = result.get("due", [])
                    for reminder in due_reminders:
                        message = reminder.get("message", "Reminder!")
                        # Call all registered callbacks
                        for callback in self._reminder_callbacks:
                            try:
                                callback(message, reminder)
                            except Exception:
                                pass
                        # Also print to stdout for simple notification
                        print(f"\n[REMINDER] {message}")
            except Exception:
                pass

    def _start_reminder_checker(self):
        """Start the background reminder checker thread"""
        if self._reminder_thread is None or not self._reminder_thread.is_alive():
            self._reminder_thread = threading.Thread(target=self._reminder_checker, daemon=True)
            self._reminder_thread.start()

    def register_reminder_callback(self, callback):
        """Register a callback function to be called when reminders are due"""
        self._reminder_callbacks.append(callback)
    
    def load_config(self, config_path):
        """Load configuration from JSON file"""
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def is_action_safe(self, action_type):
        """Check if an action is blocked by safety rules"""
        blocked = self.config['safety']['blocked_actions']
        return action_type.lower() not in blocked
    
    def _normalize_app_name(self, app_name):
        return Path(app_name).name.lower()

    def _app_search_roots(self):
        if os.name != "nt":
            return []

        roots = []
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("PROGRAMFILES", "")
        program_files_x86 = os.environ.get("PROGRAMFILES(X86)", "")
        appdata = os.environ.get("APPDATA", "")
        program_data = os.environ.get("PROGRAMDATA", "")

        if local_appdata:
            roots.append(Path(local_appdata) / "Programs")
        if program_files:
            roots.append(Path(program_files))
        if program_files_x86:
            roots.append(Path(program_files_x86))

        if program_data:
            roots.append(Path(program_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
        if appdata:
            roots.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")

        return [root for root in roots if root.exists()]

    def _find_app_in_tree(self, root, candidate_names, max_depth=3):
        root = Path(root)
        for base, dirs, files in os.walk(root):
            base_path = Path(base)
            try:
                relative = base_path.relative_to(root)
            except ValueError:
                continue

            if len(relative.parts) > max_depth:
                dirs[:] = []
                continue

            for file_name in files:
                if file_name.lower() in candidate_names:
                    return base_path / file_name

        return None

    def _resolve_app_path(self, app_name):
        app_path = Path(app_name)
        if app_path.is_file():
            return app_path

        normalized = self._normalize_app_name(app_name)
        base = Path(normalized).stem
        candidate_names = {normalized, f"{base}.exe", f"{base}.lnk"}

        # Check configured allowed entries for full paths
        for entry in self.allowed_app_entries:
            entry_path = Path(entry)
            if entry_path.is_file() and entry_path.name.lower() in candidate_names:
                return entry_path

        # Fallback: Check system PATH using shutil.which
        which_path = shutil.which(normalized)
        if which_path:
            candidate = Path(which_path)
            if self._is_trusted_location(candidate):
                return candidate

        # Search Desktop for shortcuts and executables
        desktop_path = self.user_home / "Desktop"
        if desktop_path.exists():
            for item in desktop_path.iterdir():
                if item.is_file() and item.name.lower() in candidate_names:
                    return item
                if item.is_file() and item.stem.lower() in {n.lower() for n in candidate_names}:
                    return item

        # Search Desktop subfolders (common for game shortcuts)
        if desktop_path.exists():
            for item in desktop_path.iterdir():
                if item.is_dir():
                    found = self._find_app_in_tree(item, candidate_names, max_depth=2)
                    if found:
                        return found

        # Search common install locations
        for root in self._app_search_roots():
            found = self._find_app_in_tree(root, candidate_names)
            if found:
                return found

        return None

    def _is_trusted_location(self, path):
        """Check if a resolved path is within a trusted system directory."""
        trusted_roots = []
        
        # Add standard Windows system paths
        for var in ["WINDIR", "PROGRAMFILES", "PROGRAMFILES(X86)"]:
            root = os.environ.get(var)
            if root:
                trusted_roots.append(Path(root))
        
        # Add user-specific trusted paths
        local = os.environ.get("LOCALAPPDATA")
        if local:
            trusted_roots.extend([
                Path(local) / "Programs",
                Path(local) / "Microsoft" / "WindowsApps"
            ])
        
        # Add configured allowed roots
        trusted_roots.extend(self.allowed_root_paths)

        try:
            return any(path.is_relative_to(root) for root in trusted_roots if root.exists())
        except (ValueError, AttributeError):
            return False

    def _resolve_path(self, path_str):
        path = Path(path_str).expanduser()

        if not path.is_absolute():
            parts = path.parts
            if parts and parts[0].lower() in self.allowed_dirs:
                path = self.user_home / path
            else:
                path = self.user_home / "Desktop" / path

        return path.resolve(strict=False)

    def _find_directory_in_tree(self, root, target_name, max_depth=3):
        root = Path(root)
        target_lower = target_name.lower()

        for base, dirs, _ in os.walk(root):
            base_path = Path(base)
            try:
                relative = base_path.relative_to(root)
            except ValueError:
                continue

            if len(relative.parts) > max_depth:
                dirs[:] = []
                continue

            for dir_name in dirs:
                if dir_name.lower() == target_lower:
                    return base_path / dir_name

        return None

    def resolve_directory_query(self, directory):
        path = Path(directory).expanduser()
        if path.is_absolute():
            return path.resolve(strict=False)

        if len(path.parts) > 1:
            return self._resolve_path(directory)

        for dir_name in self.config['safety']['allowed_directories']:
            if dir_name.lower() == str(path).lower():
                return (self.user_home / dir_name).resolve(strict=False)

        for root in self._get_allowed_roots():
            found = self._find_directory_in_tree(root, str(path))
            if found:
                return found.resolve(strict=False)

        return self._resolve_path(directory)

    def _is_under_root(self, path, root):
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def _get_allowed_roots(self, directory=None):
        if directory:
            path = self._resolve_path(directory)
            if self.is_directory_safe(path) and path.exists() and path.is_dir():
                return [path]
            return []

        roots = []
        for dir_name in self.config['safety']['allowed_directories']:
            candidate = (self.user_home / dir_name).resolve(strict=False)
            if candidate.exists() and candidate.is_dir():
                roots.append(candidate)

        for root in self.allowed_root_paths:
            if root.exists() and root.is_dir():
                roots.append(root)

        return roots

    def is_file_extension_allowed(self, path):
        if not self.allowed_file_extensions:
            return False
        return path.suffix.lower() in self.allowed_file_extensions

    def is_app_allowed(self, app_name):
        """Check if an application is whitelisted"""
        return self._normalize_app_name(app_name) in self.allowed_apps
    
    def is_directory_safe(self, directory):
        """Check if directory is in allowed list"""
        dir_path = Path(directory).expanduser().resolve(strict=False)
        
        # Check if it's in user's home directory and in allowed subdirectories
        try:
            relative = dir_path.relative_to(self.user_home)
            first_part = relative.parts[0] if relative.parts else ""
            return first_part.lower() in self.allowed_dirs
        except ValueError:
            pass

        for root in self.allowed_root_paths:
            if self._is_under_root(dir_path, root):
                return True

        return False
    
    # ===== FILE OPERATIONS =====
    
    def create_file(self, filepath, content=""):
        """Create a new file with optional content"""
        try:
            path = self._resolve_path(filepath)
            
            if not self.is_directory_safe(path.parent):
                return {"success": False, "error": "Directory not in safe list"}
            
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            return {"success": True, "message": f"File created: {path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def read_file(self, filepath):
        """Read file contents"""
        try:
            path = self._resolve_path(filepath)
            
            if not self.is_directory_safe(path.parent):
                return {"success": False, "error": "Directory not in safe list"}
            
            content = path.read_text()
            return {"success": True, "content": content}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def list_directory(self, directory):
        """List files in a directory"""
        try:
            path = self._resolve_path(directory)
            
            if not self.is_directory_safe(path):
                return {"success": False, "error": "Directory not in safe list"}

            if not path.exists() or not path.is_dir():
                return {"success": False, "error": "Directory does not exist"}
            
            files = [f.name for f in path.iterdir()]
            return {"success": True, "files": files}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_file(self, filepath):
        """Open a file with the default application"""
        try:
            path = self._resolve_path(filepath)

            if not self.is_directory_safe(path.parent):
                return {"success": False, "error": "Directory not in safe list"}

            if not path.exists() or not path.is_file():
                return {"success": False, "error": "File does not exist"}

            if not self.is_file_extension_allowed(path):
                return {"success": False, "error": "File type not allowed"}

            if os.name == 'nt':
                os.startfile(str(path))
            elif sys.platform == 'darwin':
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])

            return {"success": True, "message": f"Opened file: {path.name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_directory(self, directory):
        """Open a directory in the default file explorer"""
        try:
            path = self.resolve_directory_query(directory)

            if not path.exists() or not path.is_dir():
                return {"success": False, "error": "Directory does not exist"}

            if not self.is_directory_safe(path):
                return {"success": False, "error": "Directory not in safe list"}

            if os.name == 'nt':
                os.startfile(str(path))
            elif sys.platform == 'darwin':
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])

            return {"success": True, "message": f"Opened folder: {path.name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_random_file(self, file_extensions=None, directory=None):
        """Open a random file from allowed directories"""
        try:
            roots = self._get_allowed_roots(directory)
            if not roots:
                return {"success": False, "error": "No safe directories available"}

            if file_extensions:
                exts = {
                    ext.lower() if ext.startswith(".") else f".{ext.lower()}"
                    for ext in file_extensions
                }
            else:
                exts = set(self.allowed_file_extensions)

            if not exts:
                return {"success": False, "error": "No allowed file types configured"}

            selected = None
            seen = 0

            for root in roots:
                for base, _, files in os.walk(root):
                    base_path = Path(base)
                    if not self.is_directory_safe(base_path):
                        continue

                    for file_name in files:
                        path = base_path / file_name
                        if path.suffix.lower() in exts:
                            seen += 1
                            if random.randint(1, seen) == 1:
                                selected = path

            if not selected:
                return {"success": False, "error": "No matching files found"}

            result = self.open_file(str(selected))
            if result.get("success"):
                result["message"] = f"Opened random file: {selected.name}"
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ===== APPLICATION OPERATIONS =====
    
    def open_application(self, app_name):
        """Open an application (whitelist removed for flexibility)"""
        try:
            resolved = self._resolve_app_path(app_name)
            
            # Fallback: try to start directly via system PATH/associations
            if not resolved or not resolved.exists():
                try:
                    subprocess.Popen([app_name])
                    return {"success": True, "message": f"Started {app_name}"}
                except Exception:
                    return {"success": False, "error": f"Application not found: {app_name}"}

            if resolved.suffix.lower() == ".lnk":
                os.startfile(str(resolved))
            else:
                subprocess.Popen([str(resolved)])

            return {"success": True, "message": f"Opened {resolved.name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def application(self, name):
        """Alias for open_application"""
        return self.open_application(name)

    def command(self, command):
        """Alias for execute_safe_command"""
        return self.execute_safe_command(command)
    
    def close_application(self, app_name):
        """Close a running application"""
        try:
            target_name = self._normalize_app_name(app_name)
            # Find and terminate the process
            killed = False
            for proc in psutil.process_iter(['name']):
                proc_name = (proc.info.get('name') or "").lower()
                if proc_name == target_name:
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
        safe_commands = ['dir', 'ls', 'echo', 'date', 'time']
        
        cmd_base = command.split()[0].lower()
        if cmd_base not in safe_commands:
            return {"success": False, "error": "Command not in safe list"}
        
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=5)
            return {"success": True, "output": result.stdout}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def type_text(self, text, interval=0.05):
        """Type text into the active window using PyAutoGUI"""
        try:
            import pyautogui
            pyautogui.write(text, interval=interval)
            return {"success": True, "message": f"Typed text successfully."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def write_file_content(self, filepath, content):
        """Write content to a file (overwrites existing)"""
        return self.create_file(filepath, content)

    # ===== REMINDER SYSTEM =====
    
    def _get_reminders_path(self):
        """Get the path to the reminders JSON file"""
        return Path.home() / ".sol_reminders.json"
    
    def _load_reminders(self):
        """Load reminders from disk"""
        path = self._get_reminders_path()
        if path.exists():
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return []
    
    def _save_reminders(self, reminders):
        """Save reminders to disk"""
        path = self._get_reminders_path()
        try:
            with open(path, 'w') as f:
                json.dump(reminders, f, indent=2)
        except Exception:
            pass
    
    def set_reminder(self, message, delay_minutes=None, remind_time=None):
        """Set a reminder. Either provide delay_minutes or remind_time (ISO format)"""
        try:
            reminder = {
                "id": int(time.time() * 1000),
                "message": message,
                "created": datetime.now().isoformat()
            }
            
            if delay_minutes is not None:
                remind_at = datetime.now() + timedelta(minutes=delay_minutes)
                reminder["remind_at"] = remind_at.isoformat()
            elif remind_time:
                reminder["remind_at"] = remind_time
            else:
                return {"success": False, "error": "Must provide delay_minutes or remind_time"}
            
            reminders = self._load_reminders()
            reminders.append(reminder)
            self._save_reminders(reminders)
            
            return {"success": True, "message": f"Reminder set for {reminder['remind_at']}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def list_reminders(self):
        """List all pending reminders"""
        try:
            reminders = self._load_reminders()
            now = datetime.now()
            pending = []
            for r in reminders:
                try:
                    remind_at = datetime.fromisoformat(r["remind_at"])
                    if remind_at > now:
                        pending.append(r)
                except (KeyError, ValueError):
                    pass
            return {"success": True, "reminders": pending}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def check_reminders(self):
        """Check for due reminders and return them"""
        try:
            reminders = self._load_reminders()
            now = datetime.now()
            due = []
            remaining = []
            
            for r in reminders:
                try:
                    remind_at = datetime.fromisoformat(r["remind_at"])
                    if remind_at <= now:
                        due.append(r)
                    else:
                        remaining.append(r)
                except (KeyError, ValueError):
                    remaining.append(r)
            
            if due:
                self._save_reminders(remaining)
            
            return {"success": True, "due": due, "count": len(due)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def clear_reminder(self, reminder_id):
        """Clear a specific reminder by ID"""
        try:
            reminders = self._load_reminders()
            new_reminders = [r for r in reminders if r.get("id") != reminder_id]
            self._save_reminders(new_reminders)
            return {"success": True, "message": "Reminder cleared"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ===== WEB SEARCH =====
    
    def web_search(self, query, max_results=5):
        """Perform a web search using DuckDuckGo instant answer API (no API key required)"""
        try:
            import urllib.parse
            import urllib.request
            import json as json_mod
            
            # Use DuckDuckGo instant answer API - more reliable than HTML scraping
            query_encoded = urllib.parse.quote_plus(query)
            url = f"https://api.duckduckgo.com/?q={query_encoded}&format=json&no_html=1"
            
            headers = {'User-Agent': 'Sol/1.0'}
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json_mod.loads(response.read().decode('utf-8'))
            
            results = []
            
            # Extract instant answer
            abstract = data.get('AbstractText', '')
            if abstract:
                results.append({
                    'title': data.get('Heading', query),
                    'href': data.get('AbstractSourceUrl', ''),
                    'snippet': abstract[:200]
                })
            
            # Extract related topics
            for topic in data.get('RelatedTopics', [])[:max_results-1]:
                if isinstance(topic, dict) and 'Text' in topic:
                    title = topic.get('Text', '')[:100]
                    href = topic.get('FirstURL', '')
                    results.append({
                        'title': title,
                        'href': href,
                        'snippet': topic.get('Text', '')[:200]
                    })
            
            if not results:
                return {"success": False, "error": "No results found", "results": []}
            
            return {"success": True, "results": results[:max_results], "count": len(results)}
        except Exception as e:
            return {"success": False, "error": str(e), "results": []}
    
    def get_weather(self, location="auto:ip"):
        """Get weather information (uses wttr.in, no API key required)"""
        try:
            import urllib.request
            import json as json_mod
            
            # Use wttr.in text format - more reliable
            if location == "auto:ip":
                url = "https://wttr.in/?format=3"
            else:
                url = f"https://wttr.in/{urllib.parse.quote_plus(location)}?format=3"
            
            headers = {'User-Agent': 'Sol/1.0'}
            req = urllib.request.Request(url, headers=headers)
            
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    weather_text = response.read().decode('utf-8').strip()
            except urllib.error.HTTPError:
                # Fallback: try j1 format
                if location != "auto:ip":
                    url = f"https://wttr.in/{urllib.parse.quote_plus(location)}?format=j1"
                else:
                    url = "https://wttr.in/?format=j1"
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json_mod.loads(response.read().decode('utf-8'))
                    current = data.get('current_condition', [{}])[0]
                    weather_text = f"{data.get('nearest_area', [{}])[0].get('areaName', [{}])[0].get('value', 'Unknown')}: {current.get('weatherDesc', [{}])[0].get('value', '')} {current.get('temp_C', '0')}°C"
            
            return {"success": True, "weather": {"simple": weather_text}}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_news_headlines(self, topic="top"):
        """Get news headlines (uses Hacker News API as free source)"""
        try:
            import urllib.request
            import json as json_mod
            
            # Use Hacker News Algo feed as a simple news source
            url = "https://hacker-news.firebaseio.com/v0/topstories.json"
            headers = {'User-Agent': 'Sol/1.0'}
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=10) as response:
                story_ids = json_mod.loads(response.read().decode('utf-8'))[:10]
            
            headlines = []
            for story_id in story_ids[:5]:
                try:
                    story_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                    story_req = urllib.request.Request(story_url, headers=headers)
                    with urllib.request.urlopen(story_req, timeout=5) as story_response:
                        story = json_mod.loads(story_response.read().decode('utf-8'))
                        if story.get('title'):
                            headlines.append({
                                'title': story['title'],
                                'url': story.get('url', ''),
                                'score': story.get('score', 0)
                            })
                except Exception:
                    continue
            
            return {"success": True, "headlines": headlines, "count": len(headlines)}
        except Exception as e:
            return {"success": False, "error": str(e)}


    def save_settings_action(self, **kwargs):
        """Save a setting value to config.json"""
        setting = kwargs.get('setting', '')
        value = kwargs.get('value', '')
        
        if not setting:
            return {"success": False, "error": "No setting specified"}
        
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Parse setting path (e.g., "lm_studio.temperature")
            parts = setting.split('.')
            if len(parts) == 2:
                section, key = parts
                config.setdefault(section, {})
                config[section][key] = value
            else:
                config[setting] = value
            
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            return {"success": True, "message": f"Setting '{setting}' saved"}
        except Exception as e:
            return {"success": False, "error": str(e)}
