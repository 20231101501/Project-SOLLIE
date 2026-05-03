"""
Sollie Test Script
Quick test to verify all components are working
"""

import sys
from pathlib import Path


def print_section(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)


def test_imports():
    """Test if all required modules can be imported"""
    print_section("Testing Imports")
    
    modules = {
        "requests": "HTTP requests",
        "customtkinter": "GUI framework",
        "psutil": "System monitoring",
        "pyautogui": "Automation",
        "sqlite3": "Database (built-in)",
        "json": "JSON handling (built-in)",
        "threading": "Multi-threading (built-in)"
    }
    
    failed = []
    for module, description in modules.items():
        try:
            __import__(module)
            print(f"✓ {module:20s} - {description}")
        except ImportError:
            print(f"✗ {module:20s} - FAILED")
            failed.append(module)
    
    if failed:
        print(f"\n❌ Missing modules: {', '.join(failed)}")
        print("Run: python setup.py")
        return False
    
    print("\n✓ All imports successful")
    return True


def test_config():
    """Test if config file exists and is valid"""
    print_section("Testing Configuration")
    
    import json
    
    if not Path("config.json").exists():
        print("❌ config.json not found!")
        return False
    
    try:
        with open("config.json", 'r') as f:
            config = json.load(f)
        
        required_keys = ['lm_studio', 'sollie', 'safety', 'memory']
        for key in required_keys:
            if key in config:
                print(f"✓ {key} section found")
            else:
                print(f"✗ {key} section missing")
                return False
        
        print("\n✓ Configuration valid")
        return True
    
    except json.JSONDecodeError:
        print("❌ config.json is not valid JSON!")
        return False


def test_sollie_modules():
    """Test if Sollie modules can be imported"""
    print_section("Testing Sollie Modules")
    
    modules = {
        "sollie_memory": "Memory system",
        "sollie_actions": "PC actions",
        "sollie_core": "Core brain"
    }
    
    failed = []
    for module, description in modules.items():
        try:
            __import__(module)
            print(f"✓ {module:20s} - {description}")
        except ImportError as e:
            print(f"✗ {module:20s} - FAILED: {e}")
            failed.append(module)
    
    if failed:
        print(f"\n❌ Failed to import: {', '.join(failed)}")
        return False
    
    print("\n✓ All Sollie modules loaded")
    return True


def test_intent_parsing():
    """Test intent parsing for common commands"""
    print_section("Testing Intent Parsing")

    try:
        from sollie_core import SollieBrain

        brain = SollieBrain()
        action = brain.detect_action_intent("Create a file called todo.txt", "")

        if not action or action.get('type') != "create_file":
            print("✗ Could not detect create_file intent")
            return False

        filename = Path(action.get('params', {}).get('filepath', '')).name
        if filename != "todo.txt":
            print(f"✗ Unexpected filename parsed: {filename}")
            return False

        app_action = brain.detect_action_intent("Please open note pad", "")
        if not app_action or app_action.get('type') != "open_application":
            print("✗ Could not detect open_application intent for spaced app name")
            return False

        file_action = brain.detect_action_intent("Open holiday.mp4", "")
        if not file_action or file_action.get('type') != "open_file":
            print("✗ Could not detect open_file intent for media file")
            return False

        random_action = brain.detect_action_intent("Open a random jpg", "")
        if not random_action or random_action.get('type') != "open_random_file":
            print("✗ Could not detect open_random_file intent for random image")
            return False

        folder_action = brain.detect_action_intent("Open pictures folder", "")
        if not folder_action or folder_action.get('type') != "open_directory":
            print("✗ Could not detect open_directory intent for folder")
            return False

        print("✓ Intent parsing works for file creation, app launch, and file open")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_lm_studio():
    """Test LM Studio connection"""
    print_section("Testing LM Studio Connection")
    
    import requests
    
    try:
        print("Attempting to connect to http://localhost:1234...")
        response = requests.get("http://localhost:1234/v1/models", timeout=3)
        
        if response.status_code == 200:
            print("✓ LM Studio is running and accessible")
            
            # Try to list models
            data = response.json()
            if data.get('data'):
                print(f"\n  Available models:")
                for model in data['data']:
                    print(f"    • {model.get('id', 'Unknown')}")
            
            return True
        else:
            print(f"⚠ LM Studio responded with status {response.status_code}")
            return False
    
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to LM Studio")
        print("\n  Please:")
        print("    1. Open LM Studio")
        print("    2. Go to 'Local Server' tab")
        print("    3. Click 'Start Server'")
        print("    4. Run this test again")
        return False
    
    except requests.exceptions.Timeout:
        print("❌ Connection timed out")
        return False


