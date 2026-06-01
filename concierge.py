import os
import requests
import json
from typing import Optional, Tuple, List, Dict

class ConciergeClient:
    """
    The Interchangeable Concierge API.
    Orchestrates queries across local and remote multimodal LLMs.
    """
    def __init__(self):
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

    def generate(self, prompt: str, provider: str = "ollama", model: str = None, system: str = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Unified generate method.
        Providers: 'ollama', 'gemini', 'openai', 'anthropic'
        """
        if provider == "ollama":
            return self._query_ollama(prompt, model or "deepseek-r1:1.5b", system)
        elif provider == "gemini":
            return self._query_gemini(prompt, model or "gemini-1.5-pro", system)
        elif provider == "openai":
            return self._query_openai(prompt, model or "gpt-4o", system)
        elif provider == "anthropic":
            return self._query_anthropic(prompt, model or "claude-3-5-sonnet-20240620", system)
        else:
            return None, f"Unknown provider: {provider}"

    def _query_ollama(self, prompt: str, model: str, system: str) -> Tuple[Optional[str], Optional[str]]:
        try:
            payload = {"model": model, "prompt": prompt, "stream": False}
            if system: payload["system"] = system
            resp = requests.post(f"{self.ollama_host}/api/generate", json=payload, timeout=120)
            resp.raise_for_status()
            return resp.json().get("response", ""), None
        except Exception as e:
            return None, f"Ollama Error: {e}"

    def _query_gemini(self, prompt: str, model: str, system: str) -> Tuple[Optional[str], Optional[str]]:
        if not self.google_api_key: return None, "Missing GOOGLE_API_KEY"
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.google_api_key}"
            contents = [{"parts": [{"text": prompt}]}]
            if system:
                # Gemini system instruction structure
                payload = {"contents": contents, "system_instruction": {"parts": [{"text": system}]}}
            else:
                payload = {"contents": contents}
            
            resp = requests.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data['candidates'][0]['content']['parts'][0]['text'], None
        except Exception as e:
            return None, f"Gemini Error: {e}"

    def _query_openai(self, prompt: str, model: str, system: str) -> Tuple[Optional[str], Optional[str]]:
        if not self.openai_api_key: return None, "Missing OPENAI_API_KEY"
        try:
            messages = []
            if system: messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.openai_api_key}"},
                json={"model": model, "messages": messages},
                timeout=60
            )
            resp.raise_for_status()
            return resp.json()['choices'][0]['message']['content'], None
        except Exception as e:
            return None, f"OpenAI Error: {e}"

    def _query_anthropic(self, prompt: str, model: str, system: str) -> Tuple[Optional[str], Optional[str]]:
        if not self.anthropic_api_key: return None, "Missing ANTHROPIC_API_KEY"
        try:
            payload = {
                "model": model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}]
            }
            if system: payload["system"] = system
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json=payload,
                timeout=60
            )
            resp.raise_for_status()
            return resp.json()['content'][0]['text'], None
        except Exception as e:
            return None, f"Anthropic Error: {e}"

# Global instance
concierge = ConciergeClient()
