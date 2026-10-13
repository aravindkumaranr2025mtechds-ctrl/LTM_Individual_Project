from collections import defaultdict


class RenewableResourceAgent:
    kind = ""

    def check(self, task, start, resources, usage):
        reasons = []
        for rid, qty in task["requirements"].items():
            r = resources[rid]
            if r["kind"] != self.kind:
                continue
            for day in range(start, start + task["duration"]):
                capacity = 0 if day in r["unavailable_days"] else r["capacity"]
                if usage[rid].get(day, 0) + qty > capacity:
                    reasons.append(f"{r['name']} unavailable or fully allocated on day {day + 1}")
                    break
        return reasons


class LabourAllocationAgent(RenewableResourceAgent):
    """Enforce daily crew capacities; quantities represent workers, not worker-days."""
    kind = "labour"


class EquipmentAllocationAgent(RenewableResourceAgent):
    """Enforce equipment units and downtime calendars."""
    kind = "equipment"


class MaterialRequirementAgent:
    """Reserve consumables at activity start against cumulative dated deliveries."""
    def check(self, task, start, resources, consumed):
        reasons = []
        for rid, qty in task["requirements"].items():
            r = resources[rid]
            if r["kind"] != "material":
                continue
            # A new early activity must not steal inventory reserved for a later one.
            days = {start} | {d for d in consumed[rid] if d >= start}
            for day in sorted(days):
                supply = r["stock"] + sum(x["quantity"] for x in r["deliveries"] if x["day"] <= day)
                used = sum(q for d, q in consumed[rid].items() if d <= day)
                if used + qty > supply + 1e-8:
                    reasons.append(f"{r['name']} stock or dated deliveries are insufficient")
                    break
        return reasons

    def report(self, project, consumed):
        rows = []
        for r in project["resources"]:
            if r["kind"] != "material":
                continue
            required = sum(t["requirements"].get(r["id"], 0) for t in project["tasks"])
            supplied = r["stock"] + sum(d["quantity"] for d in r["deliveries"])
            rows.append({"id": r["id"], "name": r["name"], "unit": r["unit"], "required": required,
                         "supplied": supplied, "shortfall": max(0, required - supplied),
                         "reserved": sum(consumed[r["id"]].values())})
        return rows


def baseline_conflicts(project, baseline):
    usage = defaultdict(lambda: defaultdict(float))
    for task in project["tasks"]:
        slot = baseline["tasks"][task["id"]]
        for rid, qty in task["requirements"].items():
            for day in range(slot["start"], slot["finish"]):
                usage[rid][day] += qty
    conflicts = []
    for r in project["resources"]:
        if r["kind"] == "material":
            continue
        over = []
        for day, demand in sorted(usage[r["id"]].items()):
            cap = 0 if day in r["unavailable_days"] else r["capacity"]
            if demand > cap:
                over.append({"day": day, "demand": demand, "capacity": cap})
        if over:
            conflicts.append({"id": r["id"], "resource": r["name"], "kind": r["kind"],
                              "days": over, "peak_demand": max(d["demand"] for d in over)})
    return conflicts
