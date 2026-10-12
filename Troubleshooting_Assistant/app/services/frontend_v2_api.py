"""Development preview route for Industrial Technician Workspace V2."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse


router = APIRouter()


_PAGE = (
    Path(__file__).resolve()
    .parents[1]
    / "static"
    / "assistant_v2.html"
)


@router.get(
    "/development/ui/v2",
    include_in_schema=True,
)
def frontend_v2():
    """Return the non-destructive Frontend V2 preview."""

    return FileResponse(
        _PAGE,
        media_type="text/html",
    )
