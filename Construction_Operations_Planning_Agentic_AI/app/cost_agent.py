class CostBudgetAgent:
    """Estimate resource use + task fixed costs + calendar-day overhead."""
    def analyze(self, project, makespan, baseline_days, scheduled_ids):
        resources = {r["id"]: r for r in project["resources"]}
        totals = {"labour": 0, "equipment": 0, "material": 0, "fixed": 0}
        rows = []
        for t in project["tasks"]:
            parts = {"labour": 0, "equipment": 0, "material": 0, "fixed": t["fixed_cost"]}
            for rid, qty in t["requirements"].items():
                r = resources[rid]
                multiplier = 1 if r["kind"] == "material" else t["duration"]
                parts[r["kind"]] += qty * r["rate"] * multiplier
            for k, v in parts.items():
                totals[k] += v
            rows.append({"id": t["id"], "name": t["name"], "scheduled": t["id"] in scheduled_ids,
                         "total": round(sum(parts.values()), 2), **{k: round(v, 2) for k, v in parts.items()}})
        direct = sum(totals.values())
        complete = len(scheduled_ids) == len(project["tasks"])
        overhead = makespan * project["overhead_per_day"]
        return {**{k: round(v, 2) for k, v in totals.items()}, "direct": round(direct, 2),
                "overhead": round(overhead, 2), "total": round(direct + overhead, 2),
                "baseline_total": round(direct + baseline_days * project["overhead_per_day"], 2),
                "budget": project["budget"], "variance": round(project["budget"] - direct - overhead, 2),
                "complete_estimate": complete, "tasks": rows}
