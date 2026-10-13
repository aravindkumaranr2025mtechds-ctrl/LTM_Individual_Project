# Local API reference

Base URL: `http://127.0.0.1:8765`. Both server modes share these routes. Use `Content-Type: application/json` for POST requests. Requests are limited to 2 MB. Browser origins must match the server's host/port.

| Method | Path | Purpose / request |
|---|---|---|
| GET | `/api/health` | Application status and version. |
| GET | `/api/sample` | Included demonstration project JSON. |
| GET | `/api/projects` | Saved project metadata. |
| GET | `/api/projects/{id}` | Saved input, revision and timestamp. |
| POST | `/api/projects` | Validate/save inputs: `{ "project": {...}, "project_id": null, "revision": null }`. |
| POST | `/api/preview` | Compute without saving: `{ "project": {...} }`. |
| POST | `/api/plan` | Compute and save inputs/run. Same request fields as project save. |
| GET | `/api/projects/{id}/history` | Latest 20 run summaries. |
| GET | `/api/runs/{id}` | Immutable full historical result. |
| POST | `/api/scenario` | `{ "project": {...}, "resource_id": "crew", "amount": 2 }`. Does not save. |
| POST | `/api/export/csv` | `{ "project": {...} }`; returns CSV filename/content as JSON. |
| POST | `/api/advisor` | `{ "project": {...} }`; computes plan then asks local Ollama for an explanation. |

For updates, pass the project ID and current revision from the last successful read/save. A stale revision returns 409. Omitting the ID creates a new project. Input validation returns 422, missing routes/items return 404, and disallowed origins return 403.

Read `examples/demo_project.json` for a complete importable schema. Additional project fields may be retained but have no scheduling effect unless documented.

Minimal example project:

```json
{
  "name": "Small site plan",
  "location": "Chennai",
  "start_date": "2026-10-12",
  "budget": 100000,
  "overhead_per_day": 1000,
  "target_days": 10,
  "strategy": "critical",
  "data_source": "User-entered assumptions",
  "resources": [
    {"id": "crew", "name": "Site crew", "kind": "labour", "unit": "workers", "capacity": 4, "rate": 850}
  ],
  "tasks": [
    {"id": "A01", "name": "Site preparation", "duration": 2, "priority": 5, "dependencies": [], "requirements": {"crew": 4}},
    {"id": "A02", "name": "Set-out survey", "duration": 1, "priority": 4, "dependencies": ["A01"], "requirements": {"crew": 2}}
  ]
}
```

A plan response contains normalized `project`, per-activity `tasks`, CPM `baseline`, renewable-resource baseline `conflicts`, daily `resources`, `materials`, `cost`, `risk`, `trace`, and `summary`. Persisted plans also return `saved` metadata. `summary.feasible` means all entered scheduling/resource constraints were satisfied; it does not mean the budget/target was met or that the plan was approved.

Only local operation is supported. These endpoints do not provide authentication for shared hosting.
