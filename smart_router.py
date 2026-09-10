import sys
import os
import json
import time
import random
from openai import OpenAI
from filelock import FileLock, Timeout

# Optional import for anthropic
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

# Paths and configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CIRCUIT_FILE = os.path.join(SCRIPT_DIR, "circuit_breaker.json")
LOCK_FILE = os.path.join(SCRIPT_DIR, "circuit_breaker.json.lock")
COOLDOWN_SECONDS = 120
MAX_FAILURES = 2

# API Keys Configuration
KEYS_FILE = os.path.join(SCRIPT_DIR, "keys.json")

def get_api_key(provider):
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE, 'r') as f:
                keys = json.load(f)
                env_name = f"{provider.upper()}_API_KEY"
                if keys.get(env_name):
                    return keys[env_name]
        except Exception as e:
            pass
    return os.environ.get(f"{provider.upper()}_API_KEY")

NVIDIA_API_KEY = get_api_key("NVIDIA")
OPENAI_API_KEY = get_api_key("OPENAI")
GROQ_API_KEY = get_api_key("GROQ")
GEMINI_API_KEY = get_api_key("GEMINI")
ANTHROPIC_API_KEY = get_api_key("ANTHROPIC")

PROVIDERS = {
    "nvidia": {"base_url": "https://integrate.api.nvidia.com/v1", "api_key": NVIDIA_API_KEY},
    "openai": {"base_url": "https://api.openai.com/v1", "api_key": OPENAI_API_KEY},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "api_key": GROQ_API_KEY},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "api_key": GEMINI_API_KEY},
    "anthropic": {"api_key": ANTHROPIC_API_KEY} # anthropic uses its own SDK
}

def load_circuit():
    for _ in range(3):
        if os.path.exists(CIRCUIT_FILE):
            try:
                with open(CIRCUIT_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                time.sleep(random.uniform(0.01, 0.05))
    return {}

def save_circuit(data):
    for _ in range(3):
        try:
            current_time = time.time()
            active_data = {
                k: v for k, v in data.items()
                if v.get('failures', 0) > 0 or v.get('cooldown_until', 0) > current_time
            }
            
            if not active_data:
                if os.path.exists(CIRCUIT_FILE):
                    os.remove(CIRCUIT_FILE)
                return
                
            with open(CIRCUIT_FILE, 'w') as f:
                json.dump(active_data, f)
            break
        except:
            time.sleep(random.uniform(0.01, 0.05))

def check_health(model_id):
    try:
        with FileLock(LOCK_FILE, timeout=5):
            circuit = load_circuit()
            if model_id in circuit:
                stats = circuit[model_id]
                if stats.get('cooldown_until', 0) > time.time():
                    return False
            return True
    except Timeout:
        print(f"[*] Timeout acquiring lock for {model_id} health check. Assuming healthy.")
        return True

def record_failure(model_id):
    try:
        with FileLock(LOCK_FILE, timeout=5):
            circuit = load_circuit()
            if model_id not in circuit:
                circuit[model_id] = {'failures': 0, 'cooldown_until': 0}
            
            circuit[model_id]['failures'] += 1
            
            if circuit[model_id]['failures'] >= MAX_FAILURES:
                circuit[model_id]['cooldown_until'] = time.time() + COOLDOWN_SECONDS
                circuit[model_id]['failures'] = 0
                print(f"[CIRCUIT BREAKER] {model_id} tripped! Cooling down for {COOLDOWN_SECONDS}s.")
                
            save_circuit(circuit)
    except Timeout:
        print(f"[*] Timeout acquiring lock. Could not record failure for {model_id}.")

def record_success(model_id):
    try:
        with FileLock(LOCK_FILE, timeout=5):
            circuit = load_circuit()
            if model_id in circuit and circuit[model_id]['failures'] > 0:
                circuit[model_id]['failures'] = 0
                save_circuit(circuit)
    except Timeout:
        pass

def parse_model(model_string):
    if ":" in model_string:
        provider, model = model_string.split(":", 1)
        return provider.strip().lower(), model.strip()
    return "nvidia", model_string.strip()

def query_ai(models_list, prompt, max_retries=2, base_timeout=30):
    if isinstance(models_list, str):
        models_list = [m.strip() for m in models_list.split(',')]
        
    for current_model_str in models_list:
        provider, current_model = parse_model(current_model_str)
        
        if not check_health(current_model_str):
            print(f"[!] Health Check Failed: {current_model_str} is in cooldown. Skipping...")
            continue
            
        provider_config = PROVIDERS.get(provider)
        if not provider_config or not provider_config.get("api_key"):
            print(f"[!] Provider '{provider}' not configured or missing API key. Skipping {current_model_str}...")
            continue
            
        is_nemotron = "nemotron" in current_model.lower()
        model_timeout = 90 if is_nemotron else base_timeout
            
        for attempt in range(max_retries):
            try:
                full_reasoning = ""
                full_content = ""

                # --- ANTHROPIC LOGIC ---
                if provider == "anthropic":
                    if not HAS_ANTHROPIC:
                        raise ImportError("Anthropic package is missing. 'pip install anthropic' is required.")
                        
                    client = anthropic.Anthropic(
                        api_key=provider_config["api_key"],
                        timeout=model_timeout
                    )
                    with client.messages.stream(
                        model=current_model,
                        max_tokens=4096,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7
                    ) as stream:
                        for text in stream.text_stream:
                            full_content += text

                # --- OPENAI / NVIDIA / GROQ / GEMINI LOGIC ---
                else:
                    client = OpenAI(
                        base_url=provider_config["base_url"],
                        api_key=provider_config["api_key"],
                        timeout=model_timeout
                    )
                    
                    extra_body = {}
                    if provider == "nvidia" and "nemotron" in current_model.lower():
                        extra_body = {"chat_template_kwargs": {"enable_thinking": True}}
                        
                    completion = client.chat.completions.create(
                        model=current_model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7,
                        max_tokens=4096,
                        extra_body=extra_body if extra_body else None,
                        stream=True
                    )
                    
                    for chunk in completion:
                        if not chunk.choices:
                            continue
                        reasoning = getattr(chunk.choices[0].delta, "reasoning_content", None)
                        if reasoning:
                            full_reasoning += reasoning
                            
                        content = chunk.choices[0].delta.content
                        if content:
                            full_content += content
                            
                record_success(current_model_str)
                
                output = ""
                if full_reasoning:
                    output += f"--- REASONING ({current_model_str}) ---\n{full_reasoning}\n--- END REASONING ---\n\n"
                output += full_content
                
                return output
                
            except Exception as e:
                error_msg = str(e).lower()
                print(f"[*] Attempt {attempt+1} failed for {current_model_str}: {str(e)}")
                
                record_failure(current_model_str)
                
                if "404" in error_msg or "not found" in error_msg or "auth" in error_msg:
                    break 
                    
                if attempt == max_retries - 1:
                    break 
                
                sleep_time = (2 ** attempt) + random.uniform(0.1, 1.5)
                time.sleep(sleep_time)
                
    return "[ERROR] All fallback models failed, timed out, or are in cooldown."

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python smart_router.py <provider:model1,provider:model2> <prompt>")
        sys.exit(1)
        
    model_arg = sys.argv[1]
    user_prompt = " ".join(sys.argv[2:])
    
    response = query_ai(model_arg, user_prompt)
    print(response)