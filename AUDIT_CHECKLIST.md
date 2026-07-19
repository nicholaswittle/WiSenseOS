# WiSense OS — Operational Compliance Audit Checklist

Use this audit checklist during development, refactoring, or feature additions to verify that all code changes stay aligned with the **WiSense OS AIOS Master Plan**.

---

## 📋 Pre-Flight Audit Checklist

### 1. Workspace & Security Boundary Check
- [ ] **Path Containment**: Are all file read/write operations strictly contained within the active project root?
- [ ] **Windows Token Auth**: Does the API request enforce loopback token authentication (`Bearer <token>`) from `%LOCALAPPDATA%\WiSenseOS\engine.token`?
- [ ] **Port Safety**: Does the launcher check for port collisions on `127.0.0.1:5050` before starting?

### 2. Model Policy & Router Check
- [ ] **Truthful Labels**: Are cloud profiles (`claude-3-7-sonnet`, `gemma4:31b-cloud`) clearly labeled as "Cloud — supervised testing"?
- [ ] **Autopilot Block**: Does the system refuse `local_autopilot` mode when a cloud model is selected?
- [ ] **Local-First Routing**: Does the multiplexer router (`wisense_os/router.py`) default to local Ollama models for low/medium complexity tasks?

### 3. Memory & Context Sync Check
- [ ] **Project Context File**: Is `.wisense/CONTEXT.md` updated with directory topology and language stack changes?
- [ ] **Task Persistence**: Are task states and events saved durably in SQLite (`engine_state.db`)?

### 4. Human-in-the-Loop Approval Check
- [ ] **Explicit Approval Gate**: Is approval required before any model modifies project files in `ask_before_changes` mode?
- [ ] **Clarification Banner**: Does the UI render an "Engine Clarification Needed" banner when status is `waiting_for_provider_input`?
- [ ] **Evidence Plan Draft**: Does the UI allow drafting and previewing evidence plans (`draftTaskPlan`) before handoff?

### 5. Code Quality & Test Verification
- [ ] **Pytest Suite**: Do all Python engine tests pass (`.venv\Scripts\python -m pytest` -> 100% pass rate)?
- [ ] **Flutter Suite**: Does Flutter analysis pass (`flutter analyze` -> 0 issues) and all unit/widget tests pass (`flutter test` -> 100% pass rate)?
- [ ] **Git Scoped Commits**: Are commits scoped specifically to modified files without sweeping unrelated changes?

### 6. Andrej Karpathy LLM Behavioral Principles Check
- [ ] **Think Before Coding**: Are assumptions explicitly stated in the plan draft before modifying code?
- [ ] **Simplicity First**: Is the patch free of speculative abstractions, unused features, or unnecessary wrappers?
- [ ] **Surgical Scope**: Are changes strictly limited to files specified in the request/plan?
- [ ] **Goal-Driven Execution**: Do unit tests run and pass to verify the exact change before finalizing?

---

## 🛠 How to Run an Audit

Run the following commands in PowerShell from `C:\development\projects\wisense-os`:

```powershell
# 1. Run Python Engine Audit Suite
.\.venv\Scripts\python -m pytest

# 2. Run Flutter Client Code Analysis
cd client
flutter analyze

# 3. Run Flutter Unit & Widget Test Suite
flutter test
```
