import csv
import io


def csv_cell(value):
    value = str(value if value is not None else "")
    # Prevent user-entered activity names becoming spreadsheet formulas.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


class ReportExporter:
    def schedule_csv(self, plan):
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(["Activity ID", "Activity", "Zone", "Status", "Start date", "Finish date (inclusive)",
                         "Duration (calendar days)", "Dependencies", "Baseline float", "Resource wait (days)", "Reason", "Resources"])
        for t in plan["tasks"]:
            writer.writerow([csv_cell(v) for v in [t["id"], t["name"], t["zone"], t["status"], t["start_date"], t["finish_date"],
                             t["duration"], "; ".join(t["dependencies"]), t["slack"], t["resource_delay"], t["reason"],
                             "; ".join(f"{r}: {q:g}" for r, q in t["requirements"].items())]])
        return "\ufeff" + stream.getvalue()
