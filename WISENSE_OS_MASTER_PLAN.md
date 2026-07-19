# WiSense OS — Master Project Plan

## 1. Product decision

**WiSense OS** is one Windows desktop application for talking to an AI, choosing local or paid models, and safely having the AI work on local projects.

The user opens one app. They do not need to separately open Local Agent Work Center, `my_ai`, Command Center, a terminal watcher, or an Ollama control surface to complete ordinary work.

The product is local-first:

- Routine work uses installed Ollama models at zero cloud cost.
- Cloud models are optional specialists, only reachable through the engine's budget and redaction controls.
- The user can use text or voice, select a project by name, and see evidence for every action.
- The engine, not the user interface, is the only component that may call models, read/write projects, run tests, or commit changes.

### Current hardware reality and rollout policy

WiSense OS must **not** assume that a reliable large local builder is available today. In the current machine configuration, local models may be used for limited experiments or lightweight tasks, but dependable implementation work can use an explicitly approved cloud builder through the engine's existing redaction, confirmation, and budget controls.

The target after the planned hardware upgrade is reliable offline operation with a Gemma-class local builder. That is a future capability milestone, not a prerequisite for the first WiSense OS bridge and not a reason to pretend that a `gemma4:31b` cloud or local service exists today.

Model policy is therefore capability-based and configuration-driven:

- Every provider/model is discovered from the actual local/runtime configuration; UI labels never invent availability.
- A model is eligible for a task only after it has a matching local or cloud capability profile and qualification evidence.
- Offline/Local mode uses only models confirmed available locally; if none is qualified, it stops honestly instead of silently changing to cloud.
- Hybrid mode may use an approved cloud builder, with a visible model name, confirmation boundary, and budget result.
- After the hardware upgrade, a qualified local builder can become the preferred default without changing the task, approval, or validation lifecycle.

## 2. The desired daily experience

> “Fix the totals bug in the billing project, then run the relevant tests.”

WiSense OS should understand the request, resolve the project nickname, explore it, show progress, propose or make the change according to the chosen mode, test it, make one bounded repair attempt if needed, and show the result, diff, and commit evidence.

Three visible operating modes:

| Mode | What it can do | Write rule |
|---|---|---|
| Talk Only | Explain, research, audit, inspect code | Writes are hard-blocked. |
| Ask Before Changes | Explore and prepare a validated proposal | One clear approval before live files change. |
| Local Autopilot | Local model explores, edits, tests, and may make one repair | Limited to the active project; cloud remains blocked unless explicitly enabled. |

Cloud assistance is a separate, explicit choice. It always goes through secret redaction, spend accounting, and the configured per-task budget.

## 3. What we keep from the existing projects

| Source project | Role in WiSense OS | Reuse | Do not carry forward as authority |
|---|---|---|---|
| `local-agent-work-center` | **WiSense Engine** | Model routing, validator, path containment, redaction, budget ledger, snapshots, test runner, model qualification, CLI task flow | Its current web UI as the long-term primary client |
| `my_ai` | **WiSense OS desktop shell** | Conversation UI, voice capture/playback, routing, workbench visuals, agent/task presentation | Direct provider calls and `.tasks` folder-based dispatch |
| `command_center` | **Command View design source** | Project health, history, live status, model metrics, useful operations cards | Supabase as execution authority; unrelated business/game/ticket features |
| `packages/wisense_core`, `packages/wisense_ui` | Shared Flutter foundations | Existing common models and UI utilities after audit | Duplicated task protocol models |

Existing projects stay intact during migration. WiSense OS will integrate them incrementally; it is not a destructive merge.

## 4. Target architecture

```text
WiSense OS desktop app (Flutter)
  ├─ Companion View: chat, voice, approvals, task result
  ├─ Command View: active timeline, diffs, tests, projects, model metrics
  └─ EngineClient: the only client-side connection to the local engine
                         │
                         │ loopback authenticated task API
                         ▼
WiSense Engine (Python; evolved from Local Agent Work Center)
  ├─ Task coordinator and persisted task state
  ├─ Model policy: Ollama local / budgeted cloud adapters
  ├─ Read-only exploration and project nickname resolution
  ├─ Proposal validator, file containment, and redaction
  ├─ Snapshot/restore, tests, bounded repair, git commit
  └─ SQLite run history, evidence, and qualification results
                         │
                         ▼
Active local project worktree(s)
```

### Non-negotiable architecture rules

