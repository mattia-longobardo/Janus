from fastapi import Depends, FastAPI

from app.api import approval, devices, events, groups, health, intel, maintenance, notifications, sync
from app.security import require_internal


def create_app() -> FastAPI:
    app = FastAPI(title="Janus")
    app.include_router(health.router)
    protected = [Depends(require_internal)]
    for router in (groups.router, devices.router, approval.router, sync.router,
                   notifications.router, maintenance.router, events.router, intel.router):
        app.include_router(router, dependencies=protected)
    return app


app = create_app()
