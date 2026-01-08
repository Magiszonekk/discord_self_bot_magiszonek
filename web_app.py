import os
import random
import asyncio
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Request, Form, HTTPException, Depends, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from db_utils import (
    get_all_statuses, add_status_request, remove_status, approve_status_by_id,
    get_approved_statuses, get_all_categories, add_category, remove_category,
    get_statuses_by_category, does_status_exist
)
from discord_actions import get_discord_actions
from logging_utils import log, get_logs_closest_to, get_latest_logs, get_log_files
from token_manager import get_token_manager

app = FastAPI(title="Discord Bot Control Panel")

# Session middleware for auth
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("WEB_PASSWORD", "change-me-please"),
    max_age=86400  # 24 hours
)

# Templates and static files
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
static_dir = os.path.join(os.path.dirname(__file__), "static")

os.makedirs(templates_dir, exist_ok=True)
os.makedirs(static_dir, exist_ok=True)

templates = Jinja2Templates(directory=templates_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ============== State Management ==============

class AppState:
    """Manages application state."""

    def __init__(self):
        self.eventsub_running = False
        self.eventsub_task = None
        self.rotation_enabled = True
        self.rotation_task = None
        self.rotation_interval_min = 25
        self.rotation_interval_max = 45
        self.statuses = []

    def reload_statuses(self):
        """Reloads approved statuses from database."""
        self.statuses = get_approved_statuses()


state = AppState()


# ============== Auth Helpers ==============

def get_session(request: Request):
    return request.session


def is_authenticated(request: Request) -> bool:
    return request.session.get("authenticated", False)


def require_auth(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Not authenticated")


# ============== Background Tasks ==============

async def rotation_loop():
    """Background task for status rotation."""
    discord_actions = get_discord_actions()

    while state.rotation_enabled:
        try:
            state.reload_statuses()
            if state.statuses:
                status = random.choice(state.statuses)
                await discord_actions.change_status(status['status'])
                log(f"[ROTATION] Status changed to: {status['status']}", True)
        except Exception as e:
            log(f"[ROTATION] Error: {e}", True, "error")

        sleep_minutes = random.randint(state.rotation_interval_min, state.rotation_interval_max)
        log(f"[ROTATION] Next change in {sleep_minutes} minutes", True)

        # Sleep in small intervals to allow stopping
        for _ in range(sleep_minutes * 60):
            if not state.rotation_enabled:
                break
            await asyncio.sleep(1)

    log("[ROTATION] Rotation stopped", True)


async def start_rotation():
    """Starts the rotation background task."""
    if state.rotation_task is None or state.rotation_task.done():
        state.rotation_enabled = True
        state.rotation_task = asyncio.create_task(rotation_loop())
        log("[ROTATION] Started", True)


async def stop_rotation():
    """Stops the rotation background task."""
    state.rotation_enabled = False
    if state.rotation_task:
        state.rotation_task.cancel()
        try:
            await state.rotation_task
        except asyncio.CancelledError:
            pass
    log("[ROTATION] Stopped", True)


# ============== Auth Routes ==============

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    correct_password = os.getenv("WEB_PASSWORD", "admin")
    if password == correct_password:
        request.session["authenticated"] = True
        log(f"[AUTH] Login successful from {request.client.host}", True)
        return RedirectResponse(url="/", status_code=302)
    else:
        log(f"[AUTH] Login failed from {request.client.host}", True, "warning")
        return templates.TemplateResponse("login.html", {"request": request, "error": "Nieprawidlowe haslo"})


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


# ============== Dashboard ==============

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=302)

    state.reload_statuses()
    all_statuses = get_all_statuses()
    categories = get_all_categories()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "statuses": all_statuses,
        "approved_count": len(state.statuses),
        "categories": categories,
        "eventsub_running": state.eventsub_running,
        "rotation_enabled": state.rotation_enabled,
        "rotation_min": state.rotation_interval_min,
        "rotation_max": state.rotation_interval_max,
    })


# ============== Status API ==============

@app.get("/api/statuses")
async def api_get_statuses(request: Request):
    require_auth(request)
    return get_all_statuses()


@app.get("/api/statuses/approved")
async def api_get_approved_statuses(request: Request):
    require_auth(request)
    return get_approved_statuses()


@app.post("/api/statuses")
async def api_add_status(request: Request, status: str = Form(...), category: str = Form(...)):
    require_auth(request)

    if does_status_exist(status):
        raise HTTPException(status_code=400, detail="Status already exists")

    add_status_request(
        person_name="web_panel",
        person_id=0,
        status=status,
        category=category
    )
    log(f"[WEB] Status added: {status}", True)
    return RedirectResponse(url="/", status_code=302)


@app.post("/api/statuses/{status_id}/delete")
async def api_delete_status(request: Request, status_id: int):
    require_auth(request)
    remove_status(status_id)
    log(f"[WEB] Status deleted: id={status_id}", True)
    return RedirectResponse(url="/", status_code=302)


@app.post("/api/statuses/{status_id}/approve")
async def api_approve_status(request: Request, status_id: int):
    require_auth(request)
    approve_status_by_id(status_id, 0)  # 0 = web panel
    log(f"[WEB] Status approved: id={status_id}", True)
    return RedirectResponse(url="/", status_code=302)


