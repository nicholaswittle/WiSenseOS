# AIOS notes (aspirational overlay — not product authority)

**Authority for WiSense OS is [`WISENSE_OS_MASTER_PLAN.md`](WISENSE_OS_MASTER_PLAN.md).**  
This file is historical/aspirational notes from an AIOS packaging pass. Do not treat it as the source of truth for modes, models, or readiness.

## Current hardware reality

- Configured profiles are **cloud-assisted** (`config/model_profiles.json`).
- **Local Autopilot** and **Offline** stay unavailable until a qualified local builder exists.
- Daily path: **Ask Before Changes** with digest-bound propose → approve → apply.
- Model qualification for cloud builders is **not_applicable** (offline corpus only).
- Agentic tool explore/locate is **local-only**; cloud Talk Only uses deterministic explore + redacted chat.

## What “SOPs” actually are

Builtin SOPs are **prompt templates** that fill Companion request text and suggest a mode.  
They do **not** orchestrate agents, bypass approval, or enable Autopilot.

## Telemetry honesty

Command View compute fields may be null with `instrumented: false`. That is intentional — never invent VRAM or tok/s.

## Useful leftovers worth keeping (implemented elsewhere)

- Intent floor + classify API
- Local agentic explore tools
- Budget ledger + redacting Ollama adapter
- Digest-bound proposals

For implementation order and DoD, follow the master plan — not this overlay.