1. **One execution authority.** Only WiSense Engine calls providers, touches project files, runs commands/tests, creates commits, or records cost.
2. **One task lifecycle.** Every interface creates the same task type and receives the same events/results.
3. **No client-held model keys.** Flutter never contains a Claude or other paid-provider API key after migration.
4. **No uncontrolled write agents.** Agent roles have typed evidence hand-offs; mutations stay serialized per project.
5. **No destructive rollback of normal worktrees.** Preserve current targeted snapshots/restore. Evaluate isolated worktrees later; do not use `git read-tree` to reset a user's live uncommitted work.
6. **Offline is real.** Local/Offline mode hard-blocks every cloud route, including classification, planning, and recovery.

## 5. Security and reliability model

### Local engine access

- Bind the engine to `127.0.0.1` only.
- Generate a random per-launch token.
- Store it under `%LOCALAPPDATA%\WiSenseOS\` using Windows per-user ACLs or DPAPI—not Unix permission assumptions.
- The desktop app reads it and sends it on every request.
- Treat the token as protection from other local accounts/accidental callers, not protection from malware running as the same Windows user.

### Task safety

- Resolve every path under an explicitly selected project root.
- Keep the existing proposal validator and candidate-code screen.
- Require a visible target and diff before writes in Ask Before Changes mode.
- In Local Autopilot, display the selected target, patch, test result, and commit evidence after completion; keep a prominent stop/cancel control.
- Run targeted tests, preserve the pre-change state on failure, and allow at most one evidence-driven repair attempt.
- Never silently spend cloud money; show model, estimated/actual cost, and confirmation boundary.

### Operational recovery

- Persist task state before and after every material step.
- A restarted app reconnects to the engine and restores active/past task history.
- A restarted engine marks interrupted tasks honestly as interrupted; it never guesses that a write or test completed.
- Qualification data recommends models; it never silently changes the user's chosen default.

## 6. Common contract

Define one versioned task protocol before moving the UI. Start with JSON and Dart/Python types; defer automatic code generation until the protocol has survived real use.

Core records:

- `Project`: id, display name, root, trusted/local-autopilot policy.
- `Task`: user request, selected project, mode, requested model policy.
- `TaskRun`: immutable execution attempt with model/provider and timestamps.
- `TaskEvent`: ordered status/evidence event.
- `Approval`: action, digest/target binding, mode, expiry, user confirmation.
- `TaskResult`: outcome, changed paths, diff summary, test evidence, commit, cost.
- `ModelProfile`: local/cloud capability, context limit, qualification evidence, user preference.

Initial task events:

```text
accepted → resolving_project → exploring → proposal_ready
→ awaiting_approval → applying → testing → repairing (optional)
→ committed | completed | rolled_back | blocked | failed | cancelled
```

Use asynchronous tasks: submit returns a `task_id`; the client polls status first and later upgrades to streamed events. Do not hold a single HTTP request open while a local model runs for minutes.

## 7. Bounded role agents

Roles are engine-internal, temporary, and task-scoped—not independently empowered bots.

| Role | Permission | Output |
|---|---|---|
| Planner | No filesystem writes | Bounded step plan |
| Explorer | Read/search only | `ContextEnvelope` with verified files and snippets |
| Implementer | Proposes only | Validated patch/create proposal |
| Verifier | Runs approved checks | `VerificationReport` |
| Recovery | One repair proposal after failed verification | Targeted repair proposal |

The coordinator owns the project lock, mode, approval, budgets, validation, and commit. Read-only work may later run concurrently; writes do not.

## 8. Delivery phases

### Phase 0 — Stabilize the existing engine

**Goal:** make the current Work Center trustworthy as the one execution core.

- Resolve known review findings before migration:
  - model-located write targets need visible confirmation unless Local Autopilot is explicitly selected;
  - qualification output must distinguish expected/not-applicable baseline checks from failures.
- Confirm one canonical direct-task route in the existing API; do not create duplicate dispatch behavior.
- Make model availability truthful: surface only models actually reachable in the current runtime, distinguish local from cloud accurately, and fail closed when Offline/Local mode has no qualified builder.
- Exercise live local edit, create, test-failure, repair, cancellation, and restart cases.
- Write a migration compatibility test suite around the canonical route.

**Exit criteria:** a local task can be submitted through the current API and produces a structured, truthful result without the folder watcher.

### Phase 1 — Thin `my_ai` to Engine bridge

**Goal:** prove the desired single-app workflow before redesigning anything.

- Create `EngineClient` in `my_ai` for engine health, project choice, submit, approval/cancel, status, and history.
- Connect the existing chat input to the canonical engine route.
- Render task status and final evidence in the existing conversation view.
- Display the chosen provider, model, local/cloud status, and budget state for every run; do not hard-code a presumed Gemma model.
- Keep the folder watcher available only as a temporary legacy fallback; do not use it for the new path.
- Store no paid-provider keys in the new client flow.

**Exit criteria:** one Flutter window can submit a plain-English local task and display its completed test/commit evidence.

### Phase 2 — Durable task history and authenticated local API

**Goal:** make engine state survive UI restarts and support a real operations view.

- Add SQLite migrations and repositories for the common contract.
- Introduce task submission, status, project registry, approval, and history endpoints under a versioned API.
- Add loopback token authentication and Windows-safe secret storage.
- Start with polling; add streaming only after ordered persisted events are stable.
- Migrate current lightweight ledgers/history only where they provide authoritative data; avoid duplicating source-of-truth records.

**Exit criteria:** closing/reopening the Flutter app shows current and historical tasks accurately.

### Phase 3 — WiSense OS interface

**Goal:** turn `my_ai` into the single daily-use desktop application.

- Rename/package the Flutter app as WiSense OS.
- Add clear mode picker, active-project picker, local/cloud model policy, task stop control, and engine health indicator.
- Add Companion View for chat/voice and Command View for operations.
- Port selected Command Center concepts only: active task timeline, project health, task history, model qualification, budget/compute information.
- Remove direct provider clients and folder-queue dispatcher from the normal user path after replacement coverage exists.

**Exit criteria:** the user can operate every normal coding task from WiSense OS without opening the old interfaces.

### Phase 4 — Direct task quality and bounded orchestration

**Goal:** make natural-language project work reliable rather than merely connected.

- Use the common task contract for exploration, location, proposal, verification, and recovery evidence.
- Add planner/explorer/implementer/verifier/recovery hand-offs with strict data contracts.
- Support a single bounded repair after a failed relevant test.
- Add real-project replay fixtures for ambiguous project names, ambiguous files, failing baselines, dirty worktrees, and cancellation.
- Expand model qualification from the existing corpus with reviewed tasks from your own projects.
- Run qualification separately for each actually available model. Add the upgraded offline builder only when it is installed, reachable, and has passed the local corpus.

**Exit criteria:** a qualified currently available builder can reliably complete simple edit/create/fix tasks and report why it stopped when it cannot. Before the hardware upgrade, that builder may be an explicitly approved cloud model; afterward, the same corpus must qualify the intended offline local builder.

### Phase 5 — Voice, optional remote status, and packaging

**Goal:** add convenience without weakening the local execution boundary.

- Send existing voice transcription into EngineClient as ordinary tasks.
- Optionally mirror read-only task status/notifications to Supabase or a phone view.
- Keep remote clients unable to bypass desktop-local execution approval rules.
- Ship one launcher that starts the engine, waits for health, then starts WiSense OS.
- Add diagnostics: Ollama reachable, disk space, git availability, selected project health, and engine version.

**Exit criteria:** one launcher opens WiSense OS, voice/text requests work locally, and optional remote views only observe/notify.

## 9. Definition of done

WiSense OS is ready for everyday use when all of these are true:

1. One launcher opens one visible desktop application.
2. The app can use an installed Ollama model without cloud access or an API key.
3. A plain request can select a known project, explore it, make a validated change, run relevant tests, and return a concise evidence-backed result.
4. The user sees mode, model, project, live state, changed files, verification result, and cost before/after relevant actions.
5. Ask Before Changes never writes before a single explicit approval; Local Autopilot never uses cloud without a separate explicit toggle.
6. Failed work restores the exact changed files safely and says what failed.
7. The app survives client restarts and preserves honest run history.
8. Cloud providers are only reachable through the engine's redaction, budget, and approval controls.
9. The old folder watcher is unnecessary for normal interactive work.
10. The same task lifecycle powers chat, voice, dashboard, and terminal/CLI access.
11. Before the hardware upgrade, the app accurately represents cloud-assisted operation; after it, it can select a qualified offline builder without changing safety behavior.

## 10. Out of scope until the core is proven

- Autonomous open-ended agent swarms.
- Multi-machine remote execution.
- Automatic model switching without a user-visible recommendation.
- A full rewrite of the Python engine into another web framework.
- Moving unrelated Command Center business/support/gamification features into the product.
- Any destructive migration or deletion of the existing three projects.

## 11. First implementation decision

Begin with **Phase 0, then Phase 1 only**. The first concrete proof is deliberately small:

> Start WiSense Engine, open WiSense OS, type a plain-English request, select the project, and see the existing validated engine return live status and a final evidence-backed result.

Do not begin dashboard redesign, remote sync, or multi-agent orchestration until this end-to-end bridge is reliable.
