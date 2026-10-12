# Local development integration

Start from the project root:

    .\.venv\Scripts\python.exe .\run_assistant.py

Open http://127.0.0.1:8000/assistant after application startup completes.
Existing API documentation is at http://127.0.0.1:8000/docs.

The new entry point is `app.integrated:app`, which adds the interface and
`POST /assistant/turn` to the existing application's routes.

## Supported workflows

- ABB Motor stalls: list five source causes, review explicit reports, defer
  unavailable reports, and return insufficient evidence for cause identification.
- Siemens licensing: bounded comparison of descriptions 8080 and 8081, with
  caller-carried clarification counts and conflict handling.
- Siemens logfile: retrieve the source-supported parameter for an explicit
  supported alarm scope, or report insufficient evidence.
- Manual search: existing Siemens exact/semantic search and ABB symptom search
  and confirmation routes, using the previously installed vector stores.

## Conversation behavior

The caller explicitly selects a workflow. Free text does not create machine
facts. The request accepts answers, not an internal AgentState or previous
evidence. Each turn invokes the existing protected loop and validates current
source evidence again. Structured source questions take precedence over LLM
planning; Ollama is used for missing request selections. Model question wording
is replaced with the supported field's question and choices.

Boolean answers are explicit reports. Null means "cannot clarify now" and
defers that report field. Browser state is held in page memory; no server-side
session or browser persistent storage is created. Changing context starts a new
review. Licensing question counts are caller-carried, not a server-enforced
cross-session quota.

## Verification

Before this integration, the user's full suite passed 249 tests with one skip.
The new conversation tests passed against copied manual sources in the assistant
validation environment. Planner responses in those automated API tests are
stubbed; the earlier user checkpoint separately exercised real Ollama.

The installer runs the full suite in the user's environment and checks that
the integrated entry point retains the existing routes and serves the page.
Browser preview was blocked in the assistant environment. Perform the listed
browser acceptance checks locally before declaring the integrated app stable.

    .\.venv\Scripts\python.exe -m unittest discover -s evaluation -p "test_*.py"
    .\.venv\Scripts\python.exe -m evaluation.evaluate_assistance_development

## Scope

This is a local development application for the supported manuals and workflows.
Mappings remain unreviewed. Report support is not diagnosis or proof of a repair.
No action is approved for automatic physical execution. ITRS and field/diagnostic
validation are subsequent work, after integration is confirmed stable.
