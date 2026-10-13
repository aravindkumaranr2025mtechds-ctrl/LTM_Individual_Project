class DelayRiskAgent:
    """Deterministic flags, not a learned or probabilistic delay prediction."""
    def analyze(self, project, rows, duration, cost, materials):
        alerts = []
        blocked = [r for r in rows if r["status"] == "blocked"]
        if blocked:
            alerts.append({"level": "high", "title": f"{len(blocked)} activities cannot be scheduled",
                           "detail": "Resolve the listed constraints and generate a new plan. Partial schedules are not feasible project plans."})
        slip = max(0, duration - project["target_days"])
        if slip:
            alerts.append({"level": "high", "title": f"Target exceeded by {slip} calendar days",
                           "detail": "Compare capacity scenarios or revise the target after reviewing dependencies."})
        if cost["variance"] < 0:
            alerts.append({"level": "high", "title": "Estimated cost exceeds budget",
                           "detail": "Review resource rates, fixed costs and daily overhead before approving the plan."})
        for m in materials:
            if m["shortfall"]:
                alerts.append({"level": "high", "title": f"Material shortage: {m['name']}",
                               "detail": f"Additional {m['shortfall']:g} {m['unit']} required. Enter a realistic delivery day and regenerate."})
        delayed = [r for r in rows if r["status"] != "blocked" and r["resource_delay"] > 0]
        if delayed:
            alerts.append({"level": "medium", "title": f"{len(delayed)} activities wait for resources or materials",
                           "detail": "See each activity's scheduling reason and compare alternative capacity assumptions."})
        if any(r["critical"] for r in rows):
            alerts.append({"level": "info", "title": "Monitor activities with zero baseline float",
                           "detail": "Critical markers come from the dependency-only CPM analysis. Resource constraints may create additional bottlenecks."})
        return {"level": "high" if any(a["level"] == "high" for a in alerts) else "medium" if delayed else "low",
                "target_overrun": slip, "alerts": alerts}
