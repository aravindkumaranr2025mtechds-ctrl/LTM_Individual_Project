"""Shared application routes for zero-install and optional FastAPI servers."""
import copy
import json
from pathlib import Path
from urllib.parse import urlsplit
from .activity_manager import ActivityManager, ValidationError, require, number
from .coordinator import AgenticCoordinator
from .storage import ProjectRepository, ConflictError
from .reporting import ReportExporter
from .llm_advisor import LocalLLMAdvisor

ROOT = Path(__file__).resolve().parents[1]


class ApplicationService:
    def __init__(self, db_path=None):
        self.repository = ProjectRepository(db_path)

    def dispatch(self, method, path, body=None):
        path = urlsplit(path).path.rstrip("/")
        body = body or {}
        try:
            require(isinstance(body, dict), "Request body must be an object.")
            if method == "GET" and path == "/api/health":
                return 200, {"status": "ok", "application": "BuildPlan", "version": "1.0.0"}
            if method == "GET" and path == "/api/sample":
                return 200, json.loads((ROOT / "examples" / "demo_project.json").read_text(encoding="utf-8"))
            if method == "GET" and path == "/api/projects":
                return 200, self.repository.list()
            if method == "GET" and path.startswith("/api/projects/"):
                pieces = path.split("/")
                if len(pieces) == 5 and pieces[-1] == "history":
                    return 200, self.repository.history(pieces[3])
                if len(pieces) == 4:
                    return 200, self.repository.get(pieces[3])
            if method == "GET" and path.startswith("/api/runs/"):
                return 200, self.repository.run(path.rsplit("/", 1)[1])
            if method == "POST" and path == "/api/projects":
                project = ActivityManager().validate(body.get("project"))
                return 200, self.repository.save(project, body.get("project_id"), body.get("revision"))
            if method == "POST" and path in ("/api/plan", "/api/preview"):
                plan = AgenticCoordinator().plan(body.get("project"))
                if path == "/api/plan":
                    plan["saved"] = self.repository.save(plan["project"], body.get("project_id"), body.get("revision"), plan)
                return 200, plan
            if method == "POST" and path == "/api/scenario":
                base = ActivityManager().validate(body.get("project"))
                changed = copy.deepcopy(base)
                rid = body.get("resource_id")
                r = next((r for r in changed["resources"] if r["id"] == rid), None)
                require(r is not None, "Select a resource for the scenario.")
                amount = number(body.get("amount"), "Scenario change", -1e8, 1e8)
                if r["kind"] == "material":
                    r["stock"] += amount
                else:
                    r["capacity"] += amount
                original, alternative = AgenticCoordinator().plan(base), AgenticCoordinator().plan(changed)
                comparable = original["summary"]["feasible"] and alternative["summary"]["feasible"]
                return 200, {"original": original, "alternative": alternative, "comparable": comparable,
                             "days_saved": original["summary"]["duration"] - alternative["summary"]["duration"] if comparable else None,
                             "cost_change": round(alternative["cost"]["total"] - original["cost"]["total"], 2) if comparable else None}
            if method == "POST" and path == "/api/export/csv":
                plan = AgenticCoordinator().plan(body.get("project"))
                return 200, {"filename": "construction_schedule.csv", "content": ReportExporter().schedule_csv(plan)}
            if method == "POST" and path == "/api/advisor":
                plan = AgenticCoordinator().plan(body.get("project"))
                return 200, LocalLLMAdvisor().explain(plan)
            return 404, {"error": "Route not found."}
        except ConflictError as exc:
            return 409, {"error": str(exc)}
        except ValidationError as exc:
            return 422, {"error": str(exc)}
        except KeyError as exc:
            return 404, {"error": str(exc).strip("'")}


def allowed_request(host, origin):
    """Local browser origins only. No cross-origin API writes."""
    if not host or host.split(":")[0].lower() not in ("127.0.0.1", "localhost", "testserver"):
        return False
    return not origin or urlsplit(origin).netloc.lower() == host.lower()
