# LLM Proxy (API Translation Layer)

A translation layer that converts Anthropic's `Messages API` format into standard `OpenAI Chat Completions` format on the fly.

This allows developers to seamlessly use **Antigravity** or **Claude Code** with alternative local or remote models (like OpenAI, Nvidia NIM, Groq, or Ollama) with full agentic capabilities.

## Features

- **Full SSE Streaming:** Real-time token-by-token output. Prevents timeouts and preserves the native CLI UI experience.
- **Two-Way Tool Calling:** Translates Anthropic's JSON Schema tools into OpenAI functions, and maps OpenAI's `tool_calls` back to Anthropic `tool_use` blocks. (Agents can read files, run bash, etc.)
- **Fallback Chains:** You can configure ordered fallback lists for resilience if a provider API fails.
- **Concurrent Support:** Built on an asynchronous (FastAPI + HTTPX) architecture, handling multiple parallel agent requests without blocking the terminal.
- **100% Transparent:** The entire core translation logic is just a single file (`src/main.py`).

## Technical Realities
- **TOS Gray Area:** While using `ANTHROPIC_BASE_URL` is an officially supported mechanism for enterprise gateways, explicitly using it to bypass Anthropic's ecosystem and proxy to third-party models is an undefined gray area in their Terms of Service. Use for educational and testing purposes.
- **Fallback Mid-Stream:** The current fallback mechanism only works if the initial HTTP request fails. If a provider fails mid-stream (which is common), silent fallbacks are architecturally impossible without resetting the client UI.

## Security Note (Network Binding)
By default, the FastAPI server binds strictly to `127.0.0.1` (localhost). **Do not change this to `0.0.0.0`.** If you do, anyone on your local network (e.g., public WiFi, office LAN) can discover the proxy and route requests through your API keys.

## Installation as an Antigravity SKILL

If you want to use this project as a **SKILL** in Antigravity or similar AI assistants, you can clone the repository directly into your skills directory.

**Global installation (applies to all projects):**
```bash
git clone https://github.com/cadakerem/llm-proxy.git ~/.gemini/config/skills/llm-proxy
```

**Project-specific installation:**
```bash
mkdir -p .agents/skills
git clone https://github.com/cadakerem/llm-proxy.git .agents/skills/llm-proxy
```

## Standard Installation (Standalone)

```bash
# Clone the repository
git clone https://github.com/cadakerem/llm-proxy.git
cd llm-proxy

# Install requirements
pip install -r requirements.txt
```

## Usage

**Configure and Run:**
```bash
# Rename the example env file and add your keys
mv .env.example .env

# Start the proxy and the CLI
python start.py
```

## Contributing
Contributions are welcome.

## License
[MIT License](LICENSE)
