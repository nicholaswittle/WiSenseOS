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

## Run tests

```powershell
python -m pytest -q
```
