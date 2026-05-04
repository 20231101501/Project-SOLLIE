# 🤖 SOL - Your Personal AI Assistant

**A local, private, and safe AI assistant that can control your PC**

Built with love for complete privacy and control - everything runs on YOUR hardware.

---

## 🎯 What is Sol?

Sol is your personal AI assistant (like JARVIS) that:
- ✅ Runs 100% locally on your PC (no cloud, no subscriptions)
- ✅ Has a friendly personality and learns your preferences
- ✅ Can control your PC safely (open apps, manage files, etc.)
- ✅ Asks for permission before doing anything
- ✅ Remembers your conversations
- ✅ Has a modern GUI interface

---

## 🔧 System Requirements

- **OS**: Windows 10/11 (64-bit)
- **CPU**: AMD Ryzen 5 or better (you have: Ryzen 7 5700X ✓)
- **RAM**: 16GB minimum (you have: 32GB ✓)
- **GPU**: 8GB+ VRAM (you have: RX 9060 XT 16GB ✓)
- **Storage**: 20GB free space
- **Python**: 3.8+ (you have: 3.14.4 ✓)

**✓ Your PC is PERFECT for running Sol!**

---

## 📦 What You Get

```
sol/
├── config.json           # Settings and safety rules
├── sol_core.py        # AI brain
├── sol_gui.py         # User interface
├── sol_actions.py     # PC control functions
├── sol_memory.py      # Memory & learning
├── setup.py              # Installation script
├── requirements.txt      # Dependencies
└── README.md             # This file
```

---

## 🚀 Installation (STEP-BY-STEP)

### Step 1: Download & Extract Files

1. Download the Sol folder to your PC
2. Extract to a location like: `C:\Users\YourName\Sol`

### Step 2: Run Setup

1. Open **Command Prompt** in the Sol folder:
   - Hold `Shift` + Right-click in the folder
   - Click "Open PowerShell window here" or "Open Command Prompt here"

2. Run the setup:
   ```bash
   python setup.py
   ```

3. Wait for installation (2-5 minutes)
   - It will install all required packages
   - Test connections
   - Create a desktop shortcut

### Step 3: Setup LM Studio

1. **Download LM Studio**: https://lmstudio.ai/
2. Install and open it
3. **Download a model**:
   - Go to "Discover" tab
   - Search: `Llama-3.1-8B-Instruct`
   - Click Download (takes 10-20 mins)
4. **Start Local Server**:
   - Go to "Local Server" tab
   - Select your downloaded model
   - Click "Start Server"
   - Keep this running!

### Step 4: Launch Sol

**Option A: Desktop Shortcut**
- Double-click the "Sol" shortcut on your desktop

**Option B: Command Line**
```bash
python sol_launcher.py
```

---

## 💬 How to Use Sol

### Basic Chat
Just talk naturally! Sol understands conversational language.

```
You: Hey Sol, how are you?
Sol: I'm doing great! Ready to help you with whatever you need.

You: What can you do?
Sol: I can help you with...
```

### Agentic Task Mode
Use task mode to plan and execute multi-step goals (with approvals on each action).

```
You: /task Clean up my Downloads and open the newest PDF
```

To stop a task at any time:

```
You: /stop
```

### PC Control Examples

**Opening Applications:**
```
You: Open Chrome
You: Launch Notepad
You: Start Spotify
```

**File Management:**
```
You: Create a file called todo.txt
You: List my Desktop files
You: Show my Documents folder
```

**System Info:**
```
You: What's my PC status?
You: Show system information
```

**Web Browsing:**
```
You: Open YouTube
You: Go to reddit.com
```

**Opening Files:**
```
You: Open photo.jpg
You: Open video.mp4
```

### 🔒 Safety Features

**Sol ALWAYS asks before doing anything!**

When you request an action:
1. Sol analyzes the request
2. Shows you what it wants to do
3. Waits for your approval
4. Only executes if you click "Approve"

**Example:**
```
You: Open Chrome
Sol: I can open Chrome for you.
[Approval prompt appears]
⚠ Sol wants to: Open chrome.exe
[✓ Approve] [✗ Deny]
```

---

## ⚙️ Configuration

### Editing Settings (`config.json`)

#### Add More Allowed Apps
```json
"allowed_applications": [
  "chrome.exe",
  "firefox.exe",
  "notepad.exe",
  "your-app.exe"  // Add your app here
]
```
Tip: You can use full paths here if an app is not on your PATH.

#### Adjust AI Personality
```json
"personality": "You are Sol, a helpful assistant who is witty and clever..."
```

#### Disable Approval (Advanced Users Only!)
```json
"approval_required": false  // ⚠ Use with caution!
```

