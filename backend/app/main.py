from fastapi import Depends, FastAPI

from app.api import devices, groups, health, sync
from app.security import require_internal


def create_app() -> FastAPI:
    app = FastAPI(title="Janus")
    app.include_router(health.router)
    protected = [Depends(require_internal)]
    app.include_router(groups.router, dependencies=protected)
    app.include_router(devices.router, dependencies=protected)
    app.include_router(sync.router, dependencies=protected)
    return app


app = create_app()
