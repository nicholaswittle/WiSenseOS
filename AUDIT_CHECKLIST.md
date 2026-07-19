# Ops checklist (non-authority)

Product authority: `WISENSE_OS_MASTER_PLAN.md`.  
AIOS overlay notes: `AIOS_MASTER_PLAN.md` (aspirational only).

## Cloud-assisted Ask Before Changes (current hardware)

- [ ] Launcher reaches `/api/v1/health` with engine ready
- [ ] Models listed match `config/model_profiles.json` (cloud profiles; no invented locals)
- [ ] Offline + Local Autopilot unavailable / blocked without local builder
- [ ] Plan draft refuses when no real test can be located (no fake verify targets)
- [ ] Propose writes no files; approve requires matching digest
- [ ] Named tests run isolated; failure restores snapshot
- [ ] Budget reserve visible for cloud propose/talk paths
- [ ] Qualification shows `not_applicable` for cloud (not “failed”)
- [ ] Agentic tool explore refuses cloud models
- [ ] SOP templates only fill Companion text — they do not execute Autopilot

## Do not treat as done

- Live VRAM / tok/s instrumentation
- Automated SOP orchestration
- Offline local builder qualification pass
- Cloud agentic locate (not shipped; refuse-by-default remains)

## Commands

```powershell
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\pytest.exe -q
cd client; flutter test
```
