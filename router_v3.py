#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
ROUTER v3.0 -- Model Provider Router for Vertical AI Boardroom
Integrates with Concierge v3.0 for intelligent multi-provider orchestration.

Replaces the old router.py. Drop-in compatible with boardroom.py and vertical_ai.py.

Usage:
    from router import call_model, ModelTier, check_providers

    # Boardroom agent call (auto-selects best available)
    response, provider = call_model(prompt, system=persona, tier=ModelTier.BOARDROOM)

    # Chairman synthesis (premium model, auto-failover)
    response, provider = call_model(prompt, tier=ModelTier.FAST, chairman=True)

    # Check which providers are active
    status = check_providers()
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import time
import json
from enum import Enum, auto
from typing import Optional, Tuple, List, Dict, Set
from dataclasses import dataclass

# Import the new concierge
from concierge import ConciergeClient, ProviderTier, ModelCapability


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL TIER MAPPING (Backward compatible with boardroom.py)
# ═══════════════════════════════════════════════════════════════════════════════

class ModelTier(Enum):
    """Backward-compatible tier definitions."""
    BOARDROOM = auto()   # Strong reasoning, used by board agents
    FAST = auto()        # Fast responses, used by chairman
    CHEAP = auto()       # Lowest cost
    PREMIUM = auto()     # Best quality regardless of cost
    LOCAL = auto()       # Ollama / local only


# Map old tiers to new capability requirements
TIER_CAPABILITY_MAP = {
    ModelTier.BOARDROOM: [ModelCapability.REASONING, ModelCapability.LONG_CONTEXT],
    ModelTier.FAST: [ModelCapability.FAST, ModelCapability.REASONING],
    ModelTier.CHEAP: [ModelCapability.CHEAP],
    ModelTier.PREMIUM: [ModelCapability.REASONING, ModelCapability.CODING, ModelCapability.LONG_CONTEXT],
    ModelTier.LOCAL: [ModelCapability.CHEAP],  # Local is always cheap (free)
}

# Map old tiers to preferred provider tiers
TIER_PROVIDER_TIER_MAP = {
    ModelTier.BOARDROOM: ProviderTier.FREE,      # Try free first, failover to cheap
    ModelTier.FAST: ProviderTier.FREE,           # Fast free models exist
    ModelTier.CHEAP: ProviderTier.FREE,          # Free is cheapest
    ModelTier.PREMIUM: ProviderTier.PREMIUM,     # Only premium
    ModelTier.LOCAL: ProviderTier.LOCAL,         # Only local
}


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER STATE
# ═══════════════════════════════════════════════════════════════════════════════

_concierge: Optional[ConciergeClient] = None
_last_provider: Optional[str] = None
_call_stats: Dict[str, Dict] = {}


def _get_concierge() -> ConciergeClient:
    """Lazy initialization of concierge client."""
    global _concierge
    if _concierge is None:
        _concierge = ConciergeClient()
    return _concierge


# ═══════════════════════════════════════════════════════════════════════════════
# CORE API (Drop-in replacement for old router.py)
# ═══════════════════════════════════════════════════════════════════════════════

