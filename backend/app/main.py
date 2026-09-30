from fastapi import FastAPI

from app.api import health


def create_app() -> FastAPI:
    app = FastAPI(title="Janus")
    app.include_router(health.router)
    return app


app = create_app()
