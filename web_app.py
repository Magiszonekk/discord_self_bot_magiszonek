import os
import random
import asyncio
from datetime import datetime
from typing import Optional
from time import time
from collections import defaultdict
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware

import json
from db_utils import (
    get_all_statuses, add_status_request, remove_status, approve_status_by_id,
    revoke_status_approval_by_id, get_approved_statuses, get_all_categories,
    add_category, remove_category, get_statuses_by_category, does_status_exist,
    verify_user, init_default_users, save_fake_dm, get_fake_dms
)
from discord_actions import get_discord_actions
from logging_utils import log, get_logs_closest_to, get_latest_logs, get_log_files
from token_manager import get_token_manager

app = FastAPI(title="Discord Bot Control Panel")

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3004",
        "http://selfbot.cikowice.pl",
        "https://selfbot.cikowice.pl",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session middleware for auth
import secrets
_session_secret = os.getenv("SESSION_SECRET", secrets.token_hex(32))
app.add_middleware(
    SessionMiddleware,
    secret_key=_session_secret,
    max_age=86400  # 24 hours
)

# Static files (optional, for legacy support)
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
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


# ============== Brute Force Protection ==============

_login_attempts = defaultdict(lambda: {"count": 0, "blocked_until": 0})
MAX_LOGIN_ATTEMPTS = 5
BLOCK_DURATION = 900  # 15 minutes


def check_brute_force(ip: str) -> bool:
    """Returns True if IP is blocked."""
    data = _login_attempts[ip]
    if data["blocked_until"] > time():
        return True
    return False


def record_failed_login(ip: str):
    """Record a failed login attempt."""
    data = _login_attempts[ip]
    data["count"] += 1
    if data["count"] >= MAX_LOGIN_ATTEMPTS:
        data["blocked_until"] = time() + BLOCK_DURATION
        data["count"] = 0
        log(f"[AUTH] IP {ip} blocked for {BLOCK_DURATION}s (brute force)", True, "warning")


def reset_login_attempts(ip: str):
    """Reset login attempts after successful login."""
    _login_attempts[ip] = {"count": 0, "blocked_until": 0}


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

@app.post("/api/login")
async def login(request: Request):
    ip = request.client.host

    # Check brute force protection
    if check_brute_force(ip):
        log(f"[AUTH] Blocked login attempt from {ip} (brute force)", True, "warning")
        return JSONResponse(
            {"success": False, "error": "Too many attempts. Try again later."},
            status_code=429
        )

    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        body = await request.json()
        username = body.get("username", "")
        password = body.get("password", "")
    else:
        form = await request.form()
        username = form.get("username", "")
        password = form.get("password", "")

    user = verify_user(username, password)
    if user:
        reset_login_attempts(ip)
        request.session["authenticated"] = True
        request.session["user_id"] = user["id"]
        request.session["username"] = user["username"]
        request.session["permissions"] = json.loads(user["permissions"])
        log(f"[AUTH] Login successful: {username} from {ip}", True)

        return JSONResponse({"success": True, "message": "Logged in successfully"})
    else:
        record_failed_login(ip)
        log(f"[AUTH] Login failed: {username} from {ip}", True, "warning")
        return JSONResponse({"success": False, "error": "Invalid credentials"}, status_code=401)


@app.get("/api/logout")
async def logout(request: Request):
    request.session.clear()
    # Check if JSON response requested
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return JSONResponse({"success": True, "message": "Logged out"})
    return JSONResponse({"success": True, "message": "Logged out"})


@app.get("/api/auth/status")
async def auth_status(request: Request):
    """Check if user is authenticated - for React frontend."""
    if is_authenticated(request):
        return JSONResponse({
            "authenticated": True,
            "username": request.session.get("username"),
            "permissions": request.session.get("permissions", [])
        })
    return JSONResponse({"authenticated": False})


# ============== Dashboard ==============

