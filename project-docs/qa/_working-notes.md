# QA working notes (scratch — superseded by browser-use-product-quality-audit.md)

Commit under test: b9460305bcc3f61dce51476816ac6bf8a9dc46a9 (branch story_4_8)
Test date: 2026-08-22
Env: web http://localhost:3000 (npm run dev), api http://localhost:8000 (uvicorn --reload), both already running pre-session.
TEAM_MAKER_API_KEY auth wiring confirmed working (web proxy /api/keys/status returns data, not 401).

Provider key status at session start (GET /api/keys/status, matches on both :3000 proxy and :8000 direct):
- anthropic: available (key-config)
- openai: available (key-config)
- google: via-openrouter (reachable via OpenRouter key, NOT a direct Google key)
- groq: unsupported-by-runtime (installed CrewAI has no native groq provider) — key present but commented out in team_maker.keys anyway
- xai: via-openrouter
- ollama: keyless-local, usable=true (need to verify Ollama actually running locally during test)
- openrouter: available (key-config)

## Scenario log (ID | persona | input | expected | actual | severity | evidence)

