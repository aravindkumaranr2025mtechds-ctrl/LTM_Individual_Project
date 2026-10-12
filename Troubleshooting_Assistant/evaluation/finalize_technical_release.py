"""Verify and archive the supported local development application."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import importlib.metadata
import json
import py_compile
import re
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ROUTES = {
    "/", "/health", "/troubleshoot", "/documents/upload",
    "/documents/process", "/documents/chunk", "/documents/search",
    "/documents/search/abb", "/documents/search/abb/confirm",
    "/development/abb/conditions/check",
    "/development/abb/conditions/stall",
    "/development/abb/conditions/stall/clarify",
    "/development/abb/stall/assist",
    "/development/siemens/licensing/compare",
    "/development/siemens/logfile/answer",
    "/development/troubleshoot", "/assistant/turn",
}
REQUIRED_FILES = {
    "app/integrated.py", "app/main.py", "app/services/assistant_workflow.py",
    "app/services/itrs.py", "app/static/assistant.html", "run_assistant.py",
    "ITRS_DEVELOPMENT.md", "INTEGRATION_CHECKPOINT.md",
    "evaluation/test_itrs.py", "evaluation/evaluate_itrs_development.py",
    "evaluation/evaluate_assistance_development.py",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(command, label):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    output = (result.stdout or "") + (result.stderr or "")
    print(f"\n{label}\n{output.rstrip()}", flush=True)
    require(result.returncode == 0, f"{label} failed.")
    return output


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_checkpoint_sources():
    checkpoints = sorted(
        (ROOT / "checkpoints").glob("integrated_development_*/source_fingerprints.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    require(checkpoints, "No integrated-development source fingerprint checkpoint was found.")
    fingerprint_path = checkpoints[0]
    expected = json.loads(fingerprint_path.read_text(encoding="utf-8"))
    require(isinstance(expected, list) and expected, "The source fingerprint checkpoint is empty or invalid.")
    differences = []
    for item in expected:
        path = ROOT / item["path"]
        if not path.is_file() or path.is_symlink():
            differences.append({"path": item["path"], "reason": "missing_or_not_regular"})
            continue
        actual_size = path.stat().st_size
        actual_hash = sha256(path)
        if actual_size != item["bytes"] or actual_hash != item["sha256"]:
            differences.append({
                "path": item["path"], "reason": "content_changed",
                "expected_bytes": item["bytes"], "actual_bytes": actual_size,
                "expected_sha256": item["sha256"], "actual_sha256": actual_hash,
            })
    require(not differences, "Source fingerprint verification failed: " + json.dumps(differences, indent=2))
    return fingerprint_path, expected


def verify_routes_and_itrs():
    from fastapi.testclient import TestClient
    from app.integrated import app

    paths = set(app.openapi()["paths"])
    missing = sorted(EXPECTED_ROUTES - paths)
    require(not missing, f"Required API routes are missing: {missing}")
    with TestClient(app) as client:
        page = client.get("/assistant")
        require(page.status_code == 200, "Assistant page did not return HTTP 200.")
        require("ITRS development score" in page.text, "ITRS browser display is missing.")
        response = client.post("/assistant/turn", json={
            "mode": "siemens_logfile",
            "answers": {"alarm_scope": "61352_or_61353"},
        })
        require(response.status_code == 200, f"ITRS API smoke test failed: {response.text}")
        body = response.json()
        require(body["source_result"]["answer"] == "_PROTNAME[0]", "Source answer changed.")
        require(body["itrs"]["score"] == 100, "Expected ITRS smoke score was not returned.")
        require(body["itrs"]["calibration_status"] == "not_calibrated", "ITRS calibration label changed.")
    return sorted(paths)


def selected_files():
    allowed = {".py", ".html", ".css", ".js", ".md", ".toml"}
    selected = set()
    for folder_name in ("app", "evaluation"):
        folder = ROOT / folder_name
        for path in folder.rglob("*"):
            if not path.is_file() or path.is_symlink() or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(ROOT)
            report = relative.parts[:2] == ("evaluation", "reports") and path.suffix == ".json"
            if path.suffix in allowed or report:
                selected.add(path)
    for pattern in ("*.py", "*.md", "requirements*.txt", "pyproject.toml"):
        selected.update(path for path in ROOT.glob(pattern) if path.is_file() and not path.is_symlink())
    return sorted(selected)


def main():
    print("FINAL TECHNICAL RELEASE VERIFICATION", flush=True)
    missing_files = sorted(path for path in REQUIRED_FILES if not (ROOT / path).is_file())
    require(not missing_files, f"Required files are missing: {missing_files}")

    python_files = [
        path for parent in (ROOT / "app", ROOT / "evaluation")
        for path in parent.rglob("*.py")
        if "__pycache__" not in path.parts and not path.is_symlink()
    ]
    for path in python_files:
        py_compile.compile(str(path), doraise=True)
    print(f"Python compilation: PASS ({len(python_files)} files)")

    dependency = run([sys.executable, "-m", "pip", "check"], "DEPENDENCY CHECK")
    fingerprint_path, fingerprints = verify_checkpoint_sources()
    print(f"Source fingerprints: PASS ({len(fingerprints)} files)")
    print("Compared with:", fingerprint_path)

    tests = run(
        [sys.executable, "-m", "unittest", "discover", "-s", "evaluation", "-p", "test_*.py"],
        "FULL UNIT AND INTEGRATION SUITE",
    )
    match = re.search(r"Ran (\d+) tests", tests)
    require(match and int(match.group(1)) >= 272, "The full suite did not report at least 272 tests.")
    test_count = int(match.group(1))

    assistance = run(
        [sys.executable, "-m", "evaluation.evaluate_assistance_development"],
        "ASSISTANCE DEVELOPMENT EVALUATION",
    )
    require("Overall: PASS" in assistance, "Assistance evaluation did not report Overall: PASS.")
    itrs = run(
        [sys.executable, "-m", "evaluation.evaluate_itrs_development"],
        "ITRS DEVELOPMENT EVALUATION",
    )
    require("Overall: PASS" in itrs, "ITRS evaluation did not report Overall: PASS.")
    require("Tamper and cap checks: 3/3 passed." in itrs, "ITRS tamper checks were incomplete.")

    routes = verify_routes_and_itrs()
    required_path_count = len(EXPECTED_ROUTES) + 1  # OpenAPI paths plus the hidden /assistant page.
    print(f"Required routes and ITRS smoke check: PASS ({required_path_count} required paths)")

    files = selected_files()
    manifest = [{
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    } for path in files]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    destination = ROOT / "checkpoints" / f"technical_release_{stamp}"
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "code_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (destination / "source_fingerprints.json").write_text(json.dumps(fingerprints, indent=2), encoding="utf-8")
    (destination / "installed_packages.txt").write_text("\n".join(sorted({
        f"{distribution.metadata['Name']}=={distribution.version}"
        for distribution in importlib.metadata.distributions()
        if distribution.metadata.get("Name")
    })) + "\n", encoding="utf-8")
    (destination / "dependency_check.txt").write_text(dependency, encoding="utf-8")

    archive = destination / "technical_release_code_and_reports.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            bundle.write(path, path.relative_to(ROOT).as_posix())

    status = {
        "checkpoint": "supported_local_development_technical_release",
        "created_utc": stamp,
        "technical_verification": "PASS",
        "unit_and_integration_tests": test_count,
        "assistance_development_evaluation": "PASS",
        "itrs_development_evaluation": "PASS",
        "required_routes_verified": required_path_count,
        "archived_files": len(files),
        "source_fingerprints_verified": len(fingerprints),
        "dependency_consistency": "PASS",
        "itrs_version": "itrs_development_v1",
        "itrs_calibration_status": "not_calibrated",
        "diagnostic_accuracy_established": False,
        "automatic_physical_execution_approved": False,
        "scope": "Supported local development workflows and inspected manufacturer sources.",
        "next_research_stage": "Independent expert labels, unused questions, baseline comparison, and ITRS calibration.",
        "openapi_paths": routes,
    }
    (destination / "technical_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")

    print("\nTECHNICAL RELEASE CHECKPOINT CREATED")
    print("Folder:", destination)
    print("Archived code/report files:", len(files))
    print("Verified source fingerprints:", len(fingerprints))
    print("Full tests:", test_count)
    print("Assistance development evaluation: PASS")
    print("ITRS development evaluation: PASS")
    print("Required routes and application smoke check: PASS")
    print("Dependency consistency: PASS")
    print("TECHNICAL RELEASE READINESS: PASS")
    print("ITRS calibration and diagnostic-accuracy validation remain research work.")


if __name__ == "__main__":
    main()
