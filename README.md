# VERTICAL AI // THE BOARDROOM
### Built by Mike / ButtsCorp / BleakNarratives

A multi-agent AI strategy engine. Feed it a business idea, a target,
or a problem. Five agents debate it. A Chairman decides. A genetic
algorithm breeds a champion strategy. Outreach copy generated.

Built solo on Android Termux. Runs on a phone.

---

## QUICK START

Run a boardroom session:
  python vertical_ai.py --text "your idea" --rounds 1 --tracks 2 --iterations 2 --no-neo4j --outreach

Scout local business targets:
  python3 scout_targets.py --location "Wellington KS" --radius 25 --min-score 40

Build vertical market intelligence:
  python3 firefly_lite.py --vertical "plumber" --keywords "intake triage" --deep

Generate pitch reports:
  python3 generate_reports.py

Ingest a codebase for analysis:
  python3 ingest.py --dir /path/to/project
  python vertical_ai.py --file ingest_output.txt

Start the 3D boardroom frontend:
  python3 boardroom_bridge.py &
  python3 -m http.server 8080 &
  Then open: http://127.0.0.1:8080/vertical_ai_boardroom_3d.html

---

## AGENTS

CFO       -- Capital efficiency. Numbers only. Kills ideas without data.
CMO       -- Customer above all. Annoyed by cost-line marketing.
CRO       -- Finds the specific landmine. Not vague.
ANALYST   -- Citable data only. Pained by made-up numbers.
DEVIL     -- Actually believes the opposite. Finds consensus suspicious.
CHAIRMAN  -- Human verdict. go / no-go / conditional.

---

## YVETTE

AI intake specialist for trades businesses.
Named after Yvette Goodrich of Goodrich Plumbing, Alva Oklahoma.
The best dispatcher anyone ever knew.

Covers: sewer/drain decisions, stool pulls, furnace diagnostics,
thermostat triage, faucet repair vs replace, thermocouple threading,
serial number intelligence, parts truck checklist.

---

## VERTICALS

Pre-built domain context for:
  restaurant, plumber, hvac, auto dealer, banking, hospitality

Add your own: verticals/your_vertical.txt

---

## FILE UPLOAD / DOCUMENT ANALYSIS

Ingest a directory:
  python3 ingest.py --dir /path/to/their/project

Ingest specific files:
  python3 ingest.py --files src/*.py README.md

Then run boardroom on the result:
  python vertical_ai.py --file ingest_output.txt --outreach

---

## PROVIDERS

Groq       -- Boardroom agents. Free tier, rate limited.
Gemini     -- Chairman. Free tier, rate limited.
Ollama     -- Local fallback. Needs install.
Anthropic  -- Direct API. Key required.

Set keys in .env:
  GEMINI_API_KEY=your_key
  GROQ_API_KEY=your_key
  ANTHROPIC_API_KEY=your_key

---

## DATA SOURCES (FREE, NO KEY)

BLS        -- Employment by industry
FRED       -- Economic time series
World Bank -- Macro indicators
HackerNews -- Operator sentiment
OpenStreetMap -- Local business discovery

---

## PROJECT STRUCTURE

Official-Vertical-AI-Boardroom/
  vertical_ai.py          Main CLI entrypoint
  boardroom.py            Agent debate engine
  router.py               Provider routing
  simulator.py            Fractal market simulation
  genetics.py             Genetic arena / champion breeding
  firefly_lite.py         Market intelligence scout
  scout_targets.py        Local business target discovery
  ingest.py               File/zip/dir context ingestion
  generate_reports.py     Printable pitch report generator
  boardroom_bridge.py     Browser-to-CLI bridge server
  mutation_engine.py      AST-level code mutation
  concierge.py            Multi-provider API client
  verticals/              Domain context files
  reports/                Generated pitch reports
  targets/                Scout output

---

## BUILT ON

Android Termux. Samsung Galaxy Tab A9. Moto 4 5G.
No IDE. No laptop. No fixed address.
ButtsCorp // BleakNarratives // 2026