@app.get("/")
async def dashboard():
    """Redirect to React frontend or show API info."""
    return JSONResponse({
        "message": "Discord Bot Panel API",
        "docs": "/docs"
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
    return JSONResponse({"success": True, "message": "Status added"})


@app.post("/api/statuses/{status_id}/delete")
async def api_delete_status(request: Request, status_id: int):
    require_auth(request)
    remove_status(status_id)
    log(f"[WEB] Status deleted: id={status_id}", True)
    return JSONResponse({"success": True, "message": "Status deleted"})


@app.post("/api/statuses/{status_id}/approve")
async def api_approve_status(request: Request, status_id: int):
    require_auth(request)
    approve_status_by_id(status_id, 1)  # 1 = web panel (0 is falsy in JS)
    log(f"[WEB] Status approved: id={status_id}", True)
    return JSONResponse({"success": True, "message": "Status approved"})


@app.post("/api/statuses/{status_id}/revoke")
async def api_revoke_status(request: Request, status_id: int):
    require_auth(request)
    revoke_status_approval_by_id(status_id)
    log(f"[WEB] Status approval revoked: id={status_id}", True)
    return JSONResponse({"success": True, "message": "Status approval revoked"})


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
    return JSONResponse({"success": True, "message": "Category added"})


@app.post("/api/categories/{name}/delete")
async def api_delete_category(request: Request, name: str):
    require_auth(request)
    remove_category(name)
    log(f"[WEB] Category deleted: {name}", True)
    return JSONResponse({"success": True, "message": "Category deleted"})


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
        return JSONResponse({"success": True, "status": status})
    else:
        raise HTTPException(status_code=500, detail="Failed to change status")


@app.post("/api/discord/send-dm")
async def api_send_dm(request: Request, user_id: int = Form(...), message: str = Form(...)):
    require_auth(request)

    perms = request.session.get("permissions", [])
    can_send_dm = "all" in perms and "-send_dm" not in perms

    if can_send_dm:
        # Real DM send
        discord_actions = get_discord_actions()
        success, username = await discord_actions.send_dm(user_id, message)

        if success:
            log(f"[WEB] DM sent to {user_id} ({username}) by {request.session.get('username')}", True)
            return JSONResponse({"success": True, "message": "DM sent", "username": username})
        else:
            raise HTTPException(status_code=500, detail="Failed to send DM")
    else:
        # HONEYPOT - fake send, save to database
        sender_id = request.session.get("user_id")
        sender_username = request.session.get("username")
        save_fake_dm(sender_id, sender_username, str(user_id), message)
        log(f"[HONEYPOT] User '{sender_username}' tried to DM {user_id}: {message}", True, "warning")

        # Fake delay to make it look realistic
        await asyncio.sleep(random.uniform(1.5, 3.0))
        return JSONResponse({"success": True, "message": "DM sent", "username": "User"})


@app.get("/api/discord/dm-recipients")
async def api_get_dm_recipients(request: Request):
    require_auth(request)
    discord_actions = get_discord_actions()
    recipients = await discord_actions.get_dm_channels(limit=20)
    return recipients


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
    return JSONResponse({"success": True, "running": state.eventsub_running})


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
    return JSONResponse({"success": True, "running": state.eventsub_running})


# ============== Rotation API ==============

@app.get("/api/rotation/status")
async def api_rotation_status(request: Request):
    require_auth(request)
    state.reload_statuses()
    return {
        "enabled": state.rotation_enabled,
        "interval_min": state.rotation_interval_min,
        "interval_max": state.rotation_interval_max,
        "approved_count": len(state.statuses)
    }


@app.post("/api/rotation/toggle")
async def api_rotation_toggle(request: Request):
    require_auth(request)
    if state.rotation_enabled:
        await stop_rotation()
    else:
        await start_rotation()
    return JSONResponse({"success": True, "enabled": state.rotation_enabled})


@app.post("/api/rotation/settings")
async def api_rotation_settings(request: Request, min_minutes: int = Form(...), max_minutes: int = Form(...)):
    require_auth(request)
    if min_minutes < 1 or max_minutes < min_minutes:
        raise HTTPException(status_code=400, detail="Invalid interval")
    state.rotation_interval_min = min_minutes
    state.rotation_interval_max = max_minutes
    log(f"[WEB] Rotation interval changed: {min_minutes}-{max_minutes} min", True)
    return JSONResponse({"success": True, "interval_min": min_minutes, "interval_max": max_minutes})


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


# ============== Daily Backup ==============

async def daily_backup_loop():
    """Background task for daily database backup."""
    while True:
        await asyncio.sleep(86400)  # 24 hours
        try:
            from backup_utils import run_backup
            run_backup()
        except Exception as e:
            log(f"[BACKUP] Error: {e}", True, "error")


# ============== Startup/Shutdown ==============

@app.on_event("startup")
async def startup_event():
    log("[WEB] Starting web server...", True)
    state.reload_statuses()

    # Run backup at startup
    try:
        from backup_utils import run_backup
        run_backup()
    except Exception as e:
        log(f"[BACKUP] Startup backup failed: {e}", True, "error")

    # Start daily backup task
    asyncio.create_task(daily_backup_loop())

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
