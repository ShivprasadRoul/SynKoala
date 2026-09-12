from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.errors import register_exception_handlers


def create_app() -> FastAPI:
    app = FastAPI(title="Synthetic Koala API")
    register_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
