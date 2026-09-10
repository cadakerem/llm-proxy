---
name: llm-proxy
description: >-
  A lightweight proxy to translate Anthropic Messages API format into standard OpenAI Chat Completions format.
  Allows agents like Claude Code or Antigravity to run using models from Groq, Nvidia NIM, Ollama, etc.
---

# LLM Proxy Skill

This skill provides a lightweight (localhost) translation proxy. Agents that are hardcoded to use the Anthropic API can use this proxy to connect to OpenAI-compatible providers like Groq, Nvidia NIM, or local Ollama instances.

## How it works
1. The proxy runs locally using FastAPI.
2. It intercepts the Anthropic `Messages API` payload.
3. Translates the payload into standard `OpenAI Chat Completions` format on the fly.
4. Forwards the request to the configured provider (e.g., Groq, OpenAI).
5. Translates the response back to Anthropic's format.

## Usage for Agents
If you need to start the proxy on behalf of the user, you can run:
```bash
# Ensure dependencies are installed
pip install -r requirements.txt

# Start the proxy
python start.py
```
This will start the FastAPI proxy and output the necessary environment variable (e.g., `ANTHROPIC_BASE_URL=http://127.0.0.1:8000`) that needs to be set for the agent to use it.
