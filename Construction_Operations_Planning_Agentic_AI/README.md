# BuildPlan

**Construction Operations Planning and Resource Allocation Using Agentic AI**

A complete local application based on `T9977_REC_Rev3_Project2.pptx`. It has its own construction dashboard, activity editor, resource register, schedule, what-if comparison and reports. No troubleshooting interface or code is reused.

## Start on Windows

1. Extract the **entire ZIP** with **Extract All**. Do not run files from inside the ZIP preview.
2. Open the extracted `BuildPlan` folder.
3. Double-click **START_WINDOWS.bat**.
4. The application opens at **http://127.0.0.1:8765**. Keep the terminal window open.
5. Click **Generate plan** to save the demonstration project and its first planning run.

**Requirement:** Python 3.10 or newer, including `sqlite3`. Python 3.11 on your laptop is suitable. If Python is missing, install it from https://www.python.org/downloads/windows/ and enable **Add Python to PATH**.

The normal launcher requires **no pip installation, internet connection, Node.js, Docker, API key, or Ollama**. The compiled React dashboard is included. There is no trained model download on startup.

Alternative from PowerShell, inside the extracted folder:

```powershell
python run.py
```

If `python` is not found but the Python launcher is installed:

```powershell
py -3 run.py
```

If port 8765 is already occupied:

```powershell
python run.py --port 8766
```

Open the address printed in the terminal. Press **Ctrl+C** in the terminal to stop.

## What is included

- React dashboard with a new construction-specific layout; all assets are bundled locally.
- Python planning engine with explicit agent classes.
- Dependency analysis using CPM forward and backward passes.
- Resource leveling for labour and equipment, including unavailable days.
- Material consumption tracking with dated deliveries and shortage detection.
- Cost calculation, budget comparison and rule-based risk flags.
- What-if scenarios that compare changes without overwriting the original plan.
- SQLite project storage, revision protection and planning history.
- JSON project import/export, schedule CSV export and a printable report.
- Optional FastAPI adapter using the same planning core.
- Optional local Ollama explanation using `llama3.2:3b`.
- Test suite, sample inputs, architecture mapping and mentor demonstration guide.

## First demonstration

The sample represents an illustrative community-centre construction phase in Chennai. It contains 12 activities and 8 resource definitions.

Expected results using the supplied inputs:

| Measure | Expected value |
|---|---:|
| Dependency-only baseline | 26 calendar days |
| Resource-constrained schedule | 31 calendar days |
| Activities scheduled | 12 / 12 |
| Blocked activities | 0 |
| Estimated cost | ₹835,700 |
| Entered budget | ₹550,000 |
| Target duration | 30 days |
| Finish date | 11 November 2026 |
| Risk indication | High: target and budget exceeded |

The input values are **demonstration assumptions**, not a dataset collected from a real construction site. They must not be presented as production validation or research performance evidence.

## Main workflow

1. **Project settings:** set start date, target, budget, daily overhead, input source and scheduling rule.
2. **Resources:** add workers, equipment and material definitions, rates and availability.
3. **Activities:** set durations, dependencies, priority and resource requirements.
4. **Generate plan:** validate, schedule, calculate costs, flag risks and save a planning run.
5. **Schedule:** view the leveled timeline and each activity's allocation reason. Enable the dependency baseline for comparison.
6. **What-if studio:** change one resource capacity or material stock assumption and compare. **Apply as draft** requires a new planning run before results are saved.
7. **Reports & agents:** review costs, agent decisions and conflicts. Export CSV or use **Print / PDF** and select **Save as PDF** in your browser.

Click **Projects** in the upper-right corner to open a saved project, create a new project, reload the demo or import JSON. A new project starts empty; add resources and activities before generating it.

Changes invalidate old results. **Save inputs** stores only the project inputs. **Generate plan** saves both inputs and the resulting planning run. Closing the browser with unsaved changes prompts for confirmation. The latest saved project opens on restart.

## Data conventions

- All durations use consecutive **calendar days**, including weekends and holidays unless a resource is explicitly unavailable.
- Activities are non-preemptive: the same daily crew/equipment requirement applies for their entire duration.
- Dependencies are finish-to-start, with no lead or lag. Multiple predecessors are allowed; cycles are rejected.
- Labour/equipment quantities are units **per day**, not total unit-days.
- Materials are consumed **once at activity start**. Deliveries arrive at the beginning of their specified day.
- The interface uses **Day 1** for the project start. JSON fields `release_day`, delivery `day`, and `unavailable_days` use **zero-based offsets**. For example JSON day `12` is interface Day 13.
- Internally, activity intervals are `[start, finish)`. The displayed finish date is the **last occupied day**.
- Rate currency is INR. Renewable-resource rates are per unit per day; material rates are per unit consumed.
- Priority 5 is highest. Baseline float, priority and ID provide deterministic tie-breaking according to the selected scheduling rule.
- Critical highlighting means **zero float in the dependency-only baseline**. It is not a complete resource-constrained critical-chain analysis.

