# WiSense OS

WiSense OS is the single desktop AI workspace planned in
[`WISENSE_OS_MASTER_PLAN.md`](WISENSE_OS_MASTER_PLAN.md).

WiSense owns its own durable task ledger, model policy, native model adapter,
exact-plan patch executor, snapshot restore, and local API. It does not call,
import, launch, or depend on any older project at runtime.

## Current testing profiles

- `gemma4:31b-cloud`: supervised cloud builder test profile; future local-Gemma
  target, but **not** a current local service.
- `glm-5.2:cloud`: supervised cloud chat/planning/builder test profile.

`local_autopilot` is intentionally refused until a local builder has been
installed and qualified. Tests use fake native adapters and never call a model
or modify a real project.

## Setup

The engine needs its own virtual environment (Flask + pytest):

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install flask pytest
```

## Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Run the engine

```powershell
.\.venv\Scripts\python.exe run_engine.py --port 5050
```

The launcher binds to `127.0.0.1`, issues a per-launch loopback token, and
writes it to `%LOCALAPPDATA%\WiSenseOS\engine_token` for the desktop client.
Every `/api/v1` route except `/api/v1/health` requires that token
(`X-WiSense-Token` or `Authorization: Bearer`).
