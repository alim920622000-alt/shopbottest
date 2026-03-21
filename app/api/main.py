from __future__ import annotations
import os
import uvicorn
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from app.api.routes.auth import router as auth_router
from app.api.routes.catalog import router as catalog_router
from app.api.routes.chats import router as chats_router
from app.api.routes.profile import router as profile_router
from app.api.routes.orders import router as orders_router
from app.db.database import DBConfig, Database
from fastapi.openapi.utils import get_openapi

def custom_openapi(app: FastAPI):
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description="API ShopBot",
        routes=app.routes,
    )
    openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {})
    openapi_schema["components"]["securitySchemes"]["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
    openapi_schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

def create_app() -> FastAPI:
    app = FastAPI(title="ShopBot API", version="0.1.0")

    dsn = os.getenv("DB_DSN", "")
    app.state.db = Database(DBConfig(dsn=dsn))

    app.include_router(auth_router)
    app.include_router(catalog_router)
    app.include_router(orders_router)
    app.include_router(chats_router)
    app.include_router(profile_router)

    @app.get("/health", tags=["system"])
    async def health() -> dict:
        return {"ok": True}

    app.openapi = lambda: custom_openapi(app)
    return app

app = create_app()
if __name__ == "__main__":
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=int(os.getenv("API_PORT", "8000")), reload=False)
