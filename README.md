# Smart Router (CLI Delegation Tool)

> A lightweight, fault-tolerant CLI tool for delegating LLM tasks to expert models across multiple providers (Nvidia NIM, Groq, OpenAI, Anthropic Claude, Gemini).

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![CI](https://github.com/cadakerem/smart-router/actions/workflows/ci.yml/badge.svg)

## ⚡ Features

- **Multi-Provider Support:** seamlessly route requests to `nvidia`, `groq`, `openai`, `anthropic`, or `gemini`.
- **Automatic Fallbacks:** Provide a comma-separated list of models. If one fails, it instantly falls back to the next.
- **Circuit Breaker:** Built-in health tracking and cooldowns to prevent spamming dead endpoints.
- **Reasoning Extraction:** Automatically extracts and formats hidden `<thought>` or `reasoning` blocks (e.g., from Nemotron or DeepSeek).
- **Streaming Native:** Built on the official OpenAI SDK for fast and reliable streaming chunks.

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/cadakerem/smart-router.git
cd smart-router

# Install dependencies
pip install -r requirements.txt
```

### Setup API Keys
The router checks for a `keys.json` file in the same directory, or falls back to system environment variables.

**Option 1: keys.json**
Create a `keys.json` file in the root directory:
```json
{
  "NVIDIA_API_KEY": "nvapi-...",
  "GROQ_API_KEY": "gsk_...",
  "OPENAI_API_KEY": "sk-...",
  "ANTHROPIC_API_KEY": "sk-ant-...",
  "GEMINI_API_KEY": "AIza..."
}
```

**Option 2: Environment Variables**
```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GEMINI_API_KEY="AIza..."
export NVIDIA_API_KEY="nvapi-..."
export GROQ_API_KEY="gsk_..."
```

## 💻 Usage

```bash
python smart_router.py -m "<provider:model1>,<provider:model2>" -p "<your prompt>"
```

You can also read prompts from a file or via standard input:
```bash
python smart_router.py -m "nvidia:nemotron,groq:llama3" -f prompt.txt
cat logs.txt | python smart_router.py -m "groq:llama3"
```

### Examples

**Heavy Coding Task (Nvidia Laguna -> Groq Fallback):**
```bash
python smart_router.py -m "nvidia:poolside/laguna-xs-2.1,groq:groq/compound" -p "Write a python script to parse logs."
```

**Custom Cooldown and Project ID:**
```bash
python smart_router.py -m "groq:llama3" -p "Hello" --project "agent-core" --max-failures 3 --cooldown 300
```

## 🏗️ Architecture Overview

The router uses a `FileLock`-backed JSON state (`circuit_breaker.json`) to track failures across concurrent runs. 
If an endpoint times out or returns a 5xx error more than `MAX_FAILURES` times, the circuit trips and forces the router to skip that endpoint for the next 120 seconds, immediately trying the next fallback model.
