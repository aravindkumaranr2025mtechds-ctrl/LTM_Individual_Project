"""Application entry point combining existing APIs and the local interface."""
from app.main import app
from app.services.assistant_workflow import router

if not getattr(app.state, "assistant_workflow_registered", False):
    app.include_router(router)
    app.state.assistant_workflow_registered = True
    app.openapi_schema = None
