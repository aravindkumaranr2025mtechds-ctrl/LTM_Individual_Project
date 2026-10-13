# Validation record

BuildPlan 1.0.0 · 8 October 2026 (IST)

## Results

| Check | Result |
|---|---|
| Python unit, service and real HTTP tests | 26 tests PASS |
| Randomized dependency/resource cases | 40 seeded cases checked within the invariant test |
| React/Vite production build | PASS |
| Optional FastAPI adapter | Health, HTML, sample, saved plan and cross-origin rejection PASS |
| Browser demo and saved planning run | PASS |
| Activity editing and schedule recalculation | PASS |
| Referenced-task delete protection and circular-dependency recovery | PASS |
| Resource editing and scenario comparison/application | PASS |
| CSV/JSON downloads and print rendering | PASS |
| Persistence after browser reload | PASS |
| JSON import and historical-input restoration | PASS |
| Empty project, resource/task creation and task deletion | PASS |
| Desktop rendering and six mobile navigation views | PASS; no body overflow |
| JavaScript runtime errors during browser checks | None |

`TEST_OUTPUT.txt` records the Python test output. The repeatable tests are included in `tests/`.

Environment: Linux, Python 3.12, Node.js 24, React 19.2, Vite 7.2.2, Chromium through Playwright. The optional FastAPI 0.142.3 adapter was exercised with TestClient. The offline Python launcher was used for browser tests.

The Windows batch launcher is included but was not executed on a native Windows host. The core uses Python 3.10+ standard-library features. A live Ollama/model response was not tested; the optional integration must be exercised against the user's local service.

## Reproduce core checks

```text
python -m unittest discover -s tests -v
```

No third-party testing packages are needed for those 26 tests.

## Optional browser regression

For developers with Node and Playwright installed:

```text
npm install --no-save playwright
npx playwright install chromium
node tests/ui_smoke.cjs
```

Run these from the project root. This is an optional development workflow and requires internet for installing test tools. The browser script uses a temporary database and port 8792. It does not modify normal saved projects. Set BUILDPLAN_PYTHON if the Python executable is named differently.

## Interpretation

These checks establish behavior on demonstration and generated test cases. They do not establish real-site productivity improvement, optimal schedules, industrial safety compliance or production readiness. No trained-model accuracy, research p-values or live-site validation results are claimed.
