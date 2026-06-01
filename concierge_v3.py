#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
CONCIERGE v3.0 -- The Interchangeable Concierge
Multi-provider LLM orchestrator with intelligent failover, cost optimization,
and free-tier discovery for the Vertical AI Boardroom.

Usage:
    from concierge import concierge, ProviderTier, ModelCapability

    # Simple call with auto-failover
    text, error = concierge.generate("Analyze this market...")

    # Tiered routing (free -> cheap -> premium)
    text, error = concierge.generate(
        prompt, 
        tier=ProviderTier.FREE,
        required_capabilities=[ModelCapability.REASONING]
    )

    # Direct provider with fallback chain
    text, error = concierge.generate(
        prompt,
        provider="openrouter",
        fallback_chain=["groq", "cerebras", "ollama"]
    )

    # Check provider health
    health = concierge.health_check()

    # List all available free models
    free_models = concierge.list_free_models()
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import time
import json
import random
import hashlib
import threading
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Set, Callable, Any
from enum import Enum, auto
from collections import defaultdict
import requests


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS & CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

class ProviderTier(Enum):
    """Cost tiers for provider selection."""
    FREE = auto()      # Zero cost, rate-limited
    CHEAP = auto()     # Pay-per-token, very low cost
    STANDARD = auto()  # Mid-tier commercial APIs
    PREMIUM = auto()   # Frontier models (Claude, GPT-4, Gemini Pro)
    LOCAL = auto()     # Self-hosted / Ollama


class ModelCapability(Enum):
    """Capabilities for model matching."""
    REASONING = auto()
    CODING = auto()
    LONG_CONTEXT = auto()      # 128k+ context
    MULTIMODAL = auto()        # Vision support
    FAST = auto()              # Low latency
    CHEAP = auto()             # Lowest cost per token
    FUNCTION_CALLING = auto()
    JSON_MODE = auto()


@dataclass
class ProviderConfig:
    """Configuration for a single provider."""
    name: str
    tier: ProviderTier
    base_url: str
    env_key: str
    models: Dict[str, Dict[str, Any]]  # model_id -> {capabilities, context, cost_per_1m}
    headers_fn: Callable[[str], Dict[str, str]]
    payload_fn: Callable[[str, str, Optional[str], Optional[str], Optional[int]], Dict]
    response_fn: Callable[[Dict], str]
    rate_limit_rpm: int = 60
    rate_limit_tpm: int = 6000
    timeout: int = 60
    health_endpoint: Optional[str] = None
    requires_credit_card: bool = False

    # Runtime state
    last_call: float = field(default=0.0)
    calls_this_minute: int = field(default=0)
    tokens_this_minute: int = field(default=0)
    consecutive_failures: int = field(default=0)
    circuit_open: bool = field(default=False)
    circuit_opened_at: float = field(default=0.0)
    total_calls: int = field(default=0)
    total_failures: int = field(default=0)
    avg_latency_ms: float = field(default=0.0)


# ═══════════════════════════════════════════════════════════════════════════════
# PROVIDER DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

# --- OpenRouter (Unified Gateway, many free models) ---
def _openrouter_headers(key: str) -> Dict:
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://buttscorp.ai",
        "X-Title": "Vertical AI Boardroom"
    }

def _openrouter_payload(model: str, prompt: str, system: Optional[str], 
                        image_url: Optional[str], max_tokens: Optional[int]) -> Dict:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    content = [{"type": "text", "text": prompt}]
    if image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url}})
    messages.append({"role": "user", "content": content})
    return {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens or 2048,
        "temperature": 0.7
    }

def _openrouter_response(data: Dict) -> str:
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        # Some free models return different structure
        if "content" in data:
            return data["content"]
        raise

# --- Groq (Fast inference, free tier) ---
def _groq_headers(key: str) -> Dict:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

def _groq_payload(model: str, prompt: str, system: Optional[str],
                  image_url: Optional[str], max_tokens: Optional[int]) -> Dict:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens or 2048,
        "temperature": 0.7
    }

def _groq_response(data: Dict) -> str:
    return data["choices"][0]["message"]["content"]

# --- Cerebras (1M tokens/day free, wafer-scale speed) ---
def _cerebras_headers(key: str) -> Dict:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

def _cerebras_payload(model: str, prompt: str, system: Optional[str],
                      image_url: Optional[str], max_tokens: Optional[int]) -> Dict:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens or 2048,
        "temperature": 0.7
    }

def _cerebras_response(data: Dict) -> str:
    return data["choices"][0]["message"]["content"]

# --- Gemini (Google, 1K req/day free via CLI) ---
def _gemini_headers(key: str) -> Dict:
    return {"Content-Type": "application/json"}

def _gemini_payload(model: str, prompt: str, system: Optional[str],
                    image_url: Optional[str], max_tokens: Optional[int]) -> Dict:
    parts = [{"text": prompt}]
    if image_url:
        parts.append({"file_data": {"mime_type": "image/jpeg", "file_uri": image_url}})
    contents = [{"parts": parts}]
    payload = {
        "contents": contents,
        "generationConfig": {"maxOutputTokens": max_tokens or 2048, "temperature": 0.7}
    }
    if system:
        payload["system_instruction"] = {"parts": [{"text": system}]}
    return payload

