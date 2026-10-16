"""VulnerableShop FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.database import init_db
from app.routes import orders, products, utilities

logger = logging.getLogger("vulnerable_shop")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="VulnerableShop",
    description="Test target for a security scanning and remediation pipeline. Not for production.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(products.router)
app.include_router(orders.router)
app.include_router(utilities.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
