# Implementation mapping and methodology

Project: Construction Operations Planning and Resource Allocation Using Agentic AI.
Reference: supplied T9977_REC_Rev3_Project2.pptx, especially slides 4, 6, 7 and 8.

## PPT module mapping

| PPT module | File | Main class / component | Responsibility |
|---|---|---|---|
| Project Input and Activity Manager | `app/activity_manager.py`; `app/storage.py` | `ActivityManager`; `ProjectRepository` | Validate input, enforce IDs/references, detect dependency cycles; save projects and immutable runs in SQLite. |
| Task Dependency Planning Module | `app/dependency_planner.py` | `DependencyPlanner` | Forward/backward CPM passes, early starts/finishes, float and dependency baseline. |
| Labour Allocation Module | `app/resource_agents.py` | `LabourAllocationAgent` | Check each occupied day's worker demand against available crew capacity. |
| Equipment Allocation Module | `app/resource_agents.py` | `EquipmentAllocationAgent` | Enforce shared equipment quantities and equipment downtime. |
| Material Requirement Module | `app/resource_agents.py` | `MaterialRequirementAgent` | Check cumulative supplies and reservations; report total shortfalls. |
| Cost and Budget Tracking Module | `app/cost_agent.py` | `CostBudgetAgent` | Calculate task direct cost, overhead, total estimate and budget variance. |
| Delay and Risk Analysis Module | `app/risk_agent.py` | `DelayRiskAgent` | Flag blocked tasks, missed targets, material shortages, budget overruns and waits. |
| Agentic Coordination Controller | `app/coordinator.py` | `AgenticCoordinator` | Rank eligible activities; consult agents; commit valid reservations; return reasons, plan and audit trace. |
| Planning Dashboard and Reports | `frontend/src/main.jsx`; `app/reporting.py` | `App`, `Overview`, `Schedule`, `Activities`, `Resources`, `Scenario`, `Reports`; `ReportExporter` | Render views, edit inputs, compare scenarios, export JSON/CSV, print report. |

Other classes: `ApplicationService` (`app/service.py`) shares business routes between adapters. `LocalLLMAdvisor` (`app/llm_advisor.py`) generates optional local text. `ValidationError` represents input errors; `ConflictError` prevents stale overwrites. `RenewableResourceAgent` is the base class for crew/equipment checks.

Server choices: `app/server.py` provides a standard-library `ThreadingHTTPServer` for offline startup. `app/api.py` exposes the same application service through FastAPI. SQLite and the planning engine are shared.

## Workflow

1. Receive structured project inputs from forms or JSON import.
2. Validate dates, finite quantities, unique IDs, references, durations and cycles. Normalize default fields and remove zero resource demands.
3. Compute the dependency-only baseline.
4. Select an eligible activity according to the chosen priority rule.
5. Check labour, equipment and cumulative material availability for each candidate slot.
6. Commit the first feasible slot and reserve its resources. If none exists within the bound, block the task and its descendants.
7. Calculate requested direct costs, schedule overhead, variance and rule-based risk flags.
8. Return the schedule, reasons, resource loads and agent trace; save the plan when explicitly generated.
9. Allow human review, scenario comparison and report export.

All agents are explicit Python classes with constrained responsibilities. The coordinator's decision space is activity ordering and feasible start slots. External actions are outside the system's scope. This is a rule-based multi-agent prototype, not a multi-LLM autonomous planning system.

## Algorithms and formulas

Let activity i have duration d_i, release day r_i, predecessor set P_i, and resource demand q_ir. Time uses zero-based calendar-day offsets.

### Dependency baseline (CPM)

- ES_i = max(r_i, max(EF_j for j in P_i)). For no predecessors, use r_i.
- EF_i = ES_i + d_i.
- Baseline makespan T0 = max(EF_i).
- LF_i = min(LS_k for successors k); terminal activities use T0.
- LS_i = LF_i - d_i.
- Total float_i = LS_i - ES_i.

Activities with zero total float are highlighted. The baseline ignores resource constraints and material availability. Release dates remain constraints.

Example: task A occupies offsets [0,2). Task B depends on A and lasts 3 days, so B's baseline starts at offset 2 and finishes at 5. On the interface A occupies days 1–2 and B occupies days 3–5.

### Serial resource-constrained schedule generation

The eligible set contains activities whose predecessors have already been scheduled or blocked. Rank by one of:

1. **Critical:** smallest baseline float, then highest priority, then earliest baseline start, then activity ID.
2. **Priority:** highest priority, then smallest float, then earliest baseline start, then ID.
3. **Shortest:** shortest duration, then highest priority, then smallest float, then ID.