def _gemini_response(data: Dict) -> str:
    return data["candidates"][0]["content"]["parts"][0]["text"]

# --- Anthropic (Claude) ---
def _anthropic_headers(key: str) -> Dict:
    return {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }

def _anthropic_payload(model: str, prompt: str, system: Optional[str],
                       image_url: Optional[str], max_tokens: Optional[int]) -> Dict:
    content = [{"type": "text", "text": prompt}]
    if image_url:
        content.append({"type": "image", "source": {"type": "url", "url": image_url}})
    payload = {
        "model": model,
        "max_tokens": max_tokens or 4096,
        "messages": [{"role": "user", "content": content}]
    }
    if system:
        payload["system"] = system
    return payload

def _anthropic_response(data: Dict) -> str:
    return data["content"][0]["text"]

# --- OpenAI ---
def _openai_headers(key: str) -> Dict:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

def _openai_payload(model: str, prompt: str, system: Optional[str],
                    image_url: Optional[str], max_tokens: Optional[int]) -> Dict:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    content = [{"type": "text", "text": prompt}]
    if image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url}})
    messages.append({"role": "user", "content": content})
    return {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens or 2048,
        "temperature": 0.7
    }

def _openai_response(data: Dict) -> str:
    return data["choices"][0]["message"]["content"]

# --- Ollama (Local) ---
def _ollama_headers(key: str) -> Dict:
    return {"Content-Type": "application/json"}

def _ollama_payload(model: str, prompt: str, system: Optional[str],
                    image_url: Optional[str], max_tokens: Optional[int]) -> Dict:
    payload = {"model": model, "prompt": prompt, "stream": False}
    if system:
        payload["system"] = system
    if max_tokens:
        payload["options"] = {"num_predict": max_tokens}
    return payload

def _ollama_response(data: Dict) -> str:
    return data.get("response", "")

# --- Together AI ---
def _together_headers(key: str) -> Dict:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

def _together_payload(model: str, prompt: str, system: Optional[str],
                      image_url: Optional[str], max_tokens: Optional[int]) -> Dict:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens or 2048,
        "temperature": 0.7
    }

def _together_response(data: Dict) -> str:
    return data["choices"][0]["message"]["content"]

# --- Fireworks AI ---
def _fireworks_headers(key: str) -> Dict:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

def _fireworks_payload(model: str, prompt: str, system: Optional[str],
                       image_url: Optional[str], max_tokens: Optional[int]) -> Dict:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return {
        "model": f"accounts/fireworks/models/{model}",
        "messages": messages,
        "max_tokens": max_tokens or 2048,
        "temperature": 0.7
    }

def _fireworks_response(data: Dict) -> str:
    return data["choices"][0]["message"]["content"]

# --- DeepSeek (Direct API, very cheap) ---
def _deepseek_headers(key: str) -> Dict:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

def _deepseek_payload(model: str, prompt: str, system: Optional[str],
                      image_url: Optional[str], max_tokens: Optional[int]) -> Dict:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens or 2048,
        "temperature": 0.7
    }

def _deepseek_response(data: Dict) -> str:
    return data["choices"][0]["message"]["content"]


# ═══════════════════════════════════════════════════════════════════════════════
# PROVIDER REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

