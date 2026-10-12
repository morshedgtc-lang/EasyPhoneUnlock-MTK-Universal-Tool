import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from backend.models.db import DatabaseManager
from backend.routes import auth_routes, admin_routes, credits_routes

app = FastAPI(
    title="EasyPhoneUnlock Cloud Admin API",
    description="Central licensing, HWID activation, credit system and admin control panel.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
DatabaseManager.init_db()

app.include_router(auth_routes.router)
app.include_router(admin_routes.router)
app.include_router(credits_routes.router)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin_web")
if os.path.isdir(os.path.join(STATIC_DIR, "static")):
    app.mount("/admin/static", StaticFiles(directory=os.path.join(STATIC_DIR, "static")), name="static")

@app.get("/", response_class=HTMLResponse)
def root():
    return "<h3>EasyPhoneUnlock Cloud API is running. Admin panel at <a href='/admin'>/admin</a></h3>"

@app.get("/admin", response_class=HTMLResponse)
def admin_panel():
    index_path = os.path.join(STATIC_DIR, "templates", "admin.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>Admin panel template not found.</h3>"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
