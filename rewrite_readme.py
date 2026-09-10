import os

readme_content = """# Smart Router (CLI Delegation Tool)

> A lightweight, fault-tolerant CLI tool for delegating LLM tasks to expert models across multiple providers (Nvidia NIM, Groq, OpenAI, Anthropic Claude, Gemini).

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)

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

Run the router from the CLI. The first argument is your model fallback chain, and the rest is your prompt.

```bash
python smart_router.py "<provider:model1>,<provider:model2>" "<your prompt>"
```

### Examples

**Heavy Coding Task (Nvidia Laguna -> Groq Fallback):**
```bash
python smart_router.py "nvidia:poolside/laguna-xs-2.1,groq:groq/compound" "Write a python script to parse logs."
```

**Complex Reasoning (Nemotron -> Kimi):**
```bash
python smart_router.py "nvidia:nvidia/nemotron-3-super-120b-a12b,nvidia:moonshotai/kimi-k3" "Solve this logic puzzle..."
```

## 🏗️ Architecture Overview

The router uses a `FileLock`-backed JSON state (`circuit_breaker.json`) to track failures across concurrent runs. 
If an endpoint times out or returns a 5xx error more than `MAX_FAILURES` times, the circuit trips and forces the router to skip that endpoint for the next 120 seconds, immediately trying the next fallback model.
"""

with open("README.md", 'w', encoding='utf-8') as f:
    f.write(readme_content)