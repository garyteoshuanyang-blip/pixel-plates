"""Pixel Plates - Main FastAPI Application"""
import os
import uuid
from datetime import date, datetime, timezone, timedelta
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
SGT = timezone(timedelta(hours=8))
from sqlalchemy.orm import Session
from sqlalchemy import func
import bcrypt as bcrypt_lib
from jose import jwt, JWTError
import json

import sys
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.models import SessionLocal, User, Meal, DailyLog, ShopItem, Inventory, Pet
from backend.services import tdee as tdee_service
from backend.services.vision import analyze_food_photo, analyze_food_text

# Generate cache-busting version that changes every deploy
try:
    BUILD_VERSION = subprocess.check_output(
        ["git", "-C", os.path.dirname(os.path.abspath(__file__)), "rev-parse", "--short", "HEAD"],
        stderr=subprocess.DEVNULL
    ).decode().strip()
except Exception:
    BUILD_VERSION = os.getenv("RAILWAY_DEPLOYMENT_ID", str(int(datetime.now().timestamp())))

app = FastAPI(title="Pixel Plates")


# === Auto-migration for new columns on existing PostgreSQL ===


def check_and_migrate():
    """Add missing columns to existing tables without dropping data."""
    from sqlalchemy import inspect, text as sql_text
    engine = SessionLocal().bind
    inspector = inspect(engine)
    with engine.begin() as conn:
        # Users table
        users_cols = [c['name'] for c in inspector.get_columns('users')]
        if 'approved' not in users_cols:
            conn.execute(sql_text("ALTER TABLE users ADD COLUMN approved BOOLEAN DEFAULT FALSE"))
        if 'role' not in users_cols:
            conn.execute(sql_text("ALTER TABLE users ADD COLUMN role VARCHAR DEFAULT 'client'"))
        if 'total_points' not in users_cols:
            conn.execute(sql_text("ALTER TABLE users ADD COLUMN total_points INTEGER DEFAULT 0"))
        if 'days_as_king' not in users_cols:
            conn.execute(sql_text("ALTER TABLE users ADD COLUMN days_as_king INTEGER DEFAULT 0"))
        if 'last_king_date' not in users_cols:
            conn.execute(sql_text("ALTER TABLE users ADD COLUMN last_king_date DATE"))
        # DailyLog table
        daily_cols = [c['name'] for c in inspector.get_columns('daily_logs')]
        for col in ['points_calories', 'points_protein', 'points_carbs', 'points_fat', 'total_points']:
            if col not in daily_cols:
                conn.execute(sql_text(f"ALTER TABLE daily_logs ADD COLUMN {col} INTEGER DEFAULT 0"))
    # Auto-promote designated trainer email
    trainer_email = os.getenv("TRAINER_EMAIL", "")
    if trainer_email:
        with engine.begin() as conn:
            from sqlalchemy import text as sql_text
            conn.execute(
                sql_text("UPDATE users SET approved = TRUE, role = 'trainer' WHERE email = :email AND role != 'trainer'"),
                {"email": trainer_email}
            )
            result = conn.execute(sql_text("SELECT COUNT(*) as c FROM users WHERE email = :email AND role = 'trainer'"), {"email": trainer_email})
            row = result.fetchone()
            if row and row[0] > 0:
                print(f"✅ Trainer auto-promoted: {trainer_email}")
    
    print("✅ DB migration checked — all columns present")

    # Pets table
    tables = inspector.get_table_names()
    if 'pets' not in tables:
        from sqlalchemy import text as sql_text
        conn.execute(sql_text("""
            CREATE TABLE pets (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) UNIQUE,
                name VARCHAR DEFAULT 'Pixel',
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                happiness INTEGER DEFAULT 50,
                hunger INTEGER DEFAULT 50,
                last_fed TIMESTAMP DEFAULT NOW(),
                last_played TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        print("✅ Created pets table")


@app.on_event("startup")
async def startup():
    check_and_migrate()


# === Configuration ===


SECRET_KEY = os.getenv("SECRET_KEY", "pixel-plates-dev-key-change-in-production")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "static")), name="static")


# === Cache-busting for HTML/JS/CSS ===


@app.middleware("http")
async def no_cache_middleware(request, call_next):
    response = await call_next(request)
    if request.url.path.endswith(('.js', '.html', '.css')):
        response.headers['Cache-Control'] = 'no-cache, must-revalidate'
    return response


# === DB Helpers ===
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(db: Session = Depends(get_db)):
    """Simple session-based auth via cookie/user_id header"""
    # For MVP: return first user or allow creating one
    user = db.query(User).first()
    if not user:
        raise HTTPException(401, "No user found")
    return user


# === Auth Routes ===
@app.post("/api/auth/register")
async def register(email: str = Form(...), name: str = Form(...), password: str = Form(...), trainer_code: str = Form(None), db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(400, "Email already registered")
    secret_code = os.getenv("TRAINER_CODE", "")
    is_trainer = trainer_code and secret_code and trainer_code.strip() == secret_code.strip()
    user = User(
        email=email, name=name,
        hashed_password=bcrypt_lib.hashpw(password.encode(), bcrypt_lib.gensalt()).decode(),
        approved=is_trainer,
        role='trainer' if is_trainer else 'client',
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "email": user.email, "name": user.name, "approved": user.approved, "role": user.role}


@app.post("/api/auth/login")
async def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user or not bcrypt_lib.checkpw(password.encode(), user.hashed_password.encode()):
        raise HTTPException(401, "Invalid credentials")
    # Check approval — trainers auto-approved, clients need approval
    if not user.approved and user.role != 'trainer':
        raise HTTPException(403, "Account pending approval. Your trainer needs to activate your account.")
    token = jwt.encode({"user_id": user.id, "exp": datetime.utcnow().timestamp() + 86400 * 30}, SECRET_KEY, algorithm="HS256")
    return {"token": token, "user_id": user.id, "name": user.name, "role": user.role, "approved": user.approved}


# === Admin Endpoints ===


@app.get("/api/admin/pending-users")
async def get_pending_users(db: Session = Depends(get_db)):
    """List all users pending approval (visible to trainers only)."""
    users = db.query(User).filter(User.approved == False, User.role != 'trainer').all()
    return [{
        "id": u.id, "name": u.name, "email": u.email,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    } for u in users]


@app.post("/api/admin/approve/{user_id}")
async def approve_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    user.approved = True
    db.commit()
    return {"ok": True, "name": user.name, "email": user.email}


@app.post("/api/admin/deny/{user_id}")
async def deny_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    db.delete(user)
    db.commit()
    return {"ok": True, "deleted": user_id}


# === Trainer: Client Roster ===


@app.get("/api/trainer/clients/{trainer_id}")
async def get_my_clients(trainer_id: int, db: Session = Depends(get_db)):
    """List all approved clients for a trainer."""
    user = db.query(User).filter(User.id == trainer_id).first()
    if not user or user.role != 'trainer':
        raise HTTPException(403, "Not authorized")
    clients = db.query(User).filter(
        User.role == 'client',
        User.approved == True,
    ).all()
    result = []
    for c in clients:
        pts = db.query(func.sum(DailyLog.total_points)).filter(DailyLog.user_id == c.id).scalar() or 0
        result.append({
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "total_points": int(pts),
        })
    return result


@app.get("/api/trainer/client-detail/{client_id}")
async def get_client_detail(client_id: int, days: int = 7, date_str: str = None, db: Session = Depends(get_db)):
    """Get a client's recent daily logs with meals.
    If date_str is provided, returns only that day. Otherwise returns last N days.
    """
    from datetime import timedelta, time as dtime
    today = datetime.now(SGT).date()

    if date_str:
        try:
            target = date.fromisoformat(date_str)
            start = target
            today = target
        except:
            start = today - timedelta(days=days)
    else:
        start = today - timedelta(days=days)

    # Daily summaries
    logs = db.query(DailyLog).filter(
        DailyLog.user_id == client_id,
        DailyLog.date >= start,
        DailyLog.date <= today,
    ).order_by(DailyLog.date.desc()).all()

    daily_data = []
    for log in logs:
        # Meals for that day (SG→UTC range)
        sg_start = datetime.combine(log.date, dtime.min, tzinfo=SGT)
        sg_end = sg_start + timedelta(days=1)
        utc_start = sg_start.astimezone(timezone.utc).replace(tzinfo=None)
        utc_end = sg_end.astimezone(timezone.utc).replace(tzinfo=None)
        meals = db.query(Meal).filter(
            Meal.user_id == client_id,
            Meal.created_at >= utc_start,
            Meal.created_at < utc_end,
        ).order_by(Meal.created_at.asc()).all()

        daily_data.append({
            "date": str(log.date),
            "calories": log.total_calories or 0,
            "protein": log.total_protein or 0,
            "carbs": log.total_carbs or 0,
            "fat": log.total_fat or 0,
            "goal_calories": log.goal_calories or 0,
            "goal_protein": log.goal_protein or 0,
            "goal_carbs": log.goal_carbs or 0,
            "goal_fat": log.goal_fat or 0,
            "goal_met": log.goal_met or False,
            "meal_count": log.meal_count or 0,
            "total_points": log.total_points or 0,
            "meals": [{
                "id": m.id,
                "food_name": m.food_name,
                "calories": m.user_calories or m.ai_calories or 0,
                "protein": m.user_protein or m.ai_protein or 0,
                "carbs": m.user_carbs or m.ai_carbs or 0,
                "fat": m.user_fat or m.ai_fat or 0,
                "photo_path": m.photo_path,
                "notes": m.notes,
                "time": m.created_at.replace(tzinfo=timezone.utc).astimezone(SGT).isoformat() if m.created_at else None,
            } for m in meals],
        })

    client = db.query(User).filter(User.id == client_id).first()
    return {
        "client": {
            "id": client.id,
            "name": client.name,
            "email": client.email,
            "total_points": client.total_points or 0,
        } if client else None,
        "days": daily_data,
    }


# === Leaderboard ===


@app.get("/api/leaderboard")
async def get_leaderboard(period: str = "daily", db: Session = Depends(get_db)):
    """Leaderboard of challenge points.
    period: daily, weekly, monthly, yearly
    Points: 10 for hitting calorie goal, 5 per macro (max 25/day)
    """
    from datetime import timedelta
    today = datetime.now(SGT).date()
    if period == "daily":
        since = today
    elif period == "weekly":
        since = today - timedelta(days=7)
    elif period == "monthly":
        since = today - timedelta(days=30)
    elif period == "yearly":
        since = today - timedelta(days=365)
    else:
        since = today

    # Aggregate points per user in the period
    rows = db.query(
        DailyLog.user_id,
        func.sum(DailyLog.points_calories).label("cal_points"),
        func.sum(DailyLog.points_protein).label("pro_points"),
        func.sum(DailyLog.points_carbs).label("carb_points"),
        func.sum(DailyLog.points_fat).label("fat_points"),
        func.sum(DailyLog.total_points).label("total_points"),
        func.count(DailyLog.id).label("days_logged"),
    ).filter(
        DailyLog.date >= since,
        DailyLog.date <= today,
    ).group_by(DailyLog.user_id).order_by(func.sum(DailyLog.total_points).desc().nullslast()).all()

    result = []
    for i, row in enumerate(rows):
        user = db.query(User).filter(User.id == row.user_id).first()
        if not user:
            continue
        # Track days_as_king (once per calendar day)
        if i == 0 and period == 'daily':
            today = datetime.now(SGT).date()
            if user.last_king_date != today:
                user.days_as_king = (user.days_as_king or 0) + 1
                user.last_king_date = today
                db.commit()
        result.append({
            "user_id": user.id,
            "name": user.name,
            "total_points": int(row.total_points or 0),
            "cal_points": int(row.cal_points or 0),
            "pro_points": int(row.pro_points or 0),
            "carb_points": int(row.carb_points or 0),
            "fat_points": int(row.fat_points or 0),
            "days_logged": int(row.days_logged or 0),
            "streak": user.weekly_streak or 0,
            "days_as_king": user.days_as_king or 0,
            "rank": i + 1,
        })

    return {"period": period, "leaderboard": result}


@app.get("/api/leaderboard/my-rank/{user_id}")
async def get_my_rank(user_id: int, period: str = "daily", db: Session = Depends(get_db)):
    """Get a single user's rank and points."""
    from datetime import timedelta
    today = datetime.now(SGT).date()
    if period == "daily":
        since = today
    elif period == "weekly":
        since = today - timedelta(days=7)
    elif period == "monthly":
        since = today - timedelta(days=30)
    elif period == "yearly":
        since = today - timedelta(days=365)
    else:
        since = today

    # My points
    my_row = db.query(
        func.sum(DailyLog.points_calories).label("cal_points"),
        func.sum(DailyLog.points_protein).label("pro_points"),
        func.sum(DailyLog.points_carbs).label("carb_points"),
        func.sum(DailyLog.points_fat).label("fat_points"),
        func.sum(DailyLog.total_points).label("total_points"),
        func.count(DailyLog.id).label("days_logged"),
    ).filter(
        DailyLog.user_id == user_id,
        DailyLog.date >= since,
        DailyLog.date <= today,
    ).first()

    # My rank: count distinct users with more total points
    my_total = int(my_row.total_points or 0) if my_row else 0
    # Get all user totals, count how many are above me
    all_totals = db.query(
        DailyLog.user_id,
        func.sum(DailyLog.total_points).label("total")
    ).filter(
        DailyLog.date >= since,
        DailyLog.date <= today,
    ).group_by(DailyLog.user_id).all()
    rank = 1 + sum(1 for t in all_totals if int(t.total or 0) > my_total)
    total_participants = len(all_totals)

    user = db.query(User).filter(User.id == user_id).first()
    return {
        "rank": rank,
        "total_participants": total_participants,
        "total_points": my_total,
        "cal_points": int(my_row.cal_points or 0) if my_row else 0,
        "pro_points": int(my_row.pro_points or 0) if my_row else 0,
        "carb_points": int(my_row.carb_points or 0) if my_row else 0,
        "fat_points": int(my_row.fat_points or 0) if my_row else 0,
        "days_logged": int(my_row.days_logged or 0) if my_row else 0,
        "name": user.name if user else "",
    }


# === Achievements ===


ACHIEVEMENT_DEFS = [
    {"id": "first_meal", "emoji": "🥇", "name": "First Bite", "desc": "Log your first meal"},
    {"id": "on_fire", "emoji": "🔥", "name": "On Fire", "desc": "7-day streak"},
    {"id": "consistent", "emoji": "🌟", "name": "Star Client", "desc": "30-day streak"},
    {"id": "perfect_week", "emoji": "🏅", "name": "Perfect Week", "desc": "7 straight days at 25 pts"},
    {"id": "century", "emoji": "💯", "name": "Century", "desc": "100 total challenge points"},
    {"id": "macro_master", "emoji": "🧩", "name": "Macro Master", "desc": "Hit all 4 goals on 7 or more days"},
    {"id": "foodie", "emoji": "📸", "name": "Foodie", "desc": "Log 50 meals"},
    {"id": "top_foodie", "emoji": "👑", "name": "Top Foodie", "desc": "Take #1 on the leaderboard"},
    {"id": "goal_crusher", "emoji": "🚀", "name": "Goal Crusher", "desc": "500 total challenge points"},
    {"id": "big_spender", "emoji": "💰", "name": "Big Spender", "desc": "Buy from the shop"},
]


def check_achievement(ach_id, user, db):
    """Return (unlocked, progress, total) for one achievement."""
    user_id = user.id
    if ach_id == "first_meal":
        count = db.query(func.count(Meal.id)).filter(Meal.user_id == user_id).scalar() or 0
        return count > 0, min(count, 1), 1
    elif ach_id == "on_fire":
        s = user.weekly_streak or 0
        return s >= 7, s, 7
    elif ach_id == "consistent":
        s = user.weekly_streak or 0
        return s >= 30, s, 30
    elif ach_id == "perfect_week":
        # Count days where total_points == 25 — need last 7 consecutive
        from datetime import timedelta
        today = datetime.now(SGT).date()
        logs = db.query(DailyLog).filter(
            DailyLog.user_id == user_id,
            DailyLog.date >= today - timedelta(days=30),
        ).order_by(DailyLog.date.desc()).all()
        best_run = 0
        current_run = 0
        for log in logs:
            if log.total_points and log.total_points >= 25:
                current_run += 1
                best_run = max(best_run, current_run)
            else:
                current_run = 0
        return best_run >= 7, best_run, 7
    elif ach_id == "century":
        pts = user.total_points or 0
        return pts >= 100, pts, 100
    elif ach_id == "macro_master":
        count = db.query(func.count(DailyLog.id)).filter(
            DailyLog.user_id == user_id,
            DailyLog.points_protein >= 5,
            DailyLog.points_carbs >= 5,
            DailyLog.points_fat >= 5,
        ).scalar() or 0
        return count >= 7, count, 7
    elif ach_id == "foodie":
        count = db.query(func.count(Meal.id)).filter(Meal.user_id == user_id).scalar() or 0
        return count >= 50, count, 50
    elif ach_id == "top_foodie":
        d = user.days_as_king or 0
        return d > 0, d, 1
    elif ach_id == "goal_crusher":
        pts = user.total_points or 0
        return pts >= 500, pts, 500
    elif ach_id == "big_spender":
        owned = db.query(func.count(Inventory.id)).filter(Inventory.user_id == user_id).scalar() or 0
        return owned > 0, min(owned, 1), 1
    return False, 0, 1


@app.get("/api/achievements/{user_id}")
async def get_achievements(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404)
    results = []
    for ach in ACHIEVEMENT_DEFS:
        unlocked, progress, total = check_achievement(ach["id"], user, db)
        results.append({
            **ach,
            "unlocked": unlocked,
            "progress": progress,
            "total": total,
        })
    return {"achievements": results, "unlocked_count": sum(1 for r in results if r["unlocked"]), "total_count": len(results)}


# === Pet State Computation ===


STAGE_XP_THRESHOLDS = [0, 14, 28, 42]  # stage 1, 2, 3, 4

def compute_pet_state(user, pet, db):
    """Recalculate pet level, happiness, and hunger based on user state."""
    if not pet:
        return None
    # Level from XP (1-4)
    level = 1
    for i, threshold in enumerate(STAGE_XP_THRESHOLDS):
        if pet.xp >= threshold:
            level = i + 1
        else:
            break
    pet.level = level

    # Happiness from streak (0-100)
    streak = user.weekly_streak or 0
    pet.happiness = min(100, streak * 10)

    # Hunger decay since last fed
    now = datetime.utcnow()
    if pet.last_fed:
        hours_since_fed = (now - pet.last_fed).total_seconds() / 3600
        pet.hunger = max(0, int(pet.hunger - hours_since_fed * 2.5))
    pet.last_fed = now  # Reset decay timer on each load

    # Happiness decay if streak broken
    if streak == 0:
        pet.happiness = max(0, pet.happiness - 10)

    db.commit()
    return pet


# === Pet Endpoints ===


@app.post("/api/pet/create/{user_id}")
async def create_pet(user_id: int, db: Session = Depends(get_db)):
    """Create a pet for a user (one per user). Auto-called on first load if missing."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    existing = db.query(Pet).filter(Pet.user_id == user_id).first()
    if existing:
        return await get_pet_data(user_id, db)
    pet = Pet(user_id=user_id, name="Pixel")
    db.add(pet)
    db.commit()
    db.refresh(pet)
    pet = compute_pet_state(user, pet, db)
    return {
        "id": pet.id, "name": pet.name, "xp": pet.xp,
        "level": pet.level, "stage": pet.level,
        "happiness": pet.happiness, "hunger": pet.hunger,
        "next_stage_at": STAGE_XP_THRESHOLDS[pet.level] if pet.level < 4 else None,
    }


@app.get("/api/pet/{user_id}")
async def get_pet_data(user_id: int, db: Session = Depends(get_db)):
    """Get current pet state for a user. Auto-creates if missing."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    pet = db.query(Pet).filter(Pet.user_id == user_id).first()
    if not pet:
        return await create_pet(user_id, db)
    pet = compute_pet_state(user, pet, db)
    next_xp = STAGE_XP_THRESHOLDS[pet.level] if pet.level < 4 else None
    return {
        "id": pet.id, "name": pet.name, "xp": pet.xp,
        "level": pet.level, "stage": pet.level,
        "happiness": pet.happiness, "hunger": pet.hunger,
        "next_stage_at": next_xp,
        "xp_to_next": next_xp - pet.xp if next_xp else 0,
    }


@app.post("/api/pet/rename")
async def rename_pet(user_id: int = Form(...), name: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404)
    pet = db.query(Pet).filter(Pet.user_id == user_id).first()
    if not pet:
        raise HTTPException(404, "No pet yet")
    pet.name = name[:20]  # Max 20 chars
    db.commit()
    return {"name": pet.name}


@app.post("/api/pet/feed")
async def feed_pet(user_id: int = Form(...), db: Session = Depends(get_db)):
    """Feed pet: costs 5 points, +20 hunger."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404)
    pet = db.query(Pet).filter(Pet.user_id == user_id).first()
    if not pet:
        raise HTTPException(404, "No pet yet")
    if (user.total_points or 0) < 5:
        raise HTTPException(400, "Need 5 points to feed your pet")
    user.total_points = (user.total_points or 0) - 5
    pet.hunger = min(100, pet.hunger + 20)
    pet.last_fed = datetime.utcnow()
    db.commit()
    return {"hunger": pet.hunger, "happiness": pet.happiness, "remaining_points": user.total_points}


@app.post("/api/pet/play")
async def play_with_pet(user_id: int = Form(...), db: Session = Depends(get_db)):
    """Play with pet: costs 5 points, +20 happiness."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404)
    pet = db.query(Pet).filter(Pet.user_id == user_id).first()
    if not pet:
        raise HTTPException(404, "No pet yet")
    if (user.total_points or 0) < 5:
        raise HTTPException(400, "Need 5 points to play with your pet")
    user.total_points = (user.total_points or 0) - 5
    pet.happiness = min(100, pet.happiness + 20)
    pet.last_played = datetime.utcnow()
    db.commit()
    return {"hunger": pet.hunger, "happiness": pet.happiness, "remaining_points": user.total_points}


# === Points Calculator ===


def is_cal_goal_met(goal_type, total_calories, goal_calories):
    """Check if calorie goal is met based on goal type.
    - Gain weight (gain*): points when calories >= goal (hit your target)
    - Lose/Maintain: points when calories <= goal (kept within limit)
    """
    if not goal_calories:
        return False
    if goal_type and goal_type.startswith("gain"):
        return (total_calories or 0) >= goal_calories
    return (total_calories or 0) <= goal_calories


def calculate_daily_points(daily_log):
    """Calculate challenge points for a daily log.
    - Hit daily calorie goal: 10 points
    - Each macro goal hit (protein, carbs, fat): 5 points each (max +15)
    - Total per day: up to 25 points
    """
    if not daily_log:
        return 0, 0, 0, 0, 0
    cal_p = 10 if daily_log.goal_met else 0
    pro_p = 5 if (daily_log.total_protein or 0) >= (daily_log.goal_protein or 999999) else 0
    carb_p = 5 if (daily_log.total_carbs or 0) >= (daily_log.goal_carbs or 999999) else 0
    fat_p = 5 if (daily_log.total_fat or 0) >= (daily_log.goal_fat or 999999) else 0
    total = cal_p + pro_p + carb_p + fat_p
    return total, cal_p, pro_p, carb_p, fat_p


def update_daily_points(daily, db):
    """Recalculate and persist points on a daily log."""
    user = db.query(User).filter(User.id == daily.user_id).first()
    if user:
        daily.goal_met = is_cal_goal_met(user.goal_type, daily.total_calories, daily.goal_calories)
    total, cal_p, pro_p, carb_p, fat_p = calculate_daily_points(daily)
    daily.points_calories = cal_p
    daily.points_protein = pro_p
    daily.points_carbs = carb_p
    daily.points_fat = fat_p
    daily.total_points = total
    if user:
        all_points = db.query(func.sum(DailyLog.total_points)).filter(DailyLog.user_id == user.id).scalar() or 0
        user.total_points = all_points
        # Award XP to pet: 25 points = 1 XP
        if total > 0:
            pet = db.query(Pet).filter(Pet.user_id == user.id).first()
            if pet:
                # Convert points to XP (25:1 ratio)
                xp_gain = total // 25
                if xp_gain > 0:
                    pet.xp += xp_gain
                    compute_pet_state(user, pet, db)
    db.commit()


# === TDEE / Onboarding ===
@app.post("/api/onboard")
async def onboard(
    user_id: int = Form(...),
    age: int = Form(...),
    height_cm: float = Form(...),
    weight_kg: float = Form(...),
    gender: str = Form(...),
    activity_level: str = Form(...),
    goal_type: str = Form(...),
    custom_adj: int = Form(0),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    tdee = tdee_service.calculate_tdee(weight_kg, height_cm, age, gender, activity_level)
    daily_goal = tdee_service.calculate_goal(tdee, goal_type, custom_adj)
    macros = tdee_service.get_default_macros(goal_type, daily_goal)

    user.age = age
    user.height_cm = height_cm
    user.weight_kg = weight_kg
    user.gender = gender
    user.activity_level = activity_level
    user.goal_type = goal_type
    user.tdee = tdee
    user.daily_calorie_goal = daily_goal
    user.protein_pct = macros["protein_pct"]
    user.carbs_pct = macros["carbs_pct"]
    user.fat_pct = macros["fat_pct"]

    db.commit()
    return {
        "tdee": tdee,
        "daily_calorie_goal": daily_goal,
        "goal_type": goal_type,
        "goal_label": tdee_service.GOAL_LABELS.get(goal_type, ""),
        "macros": {
            "protein_g": macros["protein_g"],
            "carbs_g": macros["carbs_g"],
            "fat_g": macros["fat_g"],
            "protein_pct": macros["protein_pct"],
            "carbs_pct": macros["carbs_pct"],
            "fat_pct": macros["fat_pct"],
        },
    }


@app.get("/api/user/{user_id}")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404)
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "age": user.age,
        "height_cm": user.height_cm,
        "weight_kg": user.weight_kg,
        "gender": user.gender,
        "activity_level": user.activity_level,
        "goal_type": user.goal_type,
        "tdee": user.tdee,
        "daily_calorie_goal": user.daily_calorie_goal,
        "custom_adj": 0,
        "credits": user.credits,
        "weekly_streak": user.weekly_streak,
        "longest_streak": user.longest_streak,
        "onboarded": user.age is not None,
        "goal_label": tdee_service.GOAL_LABELS.get(user.goal_type, "") if user.goal_type else "",
        "activity_label": tdee_service.ACTIVITY_LABELS.get(user.activity_level, "") if user.activity_level else "",
        "protein_pct": user.protein_pct,
        "carbs_pct": user.carbs_pct,
        "fat_pct": user.fat_pct,
        "role": user.role,
        "approved": user.approved,
        "total_points": user.total_points or 0,
        "days_as_king": user.days_as_king or 0,
        "macro_goals": tdee_service.calculate_macros(
            user.daily_calorie_goal or 2000,
            user.protein_pct or 30,
            user.carbs_pct or 40,
            user.fat_pct or 30,
        ) if user.daily_calorie_goal else None,
    }
    
    

@app.post("/api/user/rename")
async def rename_user(user_id: int = Form(...), name: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if not name or not name.strip():
        raise HTTPException(400, "Name cannot be empty")
    user.name = name.strip()[:30]
    db.commit()
    return {"name": user.name}


@app.post("/api/macros")
async def update_macros(
    user_id: int = Form(...),
    protein_pct: float = Form(...),
    carbs_pct: float = Form(...),
    fat_pct: float = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404)
    total = protein_pct + carbs_pct + fat_pct
    if abs(total - 100) > 1:
        raise HTTPException(400, f"Macro percentages must add up to 100 (got {total})")

    user.protein_pct = protein_pct
    user.carbs_pct = carbs_pct
    user.fat_pct = fat_pct

    # Update today's daily log goals
    today = datetime.now(SGT).date()
    daily = db.query(DailyLog).filter(DailyLog.user_id == user_id, DailyLog.date == today).first()
    if daily:
        macros = tdee_service.calculate_macros(user.daily_calorie_goal or 2000, protein_pct, carbs_pct, fat_pct)
        daily.goal_protein = macros["protein_g"]
        daily.goal_carbs = macros["carbs_g"]
        daily.goal_fat = macros["fat_g"]

    db.commit()

    macros = tdee_service.calculate_macros(user.daily_calorie_goal or 2000, protein_pct, carbs_pct, fat_pct)
    return {"protein_pct": protein_pct, "carbs_pct": carbs_pct, "fat_pct": fat_pct, **macros}


# === Meals ===
@app.post("/api/meals")
async def create_meal(
    user_id: int = Form(...),
    photo: UploadFile = File(None),
    food_name: str = Form(None),
    calories: float = Form(None),
    notes: str = Form(None),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404)

    photo_path = None
    ai_calories = 0
    result = {}

    if photo and photo.filename:
        ext = os.path.splitext(photo.filename)[1] or ".jpg"
        filename = f"{uuid.uuid4()}{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        content = await photo.read()
        with open(filepath, "wb") as f:
            f.write(content)
        photo_path = f"/static/uploads/{filename}"

        # AI analysis
        result = await analyze_food_photo(filepath)
        ai_calories = result.get("total_calories", 0)

    elif food_name:
        # Text fallback
        result = await analyze_food_text(food_name)
        ai_calories = result.get("total_calories", 0)

    if not photo and not food_name:
        raise HTTPException(400, "Either a photo or food name is required")

    # Use AI estimate or user-provided value
    final_calories = calories if calories is not None else ai_calories

    meal = Meal(
        user_id=user_id,
        photo_path=photo_path,
        food_name=food_name or (result.get("foods", [{}])[0].get("name", "Unknown") if photo_path else food_name),
        ai_calories=ai_calories,
        ai_protein=result.get("protein_g", 0),
        ai_carbs=result.get("carbs_g", 0),
        ai_fat=result.get("fat_g", 0),
        user_calories=calories,
        notes=notes,
    )
    db.add(meal)

    # Update daily log
    today = datetime.now(SGT).date()
    daily = db.query(DailyLog).filter(DailyLog.user_id == user_id, DailyLog.date == today).first()
    if not daily:
        goal_macros = tdee_service.calculate_macros(
            user.daily_calorie_goal or 2000,
            user.protein_pct or 30,
            user.carbs_pct or 40,
            user.fat_pct or 30,
        )
        daily = DailyLog(
            user_id=user_id, date=today,
            goal_calories=user.daily_calorie_goal or 2000,
            goal_protein=goal_macros["protein_g"],
            goal_carbs=goal_macros["carbs_g"],
            goal_fat=goal_macros["fat_g"],
        )
        db.add(daily)

    daily.total_calories = (daily.total_calories or 0) + final_calories
    daily.total_protein = (daily.total_protein or 0) + result.get("protein_g", 0)
    daily.total_carbs = (daily.total_carbs or 0) + result.get("carbs_g", 0)
    daily.total_fat = (daily.total_fat or 0) + result.get("fat_g", 0)
    daily.meal_count = (daily.meal_count or 0) + 1
    daily.goal_met = is_cal_goal_met(user.goal_type, daily.total_calories, daily.goal_calories)

    # Recalculate challenge points
    update_daily_points(daily, db)

    db.commit()
    db.refresh(meal)

    # Delete photo after AI analysis (no storage retention)
    if photo_path and os.path.exists(filepath):
        try:
            os.remove(filepath)
        except:
            pass

    return {
        "meal_id": meal.id,
        "food_name": meal.food_name,
        "calories": final_calories,
        "protein": result.get("protein_g", 0),
        "carbs": result.get("carbs_g", 0),
        "fat": result.get("fat_g", 0),
        "ai_calories": ai_calories,
        "daily_total": daily.total_calories,
        "daily_protein": daily.total_protein,
        "daily_carbs": daily.total_carbs,
        "daily_fat": daily.total_fat,
        "goal": daily.goal_calories,
        "goal_protein": daily.goal_protein,
        "goal_carbs": daily.goal_carbs,
        "goal_fat": daily.goal_fat,
        "goal_met": daily.goal_met,
        "meal_count": daily.meal_count,
    }


@app.get("/api/meals/{user_id}")
async def get_meals(user_id: int, date_str: str = None, db: Session = Depends(get_db)):
    query = db.query(Meal).filter(Meal.user_id == user_id)
    # Default to today SG time — convert to UTC range for correct comparison
    from datetime import timedelta, time as dtime
    meal_today = datetime.now(SGT).date()
    target_date = date.fromisoformat(date_str) if date_str else meal_today
    try:
        # SG midnight → UTC conversion
        sg_start = datetime.combine(target_date, dtime.min, tzinfo=SGT)
        sg_end = sg_start + timedelta(days=1)
        utc_start = sg_start.astimezone(timezone.utc).replace(tzinfo=None)
        utc_end = sg_end.astimezone(timezone.utc).replace(tzinfo=None)
        query = query.filter(Meal.created_at >= utc_start, Meal.created_at < utc_end)
    except:
        pass
    meals = query.order_by(Meal.created_at.desc()).limit(50).all()
    return [{
        "id": m.id,
        "food_name": m.food_name,
        "calories": m.user_calories or m.ai_calories,
        "protein": m.user_protein or m.ai_protein or 0,
        "carbs": m.user_carbs or m.ai_carbs or 0,
        "fat": m.user_fat or m.ai_fat or 0,
        "photo_path": m.photo_path,
        "notes": m.notes,
        "time": m.created_at.replace(tzinfo=timezone.utc).astimezone(SGT).isoformat() if m.created_at else None,
    } for m in meals]


@app.delete("/api/meals/{meal_id}")
async def delete_meal(meal_id: int, db: Session = Depends(get_db)):
    meal = db.query(Meal).filter(Meal.id == meal_id).first()
    if not meal:
        raise HTTPException(404)
    user_id = meal.user_id
    db.delete(meal)
    db.commit()
    # Recalc daily points after deletion
    today = datetime.now(SGT).date()
    daily = db.query(DailyLog).filter(DailyLog.user_id == user_id, DailyLog.date == today).first()
    if daily:
        # Recalculate totals from remaining meals (SG→UTC range)
        from datetime import timedelta as td, time as dtime
        sg_start = datetime.combine(today, dtime.min, tzinfo=SGT)
        sg_end = sg_start + td(days=1)
        utc_start = sg_start.astimezone(timezone.utc).replace(tzinfo=None)
        utc_end = sg_end.astimezone(timezone.utc).replace(tzinfo=None)
        meals = db.query(Meal).filter(Meal.user_id == user_id, Meal.created_at >= utc_start, Meal.created_at < utc_end).all()
        daily.total_calories = sum(m.user_calories or m.ai_calories or 0 for m in meals)
        daily.total_protein = sum(m.user_protein or m.ai_protein or 0 for m in meals)
        daily.total_carbs = sum(m.user_carbs or m.ai_carbs or 0 for m in meals)
        daily.total_fat = sum(m.user_fat or m.ai_fat or 0 for m in meals)
        daily.meal_count = len(meals)
        update_daily_points(daily, db)
        db.commit()
    return {"ok": True}


# === Edit Meal ===


@app.put("/api/meals/{meal_id}")
async def edit_meal(
    meal_id: int,
    calories: float = Form(None),
    protein: float = Form(None),
    carbs: float = Form(None),
    fat: float = Form(None),
    food_name: str = Form(None),
    db: Session = Depends(get_db),
):
    meal = db.query(Meal).filter(Meal.id == meal_id).first()
    if not meal:
        raise HTTPException(404, "Meal not found")

    if food_name is not None:
        meal.food_name = food_name
    if calories is not None:
        meal.user_calories = calories
        meal.user_protein = protein
        meal.user_carbs = carbs
        meal.user_fat = fat

    db.commit()

    # Recalc the daily log + points for the day this meal belongs to
    user_id = meal.user_id
    from datetime import timedelta as td, time as dtime
    meal_utc = meal.created_at
    today_sg = meal_utc.replace(tzinfo=timezone.utc).astimezone(SGT).date()
    daily = db.query(DailyLog).filter(DailyLog.user_id == user_id, DailyLog.date == today_sg).first()
    if daily:
        sg_start = datetime.combine(today_sg, dtime.min, tzinfo=SGT)
        sg_end = sg_start + td(days=1)
        utc_start = sg_start.astimezone(timezone.utc).replace(tzinfo=None)
        utc_end = sg_end.astimezone(timezone.utc).replace(tzinfo=None)
        meals = db.query(Meal).filter(Meal.user_id == user_id, Meal.created_at >= utc_start, Meal.created_at < utc_end).all()
        daily.total_calories = sum(m.user_calories or m.ai_calories or 0 for m in meals)
        daily.total_protein = sum(m.user_protein or m.ai_protein or 0 for m in meals)
        daily.total_carbs = sum(m.user_carbs or m.ai_carbs or 0 for m in meals)
        daily.total_fat = sum(m.user_fat or m.ai_fat or 0 for m in meals)
        daily.meal_count = len(meals)
        update_daily_points(daily, db)
        db.commit()

    return {
        "ok": True,
        "meal_id": meal.id,
        "food_name": meal.food_name,
        "calories": meal.user_calories or meal.ai_calories or 0,
        "protein": meal.user_protein or meal.ai_protein or 0,
        "carbs": meal.user_carbs or meal.ai_carbs or 0,
        "fat": meal.user_fat or meal.ai_fat or 0,
    }


# === Dashboard ===
@app.get("/api/dashboard/{user_id}")
async def get_dashboard(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404)

    today = datetime.now(SGT).date()
    daily = db.query(DailyLog).filter(DailyLog.user_id == user_id, DailyLog.date == today).first()

    # Last 7 days
    week_logs = db.query(DailyLog).filter(
        DailyLog.user_id == user_id,
        DailyLog.date >= today.isoformat()
    ).order_by(DailyLog.date.desc()).limit(7).all()

    # Calculate streak
    streak = 0
    check_date = today
    while True:
        log = db.query(DailyLog).filter(DailyLog.user_id == user_id, DailyLog.date == check_date).first()
        if log and log.goal_met:
            streak += 1
            check_date = check_date.isoformat()
            # decrement date
            from datetime import timedelta
            check_date = date.fromisoformat(check_date) - timedelta(days=1)
        else:
            break

    # Update streak
    user.weekly_streak = streak
    if streak > (user.longest_streak or 0):
        user.longest_streak = streak
    db.commit()

    # Sync today's daily log goals from user settings if stale
    if daily:
        current_cal = user.daily_calorie_goal or 2000
        if daily.goal_calories != current_cal:
            daily.goal_calories = current_cal
            macros = tdee_service.calculate_macros(current_cal, user.protein_pct or 30, user.carbs_pct or 40, user.fat_pct or 30)
            daily.goal_protein = macros["protein_g"]
            daily.goal_carbs = macros["carbs_g"]
            daily.goal_fat = macros["fat_g"]
            daily.goal_met = is_cal_goal_met(user.goal_type, daily.total_calories, current_cal)
            update_daily_points(daily, db)
            db.commit()

    # Calculate macro goals regardless of daily log
    default_goals = tdee_service.calculate_macros(
        user.daily_calorie_goal or 2000,
        user.protein_pct or 30,
        user.carbs_pct or 40,
        user.fat_pct or 30,
    )

    return {
        "name": user.name,
        "today": {
            "total_calories": daily.total_calories if daily else 0,
            "total_protein": daily.total_protein if daily else 0,
            "total_carbs": daily.total_carbs if daily else 0,
            "total_fat": daily.total_fat if daily else 0,
            "goal": user.daily_calorie_goal or 2000,
            "goal_protein": default_goals["protein_g"],
            "goal_carbs": default_goals["carbs_g"],
            "goal_fat": default_goals["fat_g"],
            "goal_met": daily.goal_met if daily else False,
            "meal_count": daily.meal_count if daily else 0,
        },
        "macros": tdee_service.calculate_macros(
            user.daily_calorie_goal or 2000,
            user.protein_pct or 30,
            user.carbs_pct or 40,
            user.fat_pct or 30,
        ),
        "protein_pct": user.protein_pct,
        "carbs_pct": user.carbs_pct,
        "fat_pct": user.fat_pct,
        "streak": streak,
        "longest_streak": user.longest_streak or 0,
        "credits": user.credits or 0,
        "total_points": user.total_points or 0,
        "today_points": (daily.total_points or 0) if daily else 0,
        "onboarded": user.age is not None,
        "weekly_history": [{
            "date": str(log.date),
            "total": log.total_calories,
            "goal": log.goal_calories,
            "goal_met": log.goal_met,
        } for log in week_logs],
    }


# === History ===
@app.get("/api/history/{user_id}")
async def get_history(user_id: int, range: str = "week", db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404)
    from datetime import timedelta
    today = datetime.now(SGT).date()
    if range == "week":
        start = today - timedelta(days=7)
        label_format = "%a"
    elif range == "month":
        start = today - timedelta(days=30)
        label_format = "%d %b"
    elif range == "year":
        start = today - timedelta(days=365)
        label_format = "%b"
    else:
        start = today - timedelta(days=7)
        label_format = "%a"
    logs = db.query(DailyLog).filter(
        DailyLog.user_id == user_id,
        DailyLog.date >= start,
        DailyLog.date <= today,
    ).order_by(DailyLog.date.asc()).all()
    return [{
        "date": str(log.date),
        "label": log.date.strftime(label_format) if log.date else "",
        "calories": log.total_calories or 0,
        "protein": log.total_protein or 0,
        "carbs": log.total_carbs or 0,
        "fat": log.total_fat or 0,
        "goal": log.goal_calories or 0,
        "goal_met": log.goal_met or False,
    } for log in logs]


# === Shop ===
@app.get("/api/shop")
async def get_shop(db: Session = Depends(get_db)):
    items = db.query(ShopItem).filter(ShopItem.available == True).all()
    # Seed if empty
    if not items:
        seed_items = [
            ShopItem(name="Wizard Hat", item_type="hat", price=5),
            ShopItem(name="Baseball Cap", item_type="hat", price=4),
            ShopItem(name="T-Shirt", item_type="shirt", price=8),
            ShopItem(name="Pink Shirt", item_type="shirt", price=6),
            ShopItem(name="Sunglasses", item_type="glasses", price=3),
            ShopItem(name="Bow Tie", item_type="accessory", price=3),
            ShopItem(name="Crown", item_type="hat", price=15),
        ]
        for item in seed_items:
            db.add(item)
        db.commit()
        items = seed_items

    return [{"id": i.id, "name": i.name, "type": i.item_type, "price": i.price} for i in items]


@app.post("/api/shop/purchase")
async def purchase_item(user_id: int = Form(...), item_id: int = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    item = db.query(ShopItem).filter(ShopItem.id == item_id).first()
    if not user or not item:
        raise HTTPException(404)
    if (user.credits or 0) < item.price:
        raise HTTPException(400, "Not enough credits")

    # Check if already owned
    owned = db.query(Inventory).filter(Inventory.user_id == user_id, Inventory.item_id == item_id).first()
    if owned:
        raise HTTPException(400, "Already owned")

    user.credits = (user.credits or 0) - item.price
    inv = Inventory(user_id=user_id, item_id=item_id)
    db.add(inv)
    db.commit()
    return {"credits": user.credits, "item": item.name}


@app.get("/api/inventory/{user_id}")
async def get_inventory(user_id: int, db: Session = Depends(get_db)):
    items = db.query(Inventory, ShopItem).join(ShopItem).filter(Inventory.user_id == user_id).all()
    return [{
        "id": inv.id,
        "item_id": shop.id,
        "name": shop.name,
        "type": shop.item_type,
        "equipped": inv.equipped,
    } for inv, shop in items]


@app.post("/api/inventory/equip")
async def equip_item(inventory_id: int = Form(...), equipped: bool = Form(...), db: Session = Depends(get_db)):
    inv = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if not inv:
        raise HTTPException(404)
    inv.equipped = equipped
    db.commit()
    return {"ok": True}


# === Streak Credit Bonus ===
@app.post("/api/check-streak")
async def check_streak(user_id: int = Form(...), db: Session = Depends(get_db)):
    """Award credits based on streak milestones."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404)

    streak = user.weekly_streak or 0
    bonus = 0
    message = ""

    if streak >= 90 and streak % 90 == 0:
        bonus = 200
        message = "🎉 90-day streak! +200 credits!"
    elif streak >= 30 and streak % 30 == 0:
        bonus = 50
        message = "🌟 30-day streak! +50 credits!"
    elif streak >= 7 and streak % 7 == 0:
        bonus = 10
        message = "⭐ Weekly streak! +10 credits!"

    if bonus:
        user.credits = (user.credits or 0) + bonus
        db.commit()
        return {"bonus": bonus, "credits": user.credits, "message": message, "streak": streak}
    return {"bonus": 0, "credits": user.credits, "message": "", "streak": streak}


# === Trainer Summary Dashboard ===


@app.get("/api/trainer/summary/{trainer_id}")
async def get_trainer_summary(trainer_id: int, db: Session = Depends(get_db)):
    """Weekly summary for all clients: streak, hit rate, points."""
    from datetime import timedelta
    today = datetime.now(SGT).date()
    week_start = today - timedelta(days=7)

    clients = db.query(User).filter(User.role == 'client', User.approved == True).all()
    result = []
    for c in clients:
        logs = db.query(DailyLog).filter(
            DailyLog.user_id == c.id,
            DailyLog.date >= week_start,
            DailyLog.date <= today,
        ).order_by(DailyLog.date.asc()).all()

        days_logged = sum(1 for l in logs if (l.total_calories or 0) > 0)
        days_met = sum(1 for l in logs if l.goal_met)
        total_points = sum(l.total_points or 0 for l in logs)

        # Streak (current)
        streak = 0
        check = today
        while True:
            l = db.query(DailyLog).filter(DailyLog.user_id == c.id, DailyLog.date == check).first()
            if l and l.goal_met:
                streak += 1
                check -= timedelta(days=1)
            else:
                break

        result.append({
            "user_id": c.id,
            "name": c.name,
            "streak": streak,
            "days_logged": days_logged,
            "days_met": days_met,
            "total_days": 7,
            "hit_rate": round(days_met / 7 * 100) if days_logged > 0 else 0,
            "total_points": total_points,
        })

    return {"clients": result, "week_start": str(week_start), "week_end": str(today)}


# === Serve Frontend ===
@app.get("/", response_class=HTMLResponse)
async def index():
    resp = open(os.path.join(os.path.dirname(__file__), "..", "static", "index.html"), "r").read()
    # Inject cache-busting version for JS/CSS
    version = BUILD_VERSION
    resp = resp.replace('static/js/app.js">', f'static/js/app.js?v={version}">')
    resp = resp.replace('static/css/style.css">', f'static/css/style.css?v={version}">')
    return HTMLResponse(resp, headers={"Cache-Control": "no-cache, must-revalidate"})


@app.get("/app", response_class=HTMLResponse)
async def app_page():
    with open(os.path.join(os.path.dirname(__file__), "..", "static", "app.html"), "r") as f:
        return f.read()


# Run with: uvicorn backend.main:app --reload
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)