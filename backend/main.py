import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.core.bootstrap import init_db
from backend.core.config import settings
from backend.deps import limiter
from backend.routes import admin_routes, auth_routes, operations_routes, payloads_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Central licensing, HWID activation, server-authorized operations and admin panel.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — explicit origins only (never "*" with credentials). Empty list in dev
# means same-origin only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-HWID", "X-Grant"],
)

app.include_router(auth_routes.router)
app.include_router(admin_routes.router)
app.include_router(operations_routes.router)
app.include_router(payloads_routes.router)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin_web")
if os.path.isdir(os.path.join(STATIC_DIR, "static")):
    app.mount("/admin/static", StaticFiles(directory=os.path.join(STATIC_DIR, "static")), name="static")


@app.get("/", response_class=HTMLResponse)
def root():
    return "<h3>EasyPhoneUnlock Cloud API is running. Admin panel at <a href='/admin'>/admin</a></h3>"


@app.get("/health")
def health():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/admin", response_class=HTMLResponse)
def admin_panel():
    index_path = os.path.join(STATIC_DIR, "templates", "admin.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>Admin panel template not found.</h3>"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=not settings.is_prod)
