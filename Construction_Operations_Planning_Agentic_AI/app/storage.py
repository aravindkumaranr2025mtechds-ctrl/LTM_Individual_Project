"""SQLite persistence with optimistic project revisions and immutable planning runs."""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .activity_manager import ValidationError


class ConflictError(ValidationError):
    pass


class ProjectRepository:
    def __init__(self, path=None):
        self.path = Path(path or os.environ.get("BUILDPLAN_DB", Path(__file__).resolve().parents[1] / "data" / "buildplan.sqlite3"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                  id TEXT PRIMARY KEY, name TEXT NOT NULL, payload TEXT NOT NULL,
                  revision INTEGER NOT NULL, updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs (
                  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, payload TEXT NOT NULL,
                  created TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS runs_project ON runs(project_id, created);
            """)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def list(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT id,name,revision,updated FROM projects ORDER BY updated DESC")]

    def get(self, project_id):
        with self.connect() as db:
            r = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if not r:
                raise KeyError("Project not found.")
            return {"id": r["id"], "revision": r["revision"], "project": json.loads(r["payload"]), "updated": r["updated"]}

    def save(self, project, project_id=None, revision=None, plan=None):
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if project_id:
                current = db.execute("SELECT revision FROM projects WHERE id=?", (project_id,)).fetchone()
                if not current:
                    raise KeyError("Project not found.")
                if revision != current["revision"]:
                    raise ConflictError("This project changed in another window. Reload it before saving, or import the draft as a new project.")
                revision += 1
                db.execute("UPDATE projects SET name=?,payload=?,revision=?,updated=? WHERE id=?", (project["name"], json.dumps(project), revision, now, project_id))
            else:
                project_id, revision = uuid.uuid4().hex, 1
                db.execute("INSERT INTO projects VALUES (?,?,?,?,?)", (project_id, project["name"], json.dumps(project), revision, now))
            run_id = None
            if plan is not None:
                run_id = uuid.uuid4().hex
                db.execute("INSERT INTO runs VALUES (?,?,?,?)", (run_id, project_id, json.dumps(plan), now))
        return {"id": project_id, "revision": revision, "run_id": run_id, "updated": now}

    def history(self, project_id):
        with self.connect() as db:
            result = []
            for r in db.execute("SELECT id,created,payload FROM runs WHERE project_id=? ORDER BY created DESC LIMIT 20", (project_id,)):
                p = json.loads(r["payload"])
                result.append({"id": r["id"], "created": r["created"], "summary": p["summary"], "cost": p["cost"]["total"]})
            return result

    def run(self, run_id):
        with self.connect() as db:
            r = db.execute("SELECT payload FROM runs WHERE id=?", (run_id,)).fetchone()
            if not r:
                raise KeyError("Planning run not found.")
            return json.loads(r["payload"])
