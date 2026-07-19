# WiSense OS

WiSense OS is the single desktop AI workspace planned in
[`WISENSE_OS_MASTER_PLAN.md`](WISENSE_OS_MASTER_PLAN.md).

This first foundation deliberately does not replace Local Agent Work Center.
It provides a durable task ledger, truthful model policy, and a narrow HTTP
bridge boundary so the future Flutter client has one task lifecycle to use.

## Current testing profiles

- `gemma4:31b-cloud`: supervised cloud builder test profile; future local-Gemma
  target, but **not** a current local service.
- `glm-5.2:cloud`: supervised cloud chat/planning test profile.

`local_autopilot` is intentionally refused until a local builder has been
installed and qualified. Tests use a fake bridge and never call a model or
modify a project.

## Run tests

```powershell
python -m pytest -q
```

