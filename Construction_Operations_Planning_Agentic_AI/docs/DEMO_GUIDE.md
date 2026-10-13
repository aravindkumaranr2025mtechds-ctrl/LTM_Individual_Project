# Mentor demo guide

## Opening explanation

“This application supports construction planning from activity and resource inputs. Separate bounded agents check task dependencies, workers, equipment, materials, cost and delay risks. The coordinator produces a feasible schedule or explains why activities are blocked. A site engineer reviews the results.”

## Suggested demonstration

1. Launch `START_WINDOWS.bat`. Explain that this application has a new construction-planning interface.
2. Identify the sample's label: illustrative inputs, not live industrial data.
3. Click **Generate plan**. Show 12 scheduled activities, 31 days, estimated cost ₹835,700, and high risk because the entered budget and 30-day target are exceeded.
4. Open **Schedule** and enable **Show dependency baseline**. Explain the 26-day baseline versus 31-day resource-feasible schedule. Show A03 and A04: both need the single crane and 6 workers, so they cannot overlap under the entered limits.
5. Open **Activities**, edit an activity and identify its duration, predecessors, crew/equipment quantities and total material requirement. Cancel to retain the sample.
6. Open **Resources**. Show site crew capacity 10, crane capacity 1, and cement delivery on interface Day 13. Demonstrate that rates and availability are user inputs.
7. Open **What-if studio**, select **Site crew**, enter **+2** and compare. Read the calculated before/after result. Explain that equipment and dependency constraints may remain. Do not promise a specific improvement before seeing the result.
8. Click **Apply as draft** only if you want the change. Then **Generate plan** saves the new version and run.
9. Demonstrate a shortage: compare crane capacity change **-1**. The affected activity and descendants become blocked. This is intentional constraint handling, not an application failure. Do not apply unless you want this draft.
10. Open **Reports & agents**. Explain the cost breakdown and agent trace. Download CSV and show **Print / PDF**.
11. Reopen a saved project through **Projects**. Show that SQLite persists the inputs and planning history.

## How to explain the AI honestly

“The core is a bounded rule-based multi-agent planning workflow. Each Python agent owns a planning concern and the coordinator checks candidate allocations. The optional local LLM summarizes computed results; it does not control the schedule. We have not trained a prediction model or demonstrated real-site productivity improvement.”

## Useful questions and answers

**Why a resource-leveled schedule instead of only CPM?**
CPM explains precedence but can schedule several activities against the same worker or equipment supply. Resource checks make those conflicts visible and delay activities when required.

**Does feasible mean on budget?**
No. Feasible means the entered scheduling and resource constraints were satisfied. Budget and target violations remain visible risk alerts.

**What is the data source?**
The bundled example is authored demonstration input. A real deployment needs site-specific activity, capacity, rate and delivery records.

**Is the result optimal?**
No. Serial schedule generation uses a priority heuristic. Different orderings can produce different schedules. Three scheduling rules and one-resource what-if comparisons are available for review.

**What did you test?**
Dependency order, daily capacity limits, dated material conservation, blocked predecessors, cost arithmetic, validation, saving, revision conflicts and HTTP behavior. See the included validation report for exact verification scope.

**Can it execute site work automatically?**
No. It produces a reviewable draft and exports. Human planners make and approve operational decisions.

**Can it work without internet?**
Yes, with Python already installed. The default server, frontend and planning engine work offline. Optional FastAPI dependency installation, frontend rebuilding dependencies and first-time Ollama model download require internet.