def call_model(prompt: str, 
               system: Optional[str] = None,
               tier: ModelTier = ModelTier.BOARDROOM,
               chairman: bool = False,
               max_tokens: Optional[int] = None,
               provider: Optional[str] = None,
               model: Optional[str] = None) -> Tuple[str, str]:
    """
    Call an LLM with intelligent provider selection and failover.

    This is the drop-in replacement for the old router.call_model().

    Args:
        prompt: The prompt text
        system: System prompt / persona
        tier: ModelTier enum for quality/speed preference
        chairman: If True, uses premium model for synthesis
        max_tokens: Max output tokens
        provider: Force specific provider (overrides tier selection)
        model: Force specific model ID

    Returns:
        (response_text, provider_name) tuple

    Raises:
        RuntimeError: If all providers fail
    """
    concierge = _get_concierge()

    # Determine target tier and capabilities
    if chairman:
        target_tier = ProviderTier.PREMIUM
        capabilities = [ModelCapability.REASONING, ModelCapability.LONG_CONTEXT, ModelCapability.CODING]
        max_tokens = max_tokens or 2048
    else:
        target_tier = TIER_PROVIDER_TIER_MAP.get(tier, ProviderTier.FREE)
        capabilities = TIER_CAPABILITY_MAP.get(tier, [ModelCapability.REASONING])
        max_tokens = max_tokens or 1024

    # Override with specific provider if requested
    if provider:
        target_tier = None  # Let concierge use the specific provider

    # Build fallback chain based on tier
    fallback_chain = None
    if tier == ModelTier.BOARDROOM:
        # Boardroom needs reasoning - try free, then cheap, then premium
        fallback_chain = ["openrouter", "groq", "cerebras", "deepseek", "together", "anthropic", "openai"]
    elif tier == ModelTier.FAST:
        # Fast needs speed - try Groq first, then Cerebras, then OpenRouter free
        fallback_chain = ["groq", "cerebras", "openrouter", "gemini", "deepseek"]
    elif tier == ModelTier.CHEAP:
        # Cheapest possible
        fallback_chain = ["openrouter", "groq", "cerebras", "ollama", "deepseek"]
    elif tier == ModelTier.PREMIUM or chairman:
        # Best quality, cost no object
        fallback_chain = ["anthropic", "openai", "gemini", "openrouter", "groq"]
    elif tier == ModelTier.LOCAL:
        fallback_chain = ["ollama"]

    # Filter fallback chain to only configured providers
    configured = set(concierge.providers.keys())
    fallback_chain = [p for p in fallback_chain if p in configured]

    # If a specific provider was requested, put it first
    if provider and provider in configured:
        if provider not in fallback_chain:
            fallback_chain.insert(0, provider)
        else:
            fallback_chain.remove(provider)
            fallback_chain.insert(0, provider)

    # Make the call
    start_time = time.time()
    text, error = concierge.generate(
        prompt=prompt,
        system=system,
        max_tokens=max_tokens,
        tier=target_tier,
        required_capabilities=capabilities,
        fallback_chain=fallback_chain if fallback_chain else None,
        provider=provider if provider and not fallback_chain else None,
        model=model
    )

    latency = time.time() - start_time

    if text is None:
        raise RuntimeError(f"All providers failed. Last error: {error}")

    # Determine which provider actually succeeded
    # The concierge doesn't return this directly, so we infer from health
    health = concierge.health_check()
    used_provider = provider or "unknown"

    # Find provider with most recent successful call
    most_recent = None
    most_recent_time = 0
    for name, status in health.items():
        if status["total_calls"] > 0 and status["failure_rate"] < 1.0:
            # This provider has been used successfully
            if name in fallback_chain:
                used_provider = name
                break

    # Track stats
    global _last_provider
    _last_provider = used_provider

    if used_provider not in _call_stats:
        _call_stats[used_provider] = {"calls": 0, "failures": 0, "avg_latency": 0}

    stats = _call_stats[used_provider]
    stats["calls"] += 1
    stats["avg_latency"] = (stats["avg_latency"] * (stats["calls"] - 1) + latency) / stats["calls"]

    return text.strip(), used_provider


def check_providers() -> Dict[str, bool]:
    """
    Check which providers are available.

    Returns dict mapping provider name -> True/False.
    Backward compatible with old check_providers().
    """
    concierge = _get_concierge()
    health = concierge.health_check()

    # Return simple boolean availability
    return {
        name: status["available"] and not status["circuit_open"]
        for name, status in health.items()
    }


def get_provider_stats() -> Dict[str, Dict]:
    """Get detailed stats for all providers."""
    return _call_stats.copy()


def get_last_provider() -> Optional[str]:
    """Get the name of the last successfully used provider."""
    return _last_provider


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def estimate_cost(prompt: str, tier: ModelTier = ModelTier.BOARDROOM) -> Dict:
    """Estimate cost across providers for a given prompt and tier."""
    concierge = _get_concierge()
    target_tier = TIER_PROVIDER_TIER_MAP.get(tier, ProviderTier.FREE)
    capabilities = TIER_CAPABILITY_MAP.get(tier, [ModelCapability.REASONING])

    return concierge.estimate_cost(
        prompt=prompt,
        tier=target_tier
    )