## Planning and AI scope

This is a **bounded, rule-based multi-agent planning prototype**. The coordinator invokes task, labour, equipment, material, cost and risk agents within a fixed workflow. It tests feasible start slots and produces a reviewable plan. It never purchases resources, issues work orders, controls equipment or approves construction work.

There is **no trained prediction model, reinforcement learning, autonomous LLM scheduler, or claim of globally optimal scheduling**. The risk level is a transparent rule label, not a statistical delay probability. Optional Ollama text is explicitly unverified and cannot modify the calculated plan.

The PPT's Python, React/Vite and SQLite technologies are implemented. FastAPI is available as an optional server mode. A Python standard-library server is provided for offline, zero-package startup. Pandas/NumPy are unnecessary for these bounded input sizes and are not runtime requirements.

## Optional FastAPI mode

Use this if your review requires showing FastAPI. Internet is required **only for this optional dependency installation**. From the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8765
```

Open http://127.0.0.1:8765 in the browser. Stop the default server before starting this on the same port. Both adapters use the same engine, routes and SQLite file. The API route reference is in `docs/API.md`.

On macOS/Linux, use `python3 -m venv .venv`, `.venv/bin/python -m pip install -r requirements.txt`, then `.venv/bin/python -m uvicorn app.api:app --host 127.0.0.1 --port 8765`.

## Optional local LLM explanation

If Ollama and `llama3.2:3b` are already installed, start Ollama, open **Reports & agents**, and click **Explain this plan**. Otherwise install the free local model with `ollama pull llama3.2:3b` when you have internet. Model setup is independent of normal application startup.

Only the computed plan summary, cost and activity reasons are sent to your local `127.0.0.1:11434` endpoint when you click that button. No cloud model or paid API is called. On a CPU, the explanation may take up to 90 seconds before timing out. If the model is unavailable, the app shows a message and retains all normal planning functionality. Review any model explanation against the computed facts.

## Editing and rebuilding the frontend

This is needed only when changing React source. The distributable already includes `frontend/dist`.

Install Node.js 22.12+ or a compatible later release, then:

```powershell
cd frontend
npm ci
npm run build
cd ..
python run.py
```

`npm ci` requires internet. `npm run dev` provides a Vite development server; keep the Python server running on 8765. The normal launch has no Node.js dependency.

## Tests

From the project root:

```powershell
python -m unittest discover -s tests -v
```

See `docs/VALIDATION.md` for the tested scope and evidence. The tests cover scheduling constraints, material delivery/reservation behavior, cost arithmetic, invalid inputs, persistence, revision conflicts, HTTP routes and bundled frontend delivery. This is software validation on demonstration cases, not construction-site validation.

## Persistence and backup

Projects and runs are saved in `data/buildplan.sqlite3`, created automatically on first launch. Stop the app before copying this file for a full backup. JSON export contains portable project inputs; CSV contains the calculated schedule. The 20 latest runs are shown per project; older stored runs are not automatically deleted.

To recover a planning history entry, choose **Restore inputs**. This creates a new unsaved draft, preserving the earlier project and run.

## Boundaries

- Single local workspace; no login, cloud deployment or multi-user permissions. Keep it bound to loopback.
- Up to 80 activities, 40 resource definitions, 180 days per activity and a 2,000-day search horizon.
- No progress-as-built tracking, rolling-horizon replanning, weather feed, worker skill matching, safety engineering checks, labour compliance or site execution integration.
- Capacity is constant except unavailable days. Fixed crew demands cannot be automatically reduced or split across shifts.
- Cost includes assigned labour/equipment, consumed materials, fixed activity costs and calendar-day overhead. Taxes, escalation, idle equipment hire, finance cost and productivity uncertainty are excluded.
- Additional capacity changes availability; it does not add standby/hiring charges automatically. Enter such costs explicitly where relevant.
- If any task is blocked, the schedule is partial and full-project duration is unknown. The displayed cost includes all requested task direct costs plus overhead for the partial scheduled duration, and is marked incomplete.
- Scenario savings are suppressed if either compared plan is infeasible.

## Troubleshooting startup

| Situation | Action |
|---|---|
| Python not found | Install Python and enable Add Python to PATH; reopen the terminal. |
| Browser did not open | Copy the local URL printed in the terminal. |
| Port in use | Run `python run.py --port 8766`. |
| Dashboard missing | Extract the entire ZIP; retain `frontend/dist` and its assets. |
| Cannot save database | Extract to a writable folder such as Documents; do not run inside the ZIP or a protected system folder. |
| Old page after rebuilding | Refresh the browser; the server sends no-store headers. |
| Blocked plan | Read the activity's reason and adjust capacity, deliveries, dependencies or the planning horizon assumptions. |
| Another window changed project | Reload it or export your current inputs and import them as a new project. |
| Ollama unavailable | Use the computed agent decisions; Ollama is optional. |

Project module explanations and formulas are in `docs/ARCHITECTURE.md`. A short mentor demo script is in `docs/DEMO_GUIDE.md`.
