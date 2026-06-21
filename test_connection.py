#!/usr/bin/env python3
"""Quick sanity-check: ping each installed Ollama model."""

import json
import urllib.request

OLLAMA_BASE = "http://localhost:11434"


def list_models():
    req = urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags")
    return json.loads(req.read())["models"]


def chat(model: str, prompt: str) -> str:
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())["response"]


if __name__ == "__main__":
    models = list_models()
    print(f"Found {len(models)} model(s):\n")
    for m in models:
        name = m["name"]
        size_gb = m["size"] / 1e9
        print(f"  {name}  ({size_gb:.1f} GB)")
        answer = chat(name, "Reply in one sentence: what model are you?")
        print(f"  → {answer.strip()}\n")