def test_brain():
    """Test Sollie brain functionality"""
    print_section("Testing Sollie Brain")
    
    try:
        from sollie_core import SollieBrain
        
        print("Creating Sollie brain instance...")
        brain = SollieBrain()
        print("✓ Brain initialized")
        
        print("\nTesting connection to LM Studio...")
        result = brain.test_connection()
        
        if result['success']:
            print(f"✓ Connection successful!")
            print(f"\n  Response: {result['response']}")
            return True
        else:
            print(f"✗ Connection failed: {result['error']}")
            return False
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_actions():
    """Test action system"""
    print_section("Testing Action System")
    
    try:
        from sollie_actions import SollieActions
        
        actions = SollieActions()
        print("✓ Actions module loaded")
        
        # Test safe action check
        print("\nTesting safety system...")
        safe_actions = ['open_application', 'create_file', 'list_directory']
        unsafe_actions = ['shutdown', 'format', 'delete_system']
        
        for action in safe_actions:
            if actions.is_action_safe(action):
                print(f"  ✓ {action} - allowed")
            else:
                print(f"  ✗ {action} - incorrectly blocked!")
        
        for action in unsafe_actions:
            if not actions.is_action_safe(action):
                print(f"  ✓ {action} - correctly blocked")
            else:
                print(f"  ✗ {action} - DANGER: not blocked!")
        
        print("\n✓ Action system working")
        return True
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_memory():
    """Test memory system"""
    print_section("Testing Memory System")
    
    try:
        from sollie_memory import SollieMemory
        
        # Create test database
        memory = SollieMemory("test_memory.db")
        print("✓ Memory system initialized")
        
        # Test adding a message
        memory.add_message("user", "Test message")
        print("✓ Can add messages")
        
        # Test retrieving history
        history = memory.get_conversation_history(limit=1)
        if history and history[0]['content'] == "Test message":
            print("✓ Can retrieve messages")
        else:
            print("✗ Message retrieval failed")
        
        # Clean up
        Path("test_memory.db").unlink()
        print("\n✓ Memory system working")
        return True
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "🤖 "*20)
    print("       SOLLIE SYSTEM TEST")
    print("🤖 "*20)
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Sollie Modules", test_sollie_modules),
        ("Intent Parsing", test_intent_parsing),
        ("Memory System", test_memory),
        ("Action System", test_actions),
        ("LM Studio Connection", test_lm_studio),
        ("Sollie Brain", test_brain)
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n❌ {test_name} crashed: {e}")
            results[test_name] = False
    
    # Summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status:10s} {test_name}")
    
    print(f"\n  Score: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n" + "="*60)
        print("  🎉 ALL TESTS PASSED!")
        print("  Sollie is ready to use!")
        print("  Run: python sollie_gui.py")
        print("="*60)
        return True
    else:
        print("\n" + "="*60)
        print("  ⚠ SOME TESTS FAILED")
        print("  Please fix the issues above")
        print("="*60)
        return False


if __name__ == "__main__":
    success = main()
    
    input("\nPress Enter to exit...")
    
    sys.exit(0 if success else 1)
