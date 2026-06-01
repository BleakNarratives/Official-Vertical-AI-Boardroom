# ═══════════════════════════════════════════════════════════════════════════════
# VERTICAL AI BOARDROOM -- CONCIERGE v3.0 SETUP GUIDE
# Free-Tier API Provider Configuration
# ═══════════════════════════════════════════════════════════════════════════════

## QUICK START (5 minutes)

1. **Get your free API keys** (no credit card required for these):

   ### OpenRouter (Best free model selection)
   - Go to: https://openrouter.ai/keys
   - Sign up with email
   - Copy your key
   - Free models: DeepSeek R1, Llama 4 Maverick/Scout, Qwen3, Grok Mini, Mistral Small

   ### Groq (Fastest inference)
   - Go to: https://console.groq.com/keys
   - Sign up with email
   - Copy your key
   - Free tier: 30 RPM, 6K TPM, 14.4K requests/day

   ### Cerebras (1M tokens/day free)
   - Go to: https://cloud.cerebras.ai/
   - Sign up with email
   - Copy your key
   - Free tier: 1M tokens/day, 30 RPM, 2600+ tps

   ### Google Gemini (1K requests/day free)
   - Go to: https://aistudio.google.com/app/apikey
   - Sign in with Google
   - Create API key
   - Free tier: 1,000 requests/day with Gemini 2.5 Flash

2. **Install the new files:**
   ```bash
   cp concierge_v3.py concierge.py
   cp router_v3.py router.py
   ```

3. **Create your .env file:**
   ```bash
   cp .env.template .env
   # Edit .env and paste your keys
   ```

4. **Test it:**
   ```bash
   python concierge.py "Hello, what providers are available?"
   python router.py --diagnostics
   python vertical_ai.py --text "Test my boardroom"
   ```


## PROVIDER COMPARISON (May 2026)

| Provider | Free Tier | Speed | Best For | Credit Card |
|----------|-----------|-------|----------|-------------|
| **OpenRouter** | 20+ free models | Medium | Variety, reasoning, coding | No |
| **Groq** | 30 RPM / 6K TPM | **Fastest** | Real-time, low latency | No |
| **Cerebras** | **1M tokens/day** | Very Fast | High volume, sustained load | No |
| **Gemini** | 1K req/day | Fast | Long context (1M), multimodal | No |
| **Together** | $5 credit | Medium | Open source models | No |
| **Fireworks** | Limited free | Medium | Structured output, function calling | No |
| **DeepSeek** | Very cheap | Medium | Coding, reasoning | No |
| **Ollama** | Unlimited (local) | Varies | Privacy, zero cost, offline | N/A |


## TIER STRATEGY

The new router automatically selects providers based on the task:

- **BOARDROOM agents** → Try FREE first (OpenRouter DeepSeek R1, Groq Llama 70B), 
  failover to CHEAP (DeepSeek direct, Together), then PREMIUM (Claude, GPT-4)

- **Chairman synthesis** → Try PREMIUM (Claude Sonnet, Gemini Pro), 
  failover to FREE (OpenRouter Claude via OpenRouter)

- **Fast responses** → Groq first (840 TPS on Llama 8B), then Cerebras (2600 TPS)

- **Local/offline** → Ollama (deepseek-r1:7b, llama3.2:3b, qwen2.5:7b)


## CIRCUIT BREAKER BEHAVIOR

If a provider fails 5 times consecutively:
1. Circuit opens (provider skipped for 5 minutes)
2. Traffic routes to next provider in fallback chain
3. After 5 minutes, circuit automatically closes
4. Provider is retried on next call

This prevents cascading failures and ensures your boardroom keeps running.


## RATE LIMIT TRACKING

The concierge tracks per-minute usage and automatically:
- Switches to alternative providers when rate limits hit
- Backs off with exponential delay
- Resets counters every 60 seconds

You never need to manually manage rate limits again.


## ENVIRONMENT VARIABLES

```bash
# FREE TIER PROVIDERS (Get these first - no credit card)
OPENROUTER_API_KEY=sk-or-v1-...
GROQ_API_KEY=gsk_...
CEREBRAS_API_KEY=csk-...
GOOGLE_API_KEY=AIza...

# CHEAP TIER (Optional - pay-per-token, very low cost)
DEEPSEEK_API_KEY=sk-...
TOGETHER_API_KEY=...
FIREWORKS_API_KEY=...

# PREMIUM TIER (Optional - best quality, higher cost)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# LOCAL (Ollama - runs on your machine)
OLLAMA_HOST=http://127.0.0.1:11434
```


## TROUBLESHOOTING

**"No providers available"**
→ Set at least one API key in .env. Start with OpenRouter (easiest, most free models).

**"Rate limited on all providers"**
→ You've hit limits across the board. Wait 60 seconds, or add more provider keys.

**"Circuit opened for [provider]"**
→ That provider is failing repeatedly. Check your API key, or wait 5 minutes.

**"Timeout on [provider]"**
→ Network issue or provider overload. The router will automatically try next provider.

**Ollama not working**
→ Ensure Ollama is running: `ollama serve` or `ollama run deepseek-r1:7b`


## ADVANCED: CUSTOM FALLBACK CHAINS

In your boardroom.py or vertical_ai.py, you can override the default chain:

```python
from router import call_model, ModelTier

# Force specific provider
response, provider = call_model(prompt, provider="cerebras", model="llama-4-scout")

# Custom fallback for a specific agent
response, provider = call_model(
    prompt, 
    system=cfo_persona,
    tier=ModelTier.BOARDROOM,
    # Custom chain: try Cerebras first, then Groq, then OpenRouter
    # (Note: fallback_chain is handled internally, but you can patch router.py)
)
```


## MIGRATION FROM OLD CONCIERGE

The new files are drop-in replacements:
- `concierge.py` → `concierge_v3.py` (same import: `from concierge import concierge`)
- `router.py` → `router_v3.py` (same imports: `from router import call_model, ModelTier`)

No code changes needed in boardroom.py, vertical_ai.py, or the 3D frontend.


## FREE TIER LIMITS (May 2026)

| Provider | RPM | TPM | Daily | Notes |
|----------|-----|-----|-------|-------|
| OpenRouter free | 20 | 2K | Unlimited* | *Rate limits vary by model |
| Groq free | 30 | 6K | 14,400 req | Hard limits, resets daily |
| Cerebras free | 30 | 1M | 1M tokens | Most generous daily budget |
| Gemini free | ~15 | 1M | 1K req | Per Google account |
| Together | 30 | 100K | $5 credit | One-time credit |
| Fireworks | 30 | 100K | Limited | Trial tier |


## RECOMMENDED MINIMUM SETUP

For a fully free, robust boardroom:
1. **OpenRouter** (must-have: most free models, best variety)
2. **Groq** (must-have: fastest inference, good for real-time)
3. **Cerebras** (must-have: highest daily volume, 1M tokens/day)
4. **Gemini** (nice-to-have: 1M context, multimodal)

With these 3-4 keys, you have:
- 30+ free models to choose from
- Automatic failover across 3 independent infrastructures
- No single point of failure
- Zero cost operation


## NEXT STEPS

1. Get your keys
2. Copy the new files
3. Run `python router.py --diagnostics`
4. Run `python vertical_ai.py --text "Test the new router"`
5. Watch it automatically route between providers

The boardroom now has a brain that knows when to switch keys, 
which model to pick, and how to keep running when providers fail.