PROVIDERS = {
    "openrouter": ProviderConfig(
        name="openrouter",
        tier=ProviderTier.FREE,
        base_url="https://openrouter.ai/api/v1/chat/completions",
        env_key="OPENROUTER_API_KEY",
        models={
            # Free tier models (as of May 2026)
            "deepseek/deepseek-r1:free": {
                "capabilities": {ModelCapability.REASONING, ModelCapability.CODING, ModelCapability.LONG_CONTEXT},
                "context": 64000,
                "cost_per_1m": 0.0,
                "description": "Strong reasoning, slower but accurate"
            },
            "deepseek/deepseek-chat-v3-0324:free": {
                "capabilities": {ModelCapability.CODING, ModelCapability.LONG_CONTEXT, ModelCapability.FAST},
                "context": 64000,
                "cost_per_1m": 0.0,
                "description": "General chat, natural conversations"
            },
            "meta-llama/llama-4-maverick:free": {
                "capabilities": {ModelCapability.LONG_CONTEXT, ModelCapability.MULTIMODAL, ModelCapability.CHEAP},
                "context": 128000,
                "cost_per_1m": 0.0,
                "description": "1M context, vision support"
            },
            "meta-llama/llama-4-scout:free": {
                "capabilities": {ModelCapability.FAST, ModelCapability.LONG_CONTEXT, ModelCapability.CHEAP},
                "context": 128000,
                "cost_per_1m": 0.0,
                "description": "Fast, low-latency responses"
            },
            "qwen/qwen3-235b-a22b:free": {
                "capabilities": {ModelCapability.CODING, ModelCapability.REASONING, ModelCapability.LONG_CONTEXT},
                "context": 128000,
                "cost_per_1m": 0.0,
                "description": "Strongest free coding model"
            },
            "x-ai/grok-3-mini-beta:free": {
                "capabilities": {ModelCapability.FAST, ModelCapability.LONG_CONTEXT},
                "context": 131000,
                "cost_per_1m": 0.0,
                "description": "Fast lightweight reasoning"
            },
            "mistralai/mistral-small-3.1-24b-instruct:free": {
                "capabilities": {ModelCapability.CODING, ModelCapability.FAST, ModelCapability.CHEAP},
                "context": 128000,
                "cost_per_1m": 0.0,
                "description": "Balanced writing and coding"
            },
            "google/gemma-3-27b-it:free": {
                "capabilities": {ModelCapability.FAST, ModelCapability.CHEAP},
                "context": 128000,
                "cost_per_1m": 0.0,
                "description": "Lightweight, efficient"
            },
            # Paid tier (cheap)
            "anthropic/claude-sonnet-4-20250514": {
                "capabilities": {ModelCapability.REASONING, ModelCapability.CODING, ModelCapability.LONG_CONTEXT, ModelCapability.FUNCTION_CALLING},
                "context": 200000,
                "cost_per_1m": 3.0,
                "description": "Claude Sonnet via OpenRouter"
            },
            "openai/gpt-4.1": {
                "capabilities": {ModelCapability.REASONING, ModelCapability.CODING, ModelCapability.MULTIMODAL, ModelCapability.FUNCTION_CALLING},
                "context": 128000,
                "cost_per_1m": 2.5,
                "description": "GPT-4.1 via OpenRouter"
            },
        },
        headers_fn=_openrouter_headers,
        payload_fn=_openrouter_payload,
        response_fn=_openrouter_response,
        rate_limit_rpm=20,
        rate_limit_tpm=2000,
        timeout=90,
        requires_credit_card=False
    ),

    "groq": ProviderConfig(
        name="groq",
        tier=ProviderTier.FREE,
        base_url="https://api.groq.com/openai/v1/chat/completions",
        env_key="GROQ_API_KEY",
        models={
            "llama-3.1-8b-instant": {
                "capabilities": {ModelCapability.FAST, ModelCapability.CHEAP, ModelCapability.CODING},
                "context": 128000,
                "cost_per_1m": 0.05,
                "description": "Fastest, cheapest"
            },
            "llama-3.3-70b-versatile": {
                "capabilities": {ModelCapability.REASONING, ModelCapability.CODING, ModelCapability.LONG_CONTEXT},
                "context": 128000,
                "cost_per_1m": 0.59,
                "description": "Strong reasoning, good balance"
            },
            "llama-4-scout-17b-16e-instruct": {
                "capabilities": {ModelCapability.LONG_CONTEXT, ModelCapability.FAST},
                "context": 128000,
                "cost_per_1m": 0.50,
                "description": "Latest Llama 4 on Groq"
            },
            "deepseek-r1-distill-llama-70b": {
                "capabilities": {ModelCapability.REASONING, ModelCapability.CODING},
                "context": 128000,
                "cost_per_1m": 0.75,
                "description": "Reasoning specialist"
            },
            "qwen-3-32b": {
                "capabilities": {ModelCapability.CODING, ModelCapability.REASONING},
                "context": 128000,
                "cost_per_1m": 0.29,
                "description": "Strong coding model"
            },
            "gemma2-9b-it": {
                "capabilities": {ModelCapability.FAST, ModelCapability.CHEAP},
                "context": 8192,
                "cost_per_1m": 0.20,
                "description": "Lightweight, fast"
            },
            "whisper-large-v3-turbo": {
                "capabilities": {ModelCapability.FAST},
                "context": 0,
                "cost_per_1m": 0.04,
                "description": "Audio transcription"
            },
        },
        headers_fn=_groq_headers,
        payload_fn=_groq_payload,
        response_fn=_groq_response,
        rate_limit_rpm=30,
        rate_limit_tpm=6000,
        timeout=60,
        requires_credit_card=False
    ),

    "cerebras": ProviderConfig(
        name="cerebras",
        tier=ProviderTier.FREE,
        base_url="https://api.cerebras.ai/v1/chat/completions",
        env_key="CEREBRAS_API_KEY",
        models={
            "llama-4-scout-17b-16e-instruct": {
                "capabilities": {ModelCapability.FAST, ModelCapability.LONG_CONTEXT, ModelCapability.CHEAP},
                "context": 128000,
                "cost_per_1m": 0.0,  # Free tier
                "description": "1M tokens/day free, 2600+ tps"
            },
            "llama-3.1-70b": {
                "capabilities": {ModelCapability.REASONING, ModelCapability.CODING},
                "context": 128000,
                "cost_per_1m": 0.60,
                "description": "Strong 70B model"
            },
            "llama-3.1-8b": {
                "capabilities": {ModelCapability.FAST, ModelCapability.CHEAP},
                "context": 128000,
                "cost_per_1m": 0.10,
                "description": "Ultra-fast, ultra-cheap"
            },
            "deepseek-r1-distill-llama-70b": {
                "capabilities": {ModelCapability.REASONING},
                "context": 128000,
                "cost_per_1m": 0.0,
                "description": "Reasoning on wafer-scale"
            },
            "qwen3-32b": {
                "capabilities": {ModelCapability.CODING, ModelCapability.REASONING},
                "context": 128000,
                "cost_per_1m": 0.0,
                "description": "Multilingual coding"
            },
        },
        headers_fn=_cerebras_headers,
        payload_fn=_cerebras_payload,
        response_fn=_cerebras_response,
        rate_limit_rpm=30,
        rate_limit_tpm=1000000,  # 1M tokens/day
        timeout=60,
        requires_credit_card=False
    ),

    "gemini": ProviderConfig(
        name="gemini",
        tier=ProviderTier.PREMIUM,
        base_url="https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        env_key="GOOGLE_API_KEY",
        models={
            "gemini-2.5-flash-preview-05-20": {
                "capabilities": {ModelCapability.FAST, ModelCapability.CHEAP, ModelCapability.LONG_CONTEXT, ModelCapability.MULTIMODAL},
                "context": 1000000,
                "cost_per_1m": 0.15,
                "description": "1M context, fast, cheap"
            },
            "gemini-2.5-pro-preview-05-20": {
                "capabilities": {ModelCapability.REASONING, ModelCapability.CODING, ModelCapability.LONG_CONTEXT, ModelCapability.MULTIMODAL, ModelCapability.FUNCTION_CALLING},
                "context": 1000000,
                "cost_per_1m": 1.25,
                "description": "Best reasoning, 1M context"
            },
            "gemini-2.0-flash": {
                "capabilities": {ModelCapability.FAST, ModelCapability.CHEAP, ModelCapability.MULTIMODAL},
                "context": 1000000,
                "cost_per_1m": 0.10,
                "description": "Fast multimodal"
            },
        },
        headers_fn=_gemini_headers,
        payload_fn=_gemini_payload,
        response_fn=_gemini_response,
        rate_limit_rpm=15,
        rate_limit_tpm=1000000,
        timeout=60,
        requires_credit_card=False  # Free tier exists
    ),

    "anthropic": ProviderConfig(
        name="anthropic",
        tier=ProviderTier.PREMIUM,
        base_url="https://api.anthropic.com/v1/messages",
        env_key="ANTHROPIC_API_KEY",
        models={
            "claude-sonnet-4-20250514": {
                "capabilities": {ModelCapability.REASONING, ModelCapability.CODING, ModelCapability.LONG_CONTEXT, ModelCapability.FUNCTION_CALLING},
                "context": 200000,
                "cost_per_1m": 3.0,
                "description": "Best all-rounder, 200k context"
            },
            "claude-opus-4-7-20260416": {
                "capabilities": {ModelCapability.REASONING, ModelCapability.CODING, ModelCapability.LONG_CONTEXT},
                "context": 200000,
                "cost_per_1m": 15.0,
                "description": "Maximum reasoning power"
            },
            "claude-haiku-4-5-20260501": {
                "capabilities": {ModelCapability.FAST, ModelCapability.CHEAP},
                "context": 200000,
                "cost_per_1m": 0.25,
                "description": "Fast, cheap, lightweight"
            },
        },
        headers_fn=_anthropic_headers,
        payload_fn=_anthropic_payload,
        response_fn=_anthropic_response,
        rate_limit_rpm=50,
        rate_limit_tpm=40000,
        timeout=90,
        requires_credit_card=True
    ),

    "openai": ProviderConfig(
        name="openai",
        tier=ProviderTier.PREMIUM,
        base_url="https://api.openai.com/v1/chat/completions",
        env_key="OPENAI_API_KEY",
        models={
            "gpt-4.1": {
                "capabilities": {ModelCapability.REASONING, ModelCapability.CODING, ModelCapability.MULTIMODAL, ModelCapability.FUNCTION_CALLING, ModelCapability.LONG_CONTEXT},
                "context": 128000,
                "cost_per_1m": 2.0,
                "description": "Latest GPT, 128k context"
            },
            "gpt-4.1-mini": {
                "capabilities": {ModelCapability.CODING, ModelCapability.FAST, ModelCapability.CHEAP},
                "context": 128000,
                "cost_per_1m": 0.40,
                "description": "Fast, cheap GPT"
            },
            "o3": {
                "capabilities": {ModelCapability.REASONING, ModelCapability.CODING},
                "context": 128000,
                "cost_per_1m": 10.0,
                "description": "Reasoning specialist"
            },
        },
        headers_fn=_openai_headers,
        payload_fn=_openai_payload,
        response_fn=_openai_response,
        rate_limit_rpm=60,
        rate_limit_tpm=60000,
        timeout=90,
        requires_credit_card=True
    ),

    "ollama": ProviderConfig(
        name="ollama",
        tier=ProviderTier.LOCAL,
        base_url="{host}/api/generate",
        env_key="OLLAMA_HOST",
        models={
            "deepseek-r1:1.5b": {
                "capabilities": {ModelCapability.FAST, ModelCapability.CHEAP, ModelCapability.REASONING},
                "context": 32768,
                "cost_per_1m": 0.0,
                "description": "Tiny reasoning model"
            },
            "deepseek-r1:7b": {
                "capabilities": {ModelCapability.REASONING, ModelCapability.CODING},
                "context": 32768,
                "cost_per_1m": 0.0,
                "description": "Local reasoning"
            },
            "llama3.2:3b": {
                "capabilities": {ModelCapability.FAST, ModelCapability.CHEAP},
                "context": 128000,
                "cost_per_1m": 0.0,
                "description": "Fast local model"
            },
            "qwen2.5:7b": {
                "capabilities": {ModelCapability.CODING, ModelCapability.REASONING},
                "context": 32768,
                "cost_per_1m": 0.0,
                "description": "Strong local coding"
            },
            "phi4:14b": {
                "capabilities": {ModelCapability.REASONING, ModelCapability.CODING},
                "context": 16384,
                "cost_per_1m": 0.0,
                "description": "Microsoft local model"
            },
        },
        headers_fn=_ollama_headers,
        payload_fn=_ollama_payload,
        response_fn=_ollama_response,
        rate_limit_rpm=9999,
        rate_limit_tpm=999999,
        timeout=120,
        requires_credit_card=False
    ),

    "together": ProviderConfig(
        name="together",
        tier=ProviderTier.CHEAP,
        base_url="https://api.together.xyz/v1/chat/completions",
        env_key="TOGETHER_API_KEY",
        models={
            "meta-llama/Llama-4-Scout-17B-16E-Instruct": {
                "capabilities": {ModelCapability.FAST, ModelCapability.LONG_CONTEXT},
                "context": 128000,
                "cost_per_1m": 0.18,
                "description": "Cheap Llama 4"
            },
            "deepseek-ai/DeepSeek-V3": {
                "capabilities": {ModelCapability.CODING, ModelCapability.REASONING, ModelCapability.LONG_CONTEXT},
                "context": 64000,
                "cost_per_1m": 0.30,
                "description": "DeepSeek V3 cheap"
            },
            "Qwen/Qwen3-235B-A22B": {
                "capabilities": {ModelCapability.CODING, ModelCapability.REASONING},
                "context": 128000,
                "cost_per_1m": 0.40,
                "description": "Qwen3 cheap"
            },
        },
        headers_fn=_together_headers,
        payload_fn=_together_payload,
        response_fn=_together_response,
        rate_limit_rpm=30,
        rate_limit_tpm=100000,
        timeout=90,
        requires_credit_card=False  # $5 free credit
    ),

    "fireworks": ProviderConfig(
        name="fireworks",
        tier=ProviderTier.CHEAP,
        base_url="https://api.fireworks.ai/inference/v1/chat/completions",
        env_key="FIREWORKS_API_KEY",
        models={
            "accounts/fireworks/models/llama4-scout-instruct-basic": {
                "capabilities": {ModelCapability.FAST, ModelCapability.LONG_CONTEXT},
                "context": 128000,
                "cost_per_1m": 0.20,
                "description": "Fast structured output"
            },
            "accounts/fireworks/models/deepseek-v3": {
                "capabilities": {ModelCapability.CODING, ModelCapability.REASONING},
                "context": 64000,
                "cost_per_1m": 0.25,
                "description": "DeepSeek cheap"
            },
        },
        headers_fn=_fireworks_headers,
        payload_fn=_fireworks_payload,
        response_fn=_fireworks_response,
        rate_limit_rpm=30,
        rate_limit_tpm=100000,
        timeout=90,
        requires_credit_card=False  # Free tier available
    ),

    "deepseek": ProviderConfig(
        name="deepseek",
        tier=ProviderTier.CHEAP,
        base_url="https://api.deepseek.com/v1/chat/completions",
        env_key="DEEPSEEK_API_KEY",
        models={
            "deepseek-chat": {
                "capabilities": {ModelCapability.CODING, ModelCapability.REASONING, ModelCapability.LONG_CONTEXT},
                "context": 64000,
                "cost_per_1m": 0.14,
                "description": "DeepSeek V3, very cheap"
            },
            "deepseek-reasoner": {
                "capabilities": {ModelCapability.REASONING, ModelCapability.CODING},
                "context": 64000,
                "cost_per_1m": 0.55,
                "description": "DeepSeek R1 reasoning"
            },
        },
        headers_fn=_deepseek_headers,
        payload_fn=_deepseek_payload,
        response_fn=_deepseek_response,
        rate_limit_rpm=60,
        rate_limit_tpm=50000,
        timeout=120,
        requires_credit_card=False
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# CONCIERGE CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

class ConciergeClient:
    """
    Intelligent multi-provider LLM client with:
    - Automatic failover across providers
    - Cost-aware model selection
    - Circuit breaker pattern for reliability
    - Rate limit tracking and backoff
    - Capability-based model matching
    - Health monitoring and diagnostics
    """

    CIRCUIT_BREAKER_THRESHOLD = 5
    CIRCUIT_BREAKER_RESET_SEC = 300
    RATE_LIMIT_BACKOFF_SEC = 60

    def __init__(self):
        self.providers: Dict[str, ProviderConfig] = {}
        self._lock = threading.RLock()
        self._load_providers()
        self._start_maintenance()

    def _load_providers(self):
        """Initialize providers from environment."""
        for name, config in PROVIDERS.items():
            key = os.getenv(config.env_key)
            if key or config.tier == ProviderTier.LOCAL:
                self.providers[name] = config
                # For Ollama, store the host URL in the key field
                if name == "ollama":
                    config.base_url = key or "http://127.0.0.1:11434"

    def _start_maintenance(self):
        """Start background maintenance thread."""
        def maint():
            while True:
                time.sleep(60)
                self._reset_rate_limits()
                self._check_circuits()
        t = threading.Thread(target=maint, daemon=True)
        t.start()

    def _reset_rate_limits(self):
        """Reset per-minute counters."""
        with self._lock:
            for p in self.providers.values():
                p.calls_this_minute = 0
                p.tokens_this_minute = 0

    def _check_circuits(self):
        """Check if circuit breakers should reset."""
        now = time.time()
        with self._lock:
            for p in self.providers.values():
                if p.circuit_open and (now - p.circuit_opened_at) > self.CIRCUIT_BREAKER_RESET_SEC:
                    p.circuit_open = False
                    p.consecutive_failures = 0

    def _is_rate_limited(self, provider: ProviderConfig, estimated_tokens: int = 1000) -> bool:
        """Check if provider is currently rate limited."""
        if provider.circuit_open:
            return True
        if provider.calls_this_minute >= provider.rate_limit_rpm:
            return True
        if provider.tokens_this_minute + estimated_tokens >= provider.rate_limit_tpm:
            return True
        return False

    def _record_success(self, provider: ProviderConfig, latency_ms: float, tokens: int):
        """Record a successful call."""
        with self._lock:
            provider.consecutive_failures = 0
            provider.calls_this_minute += 1
            provider.tokens_this_minute += tokens
            provider.total_calls += 1
            # Exponential moving average for latency
            provider.avg_latency_ms = (provider.avg_latency_ms * 0.9) + (latency_ms * 0.1)

    def _record_failure(self, provider: ProviderConfig, error: str):
        """Record a failed call."""
        with self._lock:
            provider.consecutive_failures += 1
            provider.total_failures += 1
            provider.calls_this_minute += 1

            if provider.consecutive_failures >= self.CIRCUIT_BREAKER_THRESHOLD:
                provider.circuit_open = True
                provider.circuit_opened_at = time.time()
                print(f"[Concierge] CIRCUIT OPENED for {provider.name}: {error}")

    def _select_model(self, provider: ProviderConfig, 
                      required_capabilities: Optional[Set[ModelCapability]] = None,
                      preferred_model: Optional[str] = None) -> Optional[str]:
        """Select best model for provider based on capabilities."""
        if preferred_model and preferred_model in provider.models:
            return preferred_model

        if not required_capabilities:
            # Default: pick cheapest or fastest
            candidates = sorted(
                provider.models.items(),
                key=lambda x: (0 if ModelCapability.CHEAP in x[1]["capabilities"] else 1,
                               x[1]["cost_per_1m"])
            )
            return candidates[0][0] if candidates else None

        # Match capabilities
        scored = []
        for model_id, meta in provider.models.items():
            caps = meta["capabilities"]
            score = sum(1 for c in required_capabilities if c in caps)
            if score > 0:
                # Bonus for exact match, penalty for cost
                score += 0.5 if score == len(required_capabilities) else 0
                score -= meta["cost_per_1m"] * 0.1
                scored.append((score, model_id, meta))

        if scored:
            scored.sort(reverse=True)
            return scored[0][1]
        return None

    def _build_url(self, provider: ProviderConfig, model: str) -> str:
        """Build the API URL, handling template variables."""
        url = provider.base_url
        if "{model}" in url:
            url = url.replace("{model}", model)
        if "{host}" in url:
            url = url.replace("{host}", provider.base_url)
        return url

    def _call_provider(self, provider: ProviderConfig, prompt: str, model: str,
                       system: Optional[str], image_url: Optional[str],
                       max_tokens: Optional[int]) -> Tuple[Optional[str], Optional[str], int, float]:
        """Make a single provider call. Returns (text, error, tokens_used, latency_ms)."""
        start = time.time()

        try:
            key = os.getenv(provider.env_key, "")
            if provider.name == "ollama":
                key = provider.base_url  # host URL stored here

            url = self._build_url(provider, model)
            headers = provider.headers_fn(key)
            payload = provider.payload_fn(model, prompt, system, image_url, max_tokens)

            resp = requests.post(url, headers=headers, json=payload, 
                                timeout=provider.timeout)
            latency = (time.time() - start) * 1000

            if resp.status_code == 429:
                return None, f"Rate limited ({provider.name})", 0, latency
            if resp.status_code == 401:
                return None, f"Invalid API key ({provider.name})", 0, latency
            if resp.status_code >= 500:
                return None, f"Server error {resp.status_code} ({provider.name})", 0, latency

            resp.raise_for_status()
            data = resp.json()

            # Estimate tokens
            tokens_used = len(prompt.split()) + (max_tokens or 1000)
            if "usage" in data:
                tokens_used = data["usage"].get("total_tokens", tokens_used)

            text = provider.response_fn(data)
            return text, None, tokens_used, latency

        except requests.exceptions.Timeout:
            return None, f"Timeout ({provider.name})", 0, (time.time() - start) * 1000
        except requests.exceptions.ConnectionError:
            return None, f"Connection error ({provider.name})", 0, (time.time() - start) * 1000
        except Exception as e:
            return None, f"{type(e).__name__}: {str(e)[:60]} ({provider.name})", 0, (time.time() - start) * 1000

    # ═══════════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════════

    def generate(self, prompt: str,
                 provider: Optional[str] = None,
                 model: Optional[str] = None,
                 system: Optional[str] = None,
                 image_url: Optional[str] = None,
                 max_tokens: Optional[int] = None,
                 tier: Optional[ProviderTier] = None,
                 required_capabilities: Optional[List[ModelCapability]] = None,
                 fallback_chain: Optional[List[str]] = None,
                 max_retries: int = 3) -> Tuple[Optional[str], Optional[str]]:
        """
        Generate text with intelligent provider selection and failover.

        Args:
            prompt: The user prompt
            provider: Specific provider to use (None = auto-select)
            model: Specific model to use (None = auto-select)
            system: System prompt
            image_url: URL of image for multimodal
            max_tokens: Max output tokens
            tier: Cost tier preference (FREE, CHEAP, STANDARD, PREMIUM, LOCAL)
            required_capabilities: Required model capabilities
            fallback_chain: Ordered list of provider names to try on failure
            max_retries: Max attempts per provider

        Returns:
            (text, error) tuple. text is None on failure, error contains details.
        """

        # Build candidate provider list
        candidates = []

        if provider:
            if provider in self.providers:
                candidates.append(provider)
            else:
                return None, f"Provider '{provider}' not configured or missing API key"

        if fallback_chain:
            for p in fallback_chain:
                if p in self.providers and p not in candidates:
                    candidates.append(p)

        # Auto-select by tier and capabilities
        if not candidates:
            caps = set(required_capabilities) if required_capabilities else set()

            # Score all available providers
            scored = []
            for name, config in self.providers.items():
                if config.circuit_open:
                    continue
                if tier and config.tier != tier:
                    # Allow fallback to adjacent tiers
                    tier_order = [ProviderTier.LOCAL, ProviderTier.FREE, ProviderTier.CHEAP, 
                                  ProviderTier.STANDARD, ProviderTier.PREMIUM]
                    if abs(tier_order.index(config.tier) - tier_order.index(tier)) > 1:
                        continue

                # Check if provider has matching models
                selected = self._select_model(config, caps, model)
                if selected:
                    score = 0
                    # Prefer free/cheap
                    if config.tier == ProviderTier.FREE:
                        score += 100
                    elif config.tier == ProviderTier.CHEAP:
                        score += 50
                    elif config.tier == ProviderTier.LOCAL:
                        score += 40
                    # Penalize high failure rate
                    if config.total_calls > 0:
                        fail_rate = config.total_failures / config.total_calls
                        score -= fail_rate * 50
                    # Penalize high latency
                    score -= config.avg_latency_ms * 0.01
                    scored.append((score, name, config, selected))

            scored.sort(reverse=True)
            candidates = [name for _, name, _, _ in scored]

        if not candidates:
            return None, "No providers available. Check API keys and circuit breakers."

        # Try each candidate
        last_error = None
        for prov_name in candidates:
            config = self.providers[prov_name]

            if self._is_rate_limited(config):
                last_error = f"Rate limited on {prov_name}"
                continue

            selected_model = self._select_model(config, 
                set(required_capabilities) if required_capabilities else None, model)
            if not selected_model:
                last_error = f"No suitable model on {prov_name}"
                continue

            for attempt in range(max_retries):
                text, error, tokens, latency = self._call_provider(
                    config, prompt, selected_model, system, image_url, max_tokens
                )

                if text is not None:
                    self._record_success(config, latency, tokens)
                    return text, None

                self._record_failure(config, error or "Unknown error")
                last_error = error

                if attempt < max_retries - 1:
                    backoff = (2 ** attempt) + random.random()
                    time.sleep(backoff)

        return None, f"All providers failed. Last error: {last_error}"

    def health_check(self) -> Dict[str, Dict]:
        """
        Get health status of all configured providers.

        Returns dict of provider_name -> {
            "available": bool,
            "circuit_open": bool,
            "rate_limited": bool,
            "total_calls": int,
            "total_failures": int,
            "failure_rate": float,
            "avg_latency_ms": float,
            "models_available": int,
            "tier": str
        }
        """
        result = {}
        for name, config in self.providers.items():
            fail_rate = config.total_failures / max(config.total_calls, 1)
            result[name] = {
                "available": not config.circuit_open and config.calls_this_minute < config.rate_limit_rpm,
                "circuit_open": config.circuit_open,
                "rate_limited": self._is_rate_limited(config),
                "total_calls": config.total_calls,
                "total_failures": config.total_failures,
                "failure_rate": round(fail_rate, 3),
                "avg_latency_ms": round(config.avg_latency_ms, 1),
                "models_available": len(config.models),
                "tier": config.tier.name,
                "requires_credit_card": config.requires_credit_card
            }
        return result

    def list_free_models(self) -> List[Dict]:
        """List all zero-cost models across all configured providers."""
        free = []
        for prov_name, config in self.providers.items():
            for model_id, meta in config.models.items():
                if meta.get("cost_per_1m", 0) == 0.0:
                    free.append({
                        "provider": prov_name,
                        "model": model_id,
                        "description": meta.get("description", ""),
                        "context": meta.get("context", 0),
                        "capabilities": [c.name for c in meta.get("capabilities", set())],
                        "tier": config.tier.name
                    })
        return sorted(free, key=lambda x: (x["provider"], x["model"]))

    def list_all_models(self) -> List[Dict]:
        """List all models across all configured providers with pricing."""
        all_models = []
        for prov_name, config in self.providers.items():
            for model_id, meta in config.models.items():
                all_models.append({
                    "provider": prov_name,
                    "model": model_id,
                    "description": meta.get("description", ""),
                    "context": meta.get("context", 0),
                    "cost_per_1m": meta.get("cost_per_1m", 0),
                    "capabilities": [c.name for c in meta.get("capabilities", set())],
                    "tier": config.tier.name
                })
        return sorted(all_models, key=lambda x: (x["cost_per_1m"], x["provider"]))

    def get_cheapest_model(self, required_capabilities: Optional[List[ModelCapability]] = None) -> Optional[Dict]:
        """Find the cheapest model that matches required capabilities."""
        models = self.list_all_models()
        caps = set(required_capabilities) if required_capabilities else set()

        candidates = []
        for m in models:
            model_caps = set(ModelCapability[c] for c in m["capabilities"] if c in ModelCapability.__members__)
            if not caps or caps.issubset(model_caps):
                candidates.append(m)

        if candidates:
            return min(candidates, key=lambda x: x["cost_per_1m"])
        return None

    def estimate_cost(self, prompt: str, provider: Optional[str] = None,
                      model: Optional[str] = None) -> Dict:
        """Estimate cost for a prompt across providers."""
        tokens = len(prompt.split())  # Rough estimate
        estimates = []

        for prov_name, config in self.providers.items():
            if provider and prov_name != provider:
                continue
            selected = self._select_model(config, preferred_model=model)
            if selected:
                meta = config.models[selected]
                cost = (tokens / 1_000_000) * meta["cost_per_1m"]
                estimates.append({
                    "provider": prov_name,
                    "model": selected,
                    "estimated_tokens": tokens,
                    "estimated_cost_usd": round(cost, 6),
                    "tier": config.tier.name
                })

        return {
            "input_tokens_estimate": tokens,
            "provider_estimates": sorted(estimates, key=lambda x: x["estimated_cost_usd"])
        }

    def quick_generate(self, prompt: str, system: Optional[str] = None,
                       max_tokens: int = 2048) -> str:
        """Simplest interface - just returns text or raises."""
        text, error = self.generate(prompt, system=system, max_tokens=max_tokens,
                                    tier=ProviderTier.FREE)
        if error:
            raise RuntimeError(error)
        return text


# ═══════════════════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY
# ═══════════════════════════════════════════════════════════════════════════════

class LegacyConciergeClient(ConciergeClient):
    """Backward-compatible wrapper matching original concierge.py interface."""

    def generate(self, prompt: str, provider: str = "ollama", model: str = None,
                 system: str = None) -> Tuple[Optional[str], Optional[str]]:
        """Legacy interface - maps to new generate()."""
        return super().generate(
            prompt=prompt,
            provider=provider if provider != "ollama" else None,
            model=model,
            system=system,
            tier=ProviderTier.LOCAL if provider == "ollama" else None
        )


# Global instance for import
concierge = ConciergeClient()


# ═══════════════════════════════════════════════════════════════════════════════
# CLI / TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    print("═" * 70)
    print("  CONCIERGE v3.0 -- Provider Health & Free Model Discovery")
    print("═" * 70)

    # Health check
    print("
📊 PROVIDER HEALTH:")
    health = concierge.health_check()
    for name, status in health.items():
        icon = "🟢" if status["available"] else "🔴"
        print(f"  {icon} {name:12s} | {status['tier']:8s} | "
              f"calls:{status['total_calls']:3d} | fails:{status['total_failures']:3d} | "
              f"lat:{status['avg_latency_ms']:6.1f}ms | "
              f"{'CIRCUIT OPEN' if status['circuit_open'] else 'OK'}")

    # Free models
    print("
💰 FREE MODELS AVAILABLE:")
    free = concierge.list_free_models()
    if free:
        for m in free:
            caps = ", ".join(m["capabilities"][:3])
            print(f"  • {m['provider']:12s} | {m['model'][:40]:40s} | {caps}")
    else:
        print("  No free models configured. Set API keys for OpenRouter, Groq, or Cerebras.")

    # Test generation if argument provided
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        print(f"
🚀 TESTING: '{prompt[:50]}...'")
        print("  Trying FREE tier first, then CHEAP, then PREMIUM...")

        for tier in [ProviderTier.FREE, ProviderTier.CHEAP, ProviderTier.PREMIUM]:
            print(f"
  Attempting {tier.name}...")
            text, error = concierge.generate(prompt, tier=tier, max_tokens=256)
            if text:
                print(f"  ✅ SUCCESS via {tier.name}:")
                print(f"     {text[:200]}...")
                break
            else:
                print(f"  ❌ {tier.name} failed: {error}")
    else:
        print("
📝 Usage: python concierge.py 'your prompt here'")
        print("   Set env vars: OPENROUTER_API_KEY, GROQ_API_KEY, CEREBRAS_API_KEY, etc.")
