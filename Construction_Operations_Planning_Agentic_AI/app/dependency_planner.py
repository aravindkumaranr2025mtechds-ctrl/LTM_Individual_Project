class DependencyPlanner:
    """CPM forward/backward pass using calendar-day, finish-to-start dependencies."""
    def analyze(self, project):
        tasks = {t["id"]: t for t in project["tasks"]}
        order, early, pending = [], {}, set(tasks)
        while pending:
            ready = sorted(tid for tid in pending if all(d in early for d in tasks[tid]["dependencies"]))
            for tid in ready:
                t = tasks[tid]
                start = max([t["release_day"]] + [early[d]["finish"] for d in t["dependencies"]])
                early[tid] = {"start": start, "finish": start + t["duration"]}
                order.append(tid)
                pending.remove(tid)
        duration = max(x["finish"] for x in early.values())
        latest = {}
        for tid in reversed(order):
            successors = [i for i, t in tasks.items() if tid in t["dependencies"]]
            finish = min((latest[i]["start"] for i in successors), default=duration)
            latest[tid] = {"start": finish - tasks[tid]["duration"], "finish": finish}
            early[tid]["slack"] = latest[tid]["start"] - early[tid]["start"]
            early[tid]["critical"] = early[tid]["slack"] == 0
        return {"order": order, "tasks": early, "duration": duration,
                "critical_ids": [i for i in order if early[i]["critical"]]}
