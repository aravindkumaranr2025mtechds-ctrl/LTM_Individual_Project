"""Optional FastAPI transport. Install requirements.txt before using this module."""
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from .service import ApplicationService, ROOT, allowed_request

app = FastAPI(title="BuildPlan Construction Planning API", version="1.0.0")
service = ApplicationService()


@app.middleware("http")
async def local_only(request: Request, call_next):
    if not allowed_request(request.headers.get("host"), request.headers.get("origin")):
        return JSONResponse({"error": "Local same-origin requests only."}, status_code=403)
    return await call_next(request)


@app.api_route("/api/{path:path}", methods=["GET", "POST"])
async def route(path: str, request: Request):
    from starlette.concurrency import run_in_threadpool
    body = None
    if request.method == "POST":
        if "application/json" not in request.headers.get("content-type", ""):
            return JSONResponse({"error": "Use application/json."}, status_code=415)
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > 2_000_000:
                return JSONResponse({"error": "Request too large."}, status_code=413)
        try:
            body = json.loads(data)
        except (ValueError, UnicodeError):
            return JSONResponse({"error": "Invalid JSON request."}, status_code=400)
    status, result = await run_in_threadpool(service.dispatch, request.method, "/api/" + path, body)
    return JSONResponse(result, status_code=status)


app.mount("/", StaticFiles(directory=ROOT / "frontend" / "dist", html=True), name="dashboard")
