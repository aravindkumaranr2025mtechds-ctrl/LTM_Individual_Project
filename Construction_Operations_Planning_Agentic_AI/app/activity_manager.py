"""Input normalization and validation, independent of the web framework."""
import copy
import math
import re
from datetime import date


class ValidationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def number(value, label, low=0, high=1e10, integer=False):
    require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{label} must be a number.")
    require(math.isfinite(value) and low <= value <= high, f"{label} must be between {low:g} and {high:g}.")
    require(not integer or int(value) == value, f"{label} must be a whole number.")
    return int(value) if integer else float(value)


def text(value, label, limit=160):
    require(isinstance(value, str) and 0 < len(value.strip()) <= limit, f"{label} is required (maximum {limit} characters).")
    return value.strip()


class ActivityManager:
    """Check project fields, references, resource demands, and dependency cycles."""
    def validate(self, payload):
        require(isinstance(payload, dict), "The project must be a JSON object.")
        p = copy.deepcopy(payload)
        p["name"] = text(p.get("name"), "Project name")
        p["location"] = text(p.get("location", "Site location"), "Location")
        p["data_source"] = text(p.get("data_source", "User-entered planning assumptions"), "Data source", 500)
        try:
            p["start_date"] = date.fromisoformat(p.get("start_date", "")).isoformat()
        except (ValueError, TypeError):
            raise ValidationError("Start date must use YYYY-MM-DD.")
        require(int(p["start_date"][:4]) <= 2090, "Start date must be before 2091.")
        p["budget"] = number(p.get("budget", 0), "Budget")
        p["overhead_per_day"] = number(p.get("overhead_per_day", 0), "Daily overhead")
        p["target_days"] = number(p.get("target_days", 90), "Target duration", 1, 2000, True)
        p["strategy"] = p.get("strategy", "critical")
        require(p["strategy"] in ("critical", "priority", "shortest"), "Unknown planning strategy.")
        resources = p.get("resources")
        tasks = p.get("tasks")
        require(isinstance(resources, list) and 1 <= len(resources) <= 40, "Provide 1 to 40 resources.")
        require(isinstance(tasks, list) and 1 <= len(tasks) <= 80, "Provide 1 to 80 activities.")
        resource_map = {}
        for r in resources:
            require(isinstance(r, dict), "Each resource must be an object.")
            rid = text(r.get("id"), "Resource ID", 40)
            require(re.fullmatch(r"[A-Za-z0-9_-]+", rid), "Resource IDs must use letters, digits, underscores or hyphens.")
            require(rid not in resource_map, f"Duplicate resource ID: {rid}.")
            r["id"] = rid
            r["name"] = text(r.get("name"), f"Name for {rid}")
            require(r.get("kind") in ("labour", "equipment", "material"), f"Unknown resource kind for {rid}.")
            r["unit"] = text(r.get("unit", "units"), f"Unit for {rid}", 30)
            r["rate"] = number(r.get("rate", 0), f"Rate for {rid}")
            r["capacity"] = number(r.get("capacity", 0), f"Capacity for {rid}", 0, 10000, True)
            r["stock"] = number(r.get("stock", 0), f"Stock for {rid}")
            require(isinstance(r.get("deliveries", []), list) and len(r.get("deliveries", [])) <= 40, "Maximum 40 deliveries per resource.")
            r["deliveries"] = r.get("deliveries", [])
            for delivery in r["deliveries"]:
                require(isinstance(delivery, dict), "Each delivery must be an object.")
                delivery["day"] = number(delivery.get("day"), "Delivery day", 0, 1999, True)
                delivery["quantity"] = number(delivery.get("quantity"), "Delivery quantity", 0)
            require(isinstance(r.get("unavailable_days", []), list) and len(r.get("unavailable_days", [])) <= 2000, "Unavailable days must be a list of up to 2000 day offsets.")
            r["unavailable_days"] = sorted(set(number(d, "Unavailable day", 0, 1999, True) for d in r.get("unavailable_days", [])))
            resource_map[rid] = r
        task_map = {}
        for task in tasks:
            require(isinstance(task, dict), "Each activity must be an object.")
            tid = text(task.get("id"), "Activity ID", 40)
            require(re.fullmatch(r"[A-Za-z0-9_-]+", tid), "Activity IDs must use letters, digits, underscores or hyphens.")
            require(tid not in task_map, f"Duplicate activity ID: {tid}.")
            task["id"] = tid
            task["name"] = text(task.get("name"), f"Name for {tid}")
            task["zone"] = text(task.get("zone", "Site"), f"Zone for {tid}", 80)
            task["duration"] = number(task.get("duration"), f"Duration for {tid}", 1, 180, True)
            task["priority"] = number(task.get("priority", 3), f"Priority for {tid}", 1, 5, True)
            task["release_day"] = number(task.get("release_day", 0), f"Earliest start for {tid}", 0, 1999, True)
            task["fixed_cost"] = number(task.get("fixed_cost", 0), f"Fixed cost for {tid}")
            deps = task.get("dependencies", [])
            require(isinstance(deps, list) and all(isinstance(d, str) for d in deps), f"Dependencies for {tid} must be activity IDs.")
            task["dependencies"] = list(dict.fromkeys(deps))
            reqs = task.get("requirements", {})
            require(isinstance(reqs, dict), f"Requirements for {tid} must map resource IDs to quantities.")
            clean = {}
            for rid, qty in reqs.items():
                require(rid in resource_map, f"{tid} refers to missing resource {rid}.")
                clean[rid] = number(qty, f"{tid} demand for {rid}", 0, 1e8, resource_map[rid]["kind"] != "material")
            task["requirements"] = {k: v for k, v in clean.items() if v > 0}
            task_map[tid] = task
        for task in tasks:
            for dep in task["dependencies"]:
                require(dep in task_map, f"{task['id']} depends on missing activity {dep}.")
                require(dep != task["id"], f"{dep} cannot depend on itself.")
        pending = set(task_map)
        resolved = set()
        while pending:
            ready = {tid for tid in pending if set(task_map[tid]["dependencies"]) <= resolved}
            require(bool(ready), "Circular dependencies detected. Remove the dependency loop before planning.")
            resolved.update(ready)
            pending -= ready
        return p