For a selected activity, candidate starts begin at max(release day, actual predecessor finishes). Test each start until all resource checks pass. Search ends at day offset 2000; no infinite retry loop is possible.

For renewable resource r on every occupied day t:

`sum(q_ir for scheduled activities active on t) + candidate_demand <= capacity_r(t)`

Capacity is zero on a resource's unavailable days. Otherwise it is the entered daily capacity. Activities are not split to fit fragmented availability.

Example: two activities each require 6 workers, but capacity is 10. The 12-worker overlap is infeasible, so the second activity waits. A scenario with 12 workers may remove that wait, subject to equipment and dependencies.

This is a deterministic heuristic for a resource-constrained scheduling problem. It does not enumerate all orderings and has no global optimality claim. Increased capacity is not guaranteed to improve this heuristic's schedule in every case.

### Materials

At each relevant day t:

`remaining_r(t) = initial_stock_r + sum(deliveries_r up to t) - sum(consumption_r up to t)`

Require remaining_r(t) >= 0. Consumption occurs at task start. A proposed activity is checked at its start and at all already-reserved future consumption events, preventing it from stealing material reserved for later scheduled tasks. Delivery-only events increase inventory and cannot introduce a new minimum.

Example: initial stock is 5 bags; 5 more arrive on offset 4. A task needing 10 bags starts no earlier than interface Day 5. Materials are charged once, not once per occupied day.

### Cost

`labour cost_i = sum(labour quantity × daily rate × duration)`

`equipment cost_i = sum(equipment units × daily rate × duration)`

`material cost_i = sum(material quantity × unit rate)`

`direct cost = sum(activity labour + equipment + material + fixed costs)`

`overhead = scheduled makespan × daily site overhead`

`estimated total = direct cost + overhead`

`budget variance = entered budget - estimated total`

Positive variance is within budget. Negative variance is over budget. This is a planning estimate at user-provided rates. Fixed capacities do not automatically create idle standby charges. If the plan is partial, the overhead is incomplete and the estimate is labelled accordingly.

### Utilization and delay

`resource utilization (%) = allocated unit-days / available capacity-days over scheduled makespan × 100`

Days marked unavailable contribute zero available capacity. Utilization is reported as zero when available capacity-days are zero; blocked tasks remain separately visible.

`resource wait_i = scheduled start_i - max(release day_i, scheduled predecessor finishes)`

`baseline shift_i = scheduled start_i - baseline ES_i`

`target overrun = max(0, scheduled makespan - entered target duration)`

Resource wait excludes inherited predecessor delay. Target overrun for a partial plan does not establish a complete project finish date.

### Risk rules

- High if at least one task is blocked, the scheduled duration exceeds target, material totals are short, or estimated total exceeds budget.
- Medium if no high trigger occurs but activities wait for resources/materials.
- Low otherwise.
- Zero baseline float produces an informational monitoring alert.

These labels are rule-based, not learned probabilities or quantitative safety assessments.

## Data and training

The package does not contain a trained machine-learning model or a scraped dataset. The sample was authored to exercise dependencies, resource competition, dated material supply, costs and risk rules. It is clearly labelled as illustrative.

Project-specific input is appropriate because feasibility depends on the site's actual task durations, dependencies, capacities, rates and deliveries. A generic dataset cannot establish those facts. Real validation requires site records, a qualified planner's reference schedule and actual outcomes; these have not been supplied.

Data quality controls include explicit units, types/ranges, cycle rejection, unique IDs, missing-reference rejection, consistent date conventions and conservation checks in tests. Automated tests verify software behavior on fixtures. They do not prove reduced real-site cost or delay.

## Frontend method

The dashboard replaces conversational troubleshooting with a planning workspace:

- Overview gives schedule/cost/status summaries and attention items.
- Schedule combines Gantt bars, optional dependency baseline and allocation reasons.
- Activities and Resources expose editable business inputs.
- What-if Studio compares a single change and requires explicit draft application.
- Reports & Agents exposes calculations, agent decisions, exports and historical runs.

No public web service is required. Bundled fonts use the operating system's font stack. React/Vite source and compiled assets are included.

## PPT observations

Slides 4, 6, 7 and 8 drive the implementation. Slide 10 still contains acknowledgement text about troubleshooting and diagnostic reliability; it is unrelated to this construction application and was not implemented. The literature list in slide 11 was not independently verified and is not treated as evidence for software results. The original PPT is unchanged.
