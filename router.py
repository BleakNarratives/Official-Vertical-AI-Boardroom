#!/usr/bin/env python3
"""
VERTICAL AI -- Model Router
Groq handles boardroom agents. Gemini reserved for Chairman only.
Ollama catches everything offline. No faking. No placeholders.
"""

import os
import time
import requests
from enum import Enum

class ModelTier(Enum):
    BOARDROOM = "boardroom"
    FAST = "fast"
    CODE = "code"
    CHAIRMAN = "chairman"

OLLAMA_URI = os.environ.get("OLLAMA_URI", "http://127.0.0.1:11434")
OLLAMA_MODELS = {
    ModelTier.BOARDROOM: os.environ.get("OLLAMA_BOARDROOM_MODEL", "deepseek-r1:1.5b"),
    ModelTier.FAST: os.environ.get("OLLAMA_FAST_MODEL", "llama3.2:1b"),
    ModelTier.CODE: os.environ.get("OLLAMA_CODE_MODEL", "qwen2.5-coder:1.5b"),
    ModelTier.CHAIRMAN: os.environ.get("OLLAMA_BOARDROOM_MODEL", "deepseek-r1:1.5b"),
}

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"


def _call_gemini(prompt: str, system: str = None) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")
    contents = []
    if system:
        contents.append({"role": "user", "parts": [{"text": f"[SYSTEM CONTEXT]\n{system}"}]})
        contents.append({"role": "model", "parts": [{"text": "Understood."}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})
    resp = requests.post(
        f"{GEMINI_URL}?key={GEMINI_API_KEY}",
        json={"contents": contents},
        timeout=60
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def _call_groq(prompt: str, system: str = None) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={"model": GROQ_MODEL, "messages": messages, "temperature": 0.7},
        timeout=60
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_ollama(prompt: str, system: str = None, tier: ModelTier = ModelTier.FAST) -> str:
    model = OLLAMA_MODELS[tier]
    payload = {
        "model": model,
        "prompt": f"{system}\n\n{prompt}" if system else prompt,
        "stream": False
    }
    resp = requests.post(f"{OLLAMA_URI}/api/generate", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["response"]


def call_model(prompt: str, system: str = None, tier: ModelTier = ModelTier.FAST, chairman: bool = False) -> tuple[str, str]:
    """
    Routing:
      chairman=True  -> Gemini (the one reserved call) -> Groq fallback
      BOARDROOM      -> Groq -> Ollama (Gemini stays cold)
      FAST/CODE      -> Groq -> Gemini -> Ollama
    """
    errors = []

    if chairman:
        try:
            return _call_gemini(prompt, system), "gemini/chairman"
        except Exception as e:
            errors.append(f"Gemini: {e}")
        try:
            return _call_groq(prompt, system), "groq/chairman-fallback"
        except Exception as e:
            errors.append(f"Groq: {e}")
        raise RuntimeError("Chairman failed:\n" + "\n".join(errors))

    if tier == ModelTier.BOARDROOM:
        time.sleep(1)
        try:
            return _call_groq(prompt, system), "groq"
        except Exception as e:
            errors.append(f"Groq: {e}")
        try:
            return _call_ollama(prompt, system, tier), f"ollama/{OLLAMA_MODELS[tier]}"
        except Exception as e:
            errors.append(f"Ollama: {e}")
        raise RuntimeError("Boardroom failed:\n" + "\n".join(errors))

    try:
        return _call_groq(prompt, system), "groq"
    except Exception as e:
        errors.append(f"Groq: {e}")
    try:
        return _call_gemini(prompt, system), "gemini"
    except Exception as e:
        errors.append(f"Gemini: {e}")
    try:
        return _call_ollama(prompt, system, tier), f"ollama/{OLLAMA_MODELS[tier]}"
    except Exception as e:
        errors.append(f"Ollama: {e}")

    raise RuntimeError("All providers failed:\n" + "\n".join(errors))


def check_providers() -> dict:
    status = {}
    status["gemini"] = bool(GEMINI_API_KEY)
    status["groq"] = bool(GROQ_API_KEY)
    try:
        resp = requests.get(f"{OLLAMA_URI}/api/tags", timeout=5)
        status["ollama"] = [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        status["ollama"] = False
    return status

# Concierge fallback -- drops in when Groq/Gemini rate limit
import sys
sys.path.insert(0, '/storage/emulated/0/RootBase/src/swarm/molt')

def call_model_with_concierge(prompt, system=None, tier=None, chairman=False):
    """Try router first, fall back to Concierge/Anthropic."""
    try:
        return call_model(prompt, system=system, tier=tier, chairman=chairman)
    except RuntimeError as e:
        if '429' in str(e) or '413' in str(e):
            try:
                from concierge import ConciergeClient
                c = ConciergeClient()
                result, err = c.generate(prompt, provider='anthropic', system=system)
                if result:
                    return result, 'claude-anthropic'
                result, err = c.generate(prompt, provider='gemini', system=system)
                if result:
                    return result, 'gemini-fallback'
            except Exception as ce:
                raise RuntimeError(f"All providers failed: {e} | Concierge: {ce}")
        raise