def list_available_models(tier: Optional[ModelTier] = None) -> List[Dict]:
    """List all available models, optionally filtered by tier."""
    concierge = _get_concierge()

    if tier == ModelTier.CHEAP or tier == ModelTier.LOCAL:
        return concierge.list_free_models()

    models = concierge.list_all_models()

    if tier:
        target_tier = TIER_PROVIDER_TIER_MAP.get(tier)
        if target_tier:
            models = [m for m in models if m["tier"] == target_tier.name]

    return models


def reset_circuits():
    """Manually reset all circuit breakers."""
    concierge = _get_concierge()
    for config in concierge.providers.values():
        config.circuit_open = False
        config.consecutive_failures = 0
    print("[Router] All circuit breakers reset")


# ═══════════════════════════════════════════════════════════════════════════════
# DIAGNOSTICS
# ═══════════════════════════════════════════════════════════════════════════════

def print_diagnostics():
    """Print full diagnostic information."""
    concierge = _get_concierge()

    print("═" * 70)
    print("  ROUTER v3.0 DIAGNOSTICS")
    print("═" * 70)

    print("
📡 CONFIGURED PROVIDERS:")
    health = concierge.health_check()
    for name, status in health.items():
        icon = "🟢" if status["available"] else "🔴"
        print(f"  {icon} {name:15s} | tier:{status['tier']:8s} | "
              f"models:{status['models_available']:2d} | "
              f"calls:{status['total_calls']:3d} | fails:{status['total_failures']:3d}")

    print("
📊 CALL STATISTICS (this session):")
    if _call_stats:
        for name, stats in _call_stats.items():
            print(f"  • {name:15s} | calls:{stats['calls']:3d} | "
                  f"avg_lat:{stats['avg_latency']*1000:6.1f}ms")
    else:
        print("  No calls made yet")

    print("
💰 FREE MODELS:")
    free = concierge.list_free_models()
    for m in free[:10]:  # Show first 10
        print(f"  • {m['provider']:12s} | {m['model'][:35]:35s}")
    if len(free) > 10:
        print(f"  ... and {len(free)-10} more")

    print("
🎯 TIER MAPPING:")
    for tier in ModelTier:
        caps = [c.name for c in TIER_CAPABILITY_MAP.get(tier, [])]
        prov_tier = TIER_PROVIDER_TIER_MAP.get(tier, ProviderTier.FREE)
        print(f"  {tier.name:12s} -> {prov_tier.name:8s} | needs: {', '.join(caps)}")


# ═══════════════════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY SHIMS
# ═══════════════════════════════════════════════════════════════════════════════

# Old router.py used these names - ensure they still work
def query_ollama(prompt: str, model: str = "deepseek-r1:1.5b", system: str = None) -> Tuple[Optional[str], Optional[str]]:
    """Direct Ollama query for backward compatibility."""
    concierge = _get_concierge()
    return concierge.generate(prompt, provider="ollama", model=model, system=system)


def query_gemini(prompt: str, model: str = "gemini-1.5-pro", system: str = None) -> Tuple[Optional[str], Optional[str]]:
    """Direct Gemini query for backward compatibility."""
    concierge = _get_concierge()
    return concierge.generate(prompt, provider="gemini", model=model, system=system)


def query_groq(prompt: str, model: str = "llama-3.3-70b-versatile", system: str = None) -> Tuple[Optional[str], Optional[str]]:
    """Direct Groq query for backward compatibility."""
    concierge = _get_concierge()
    return concierge.generate(prompt, provider="groq", model=model, system=system)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--diagnostics":
        print_diagnostics()
    elif len(sys.argv) > 1 and sys.argv[1] == "--test":
        prompt = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Say hello and name your provider"
        print(f"Testing with prompt: '{prompt}'")
        print("
Trying BOARDROOM tier...")
        try:
            text, prov = call_model(prompt, tier=ModelTier.BOARDROOM)
            print(f"✅ {prov}: {text[:100]}...")
        except RuntimeError as e:
            print(f"❌ {e}")
    else:
        print_diagnostics()
        print("
Usage:")
        print("  python router.py --diagnostics    # Full health report")
        print("  python router.py --test 'prompt'  # Test generation")
