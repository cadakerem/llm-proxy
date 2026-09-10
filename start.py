import subprocess
import sys
import time
import os
import atexit

def main():
    print("🚀 Starting Claude Proxy in the background...")
    
    # Start the proxy in the background, hiding its output so it doesn't clutter the terminal
    proxy_process = subprocess.Popen(
        [sys.executable, "src/main.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    # Ensure the proxy is killed when this script exits
    def cleanup():
        print("\n🛑 Shutting down Claude Proxy...")
        proxy_process.terminate()
        proxy_process.wait()
        
    atexit.register(cleanup)

    # Give the proxy a brief moment to bind to the port (8082)
    time.sleep(1.5)

    # Check if proxy crashed immediately
    if proxy_process.poll() is not None:
        print("❌ Error: Proxy failed to start. Check if port 8082 is in use.")
        sys.exit(1)

    print("✅ Proxy is running! Launching Claude CLI...\n" + "="*50 + "\n")
    
    # Create a dummy config to bypass the login prompt in Claude CLI (LOCAL USE ONLY)
    claude_config_path = os.path.expanduser("~/.claude.json")
    try:
        if not os.path.exists(claude_config_path):
            with open(claude_config_path, "w") as f:
                import json
                json.dump({
                    "primaryApiKey": "sk-ant-api03-dummy-key",
                    "hasCompletedOnboarding": True
                }, f)
            print(f"🔒 Local Auth Bypass enabled: Fake config injected at {claude_config_path}")
    except Exception as e:
        print(f"Warning: Could not write dummy config to {claude_config_path}: {e}")

    # Prepare environment variables for Claude CLI
    env = os.environ.copy()
    env["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:8082"
    
    # Run the official claude CLI in the foreground
    try:
        subprocess.run(["claude"], env=env, shell=True)
    except KeyboardInterrupt:
        pass # Handle Ctrl+C gracefully without throwing massive python errors
    
if __name__ == "__main__":
    main()