#### Auto-start LM Studio (Windows)
```json
"app_path": "C:\\Program Files\\LM Studio\\LM Studio.exe",
"auto_start": true,
"startup_timeout_sec": 45
```

#### Agentic Tasks & Monitoring
```json
"agent": {
   "enabled": true,
   "max_steps": 5
},
"monitoring": {
   "enabled": true,
   "interval_sec": 30,
   "cpu_percent": 85,
   "memory_percent": 85,
   "disk_percent": 90,
   "quiet_hours": { "start": "23:00", "end": "07:00" }
},
"proactive_suggestions": {
   "enabled": true,
   "cooldown_sec": 600,
   "auto_queue_actions": true
}
```

---

## 🛠️ Troubleshooting

### "Cannot connect to LM Studio"
**Solution:**
1. Make sure LM Studio is running
2. Go to "Local Server" tab in LM Studio
3. Click "Start Server"
4. Check URL is: `http://localhost:1234`

### "Module not found" error
**Solution:**
```bash
python setup.py
```
This will reinstall all dependencies.

### Sol is slow to respond
**Solution:**
- Use a smaller model (7B instead of 13B)
- Check your GPU is being used in LM Studio
- Close other heavy applications

### GUI doesn't open
**Solution:**
```bash
pip install customtkinter --break-system-packages --upgrade
python sol_gui.py
```

---

## 🎨 Customization Ideas

### Change Sol's Name
Edit `config.json`:
```json
"name": "JARVIS"  // or whatever you like
```

### Add More Safe Directories
```json
"allowed_directories": [
  "Desktop",
  "Documents",
  "Downloads",
  "MyProject"  // Add custom folders
]
```

### Different AI Models

In LM Studio, try these models:
- **Fast**: Llama 3.1 8B (recommended)
- **Smart**: Llama 3.1 13B
- **Balanced**: Mistral 7B
- **Advanced**: Qwen 2.5 14B

---

## 🔐 Privacy & Security

### What Sol DOES:
✅ Runs 100% on your local PC
✅ No internet connection needed (except for model download)
✅ All data stays on your computer
✅ No tracking, no telemetry, no cloud

### What Sol CANNOT do (by default):
❌ Delete system files
❌ Shutdown/restart your PC
❌ Edit Windows registry
❌ Install software without permission
❌ Access blocked directories

### Action Logging
Every action is logged in `sol_memory.json`
- View in Settings → "View Action Log"
- See what Sol tried to do
- Review approved/denied actions

---

## 🐛 Known Limitations

1. **No voice commands yet** (coming soon!)
2. **Context window limited** (~10 messages)
3. **No built-in web browsing** (only opens URLs in your browser)
4. **Windows only** (Mac/Linux coming later)
5. **Model must be downloaded manually**

---

## 🚀 Future Features (Roadmap)

- [ ] Voice input/output
- [ ] Proactive notifications
- [ ] Task scheduling
- [ ] Email integration
- [ ] Calendar management
- [ ] File content search
- [ ] Smart home control
- [ ] Multi-language support

---

## 📝 Frequently Asked Questions

**Q: Does this cost money?**
A: No! 100% free. No subscriptions, no API fees.

**Q: Is my data private?**
A: Yes! Everything runs locally. Nothing is sent to the cloud.

**Q: Can I add more capabilities?**
A: Yes! Edit `sol_actions.py` to add custom functions.

**Q: What if I break something?**
A: Sol has safety limits. It can't damage your system. Worst case: reinstall.

**Q: Can I use a different AI model?**
A: Yes! Download any model in LM Studio and select it.

**Q: How do I update Sol?**
A: Replace the files and run `setup.py` again.

---

## 🎓 Advanced Usage

### Running Without GUI (Command Line)
```python
from sol_core import SolBrain

brain = SolBrain()
response = brain.chat("Hello Sol!")
print(response['response'])
```

### Custom Actions
Add to `sol_actions.py`:
```python
def my_custom_action(self, param):
    # Your code here
    return {"success": True, "message": "Done!"}
```

### API Mode (for developers)
Sol can be used as a local API:
```python
# Your app → Sol → LM Studio → Response
```

---

## 🙏 Credits

Built with:
- LM Studio (local AI)
- Python + CustomTkinter (UI)
- Llama 3.1 (AI model)
- Love and caffeine ☕

---

## 📄 License

This project is free to use for personal use.
No warranty provided - use at your own risk!

---

## 🆘 Need Help?

1. Check this README first
2. Review `config.json` settings
3. Test LM Studio connection
4. Check action logs in Settings

**Remember: Sol is designed to be safe. It will always ask before doing anything important!**

---

**Enjoy your personal AI assistant! 🚀**