# ============== Category API ==============

@app.get("/api/categories")
async def api_get_categories(request: Request):
    require_auth(request)
    return get_all_categories()


@app.post("/api/categories")
async def api_add_category(request: Request, name: str = Form(...)):
    require_auth(request)
    if " " in name:
        raise HTTPException(status_code=400, detail="Category name cannot contain spaces")
    add_category(created_by_user_id=0, label=name)
    log(f"[WEB] Category added: {name}", True)
    return RedirectResponse(url="/", status_code=302)


@app.post("/api/categories/{name}/delete")
async def api_delete_category(request: Request, name: str):
    require_auth(request)
    remove_category(name)
    log(f"[WEB] Category deleted: {name}", True)
    return RedirectResponse(url="/", status_code=302)


# ============== Discord Actions API ==============

@app.post("/api/discord/change-status")
async def api_change_status(request: Request, status: str = Form(None), random_status: bool = Form(False)):
    require_auth(request)

    discord_actions = get_discord_actions()

    if random_status:
        state.reload_statuses()
        if not state.statuses:
            raise HTTPException(status_code=400, detail="No approved statuses available")
        status = random.choice(state.statuses)['status']

    if not status:
        raise HTTPException(status_code=400, detail="No status provided")

    success = await discord_actions.change_status(status)

    if success:
        log(f"[WEB] Manual status change: {status}", True)
        return RedirectResponse(url="/", status_code=302)
    else:
        raise HTTPException(status_code=500, detail="Failed to change status")


@app.post("/api/discord/send-dm")
async def api_send_dm(request: Request, user_id: int = Form(...), message: str = Form(...)):
    require_auth(request)

    discord_actions = get_discord_actions()
    success = await discord_actions.send_dm(user_id, message)

    if success:
        log(f"[WEB] DM sent to {user_id}", True)
        return RedirectResponse(url="/", status_code=302)
    else:
        raise HTTPException(status_code=500, detail="Failed to send DM")


# ============== EventSub API ==============

@app.get("/api/eventsub/status")
async def api_eventsub_status(request: Request):
    require_auth(request)
    return {"running": state.eventsub_running}


@app.post("/api/eventsub/start")
async def api_eventsub_start(request: Request):
    require_auth(request)
    if not state.eventsub_running:
        from is_live import start_eventsub
        state.eventsub_task = asyncio.create_task(start_eventsub())
        state.eventsub_running = True
        log("[WEB] EventSub started", True)
    return RedirectResponse(url="/", status_code=302)


@app.post("/api/eventsub/stop")
async def api_eventsub_stop(request: Request):
    require_auth(request)
    if state.eventsub_running:
        from is_live import stop_eventsub
        await stop_eventsub()
        if state.eventsub_task:
            state.eventsub_task.cancel()
            try:
                await state.eventsub_task
            except asyncio.CancelledError:
                pass
        state.eventsub_running = False
        log("[WEB] EventSub stopped", True)
    return RedirectResponse(url="/", status_code=302)


# ============== Rotation API ==============

@app.get("/api/rotation/status")
async def api_rotation_status(request: Request):
    require_auth(request)
    return {
        "enabled": state.rotation_enabled,
        "interval_min": state.rotation_interval_min,
        "interval_max": state.rotation_interval_max
    }


@app.post("/api/rotation/toggle")
async def api_rotation_toggle(request: Request):
    require_auth(request)
    if state.rotation_enabled:
        await stop_rotation()
    else:
        await start_rotation()
    return RedirectResponse(url="/", status_code=302)


@app.post("/api/rotation/settings")
async def api_rotation_settings(request: Request, min_minutes: int = Form(...), max_minutes: int = Form(...)):
    require_auth(request)
    if min_minutes < 1 or max_minutes < min_minutes:
        raise HTTPException(status_code=400, detail="Invalid interval")
    state.rotation_interval_min = min_minutes
    state.rotation_interval_max = max_minutes
    log(f"[WEB] Rotation interval changed: {min_minutes}-{max_minutes} min", True)
    return RedirectResponse(url="/", status_code=302)


# ============== Logs API ==============

@app.get("/api/logs")
async def api_get_logs(request: Request, lines: int = 20):
    require_auth(request)
    logs = get_latest_logs(lines)
    return {"logs": logs}


@app.get("/api/logs/files")
async def api_get_log_files(request: Request):
    require_auth(request)
    files = get_log_files()
    return {"files": [f.name for f in files]}


# ============== Startup/Shutdown ==============

@app.on_event("startup")
async def startup_event():
    log("[WEB] Starting web server...", True)
    state.reload_statuses()

    # Start rotation by default
    await start_rotation()

    # Start EventSub by default
    try:
        from is_live import start_eventsub
        state.eventsub_task = asyncio.create_task(start_eventsub())
        state.eventsub_running = True
        log("[WEB] EventSub started automatically", True)
    except Exception as e:
        log(f"[WEB] Failed to start EventSub: {e}", True, "error")


@app.on_event("shutdown")
async def shutdown_event():
    log("[WEB] Shutting down...", True)
    await stop_rotation()

    if state.eventsub_running:
        from is_live import stop_eventsub
        await stop_eventsub()
