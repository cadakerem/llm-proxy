# LLM Proxy (API Translation Layer)

A simple, lightweight (~140 lines) translation layer that converts Anthropic's `Messages API` format into standard `OpenAI Chat Completions` format.

This allows developers to experiment with the official `claude` CLI using alternative local or remote models (like OpenAI, Nvidia NIM, or Ollama) for educational and testing purposes.

## ğŸ›‘ Technical Realities & Limitations

While this proxy is lightweight, it is currently a **naive, proof-of-concept implementation**. If you intend to use this for real engineering work, you must understand the following gaps:

- **TOS Gray Area:** While using `ANTHROPIC_BASE_URL` is an officially supported mechanism for enterprise routing, explicitly using it to bypass Anthropic's ecosystem and proxy to third-party models is an undefined gray area in their Terms of Service.
- **No Streaming (SSE) Support:** Claude Code expects Server-Sent Events (SSE) to render output token-by-token. This 150-line proxy currently waits for the full response before replying (blocking). This breaks the CLI's native UI experience and can lead to timeouts.
- **Tool-Calling Translation is Missing:** Anthropic and OpenAI handle tool calls fundamentally differently (Anthropic uses `content` blocks with `type: tool_use`; OpenAI uses a dedicated `tool_calls` array). This proxy currently strips out complex tool schemas. **Claude Code's agentic features (reading files, running bash) will not work until a robust two-way tool translation layer is built.**
- **Fallback Mid-Stream:** The current fallback mechanism only works if the initial HTTP request fails. If a provider fails mid-stream (which is common), silent fallbacks are architecturally impossible without resetting the client UI.

## ğŸ”’ Security Note (Network Binding)
By default, the FastAPI server binds strictly to `127.0.0.1` (localhost). **Do not change this to `0.0.0.0`.** If you do, anyone on your local network (e.g., public WiFi, office LAN) can discover the proxy and route requests through your API keys.

## âœ¨ Features

- **Fallback Chains:** You can configure ordered fallback lists for resilience if a provider API fails.
- **Concurrent Support:** Built on an asynchronous (FastAPI + HTTPX) architecture, handling multiple parallel agent requests without blocking the terminal.
- **100% Transparent:** The entire core translation logic is just a single file (`src/main.py`).

## ğŸ› ï¸ Architecture

1. **Leverages Official Routing:** Uses the officially supported `ANTHROPIC_BASE_URL` environment variable (designed by Anthropic for enterprise gateways) to route traffic to the `localhost` proxy.
2. Intercepts Anthropic's `Messages API` payload.
3. Translates the payload into standard `OpenAI Chat Completions` format on the fly.
4. Forwards it to configured providers like **Groq**, **Nvidia NIM**, or **OpenAI**.
5. Translates the response back to Anthropic's format.

## ğŸ“¦ Installation

```bash
# Clone the repository
git clone https://github.com/cadakerem/llm-proxy.git
cd llm-proxy

# Install requirements
pip install -r requirements.txt
```

## ğŸ® Usage

The project includes a unified launcher.

**Configure and Run:**
```bash
# Rename the example env file and add your keys
mv .env.example .env

# Start the proxy and the CLI
python start.py
```

**What `start.py` does automatically:**
1. Starts the FastAPI proxy in the background silently.
2. Sets the `ANTHROPIC_BASE_URL` routing variable.
3. Launches the official `claude` CLI in your terminal.
4. Cleanly shuts down the background proxy when you exit Claude.

## ğŸ¤ Contributing
Keep it simple. Security and minimalism are our top priorities.

## ğŸ“œ License
[MIT License](LICENSE)
