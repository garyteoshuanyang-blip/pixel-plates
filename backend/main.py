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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.models import SessionLocal, User, Meal, DailyLog, ShopItem, Inventory
from backend.services import tdee as tdee_service
from backend.services.vision import analyze_food_photo, analyze_food_text

app = FastAPI(title="Pixel Plates")

SECRET_KEY = os.getenv("SECRET_KEY", "pixel-plates-dev-key-change-in-production")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "static")), name="static")


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
    for row in rows:
        user = db.query(User).filter(User.id == row.user_id).first()
        if not user:
            continue
        result.append({
            "user_id": user.id,
            "name": user.name,
            "total_points": int(row.total_points or 0),
            "cal_points": int(row.cal_points or 0),
            "pro_points": int(row.pro_points or 0),
            "carb_points": int(row.carb_points or 0),
            "fat_points": int(row.fat_points or 0),
            "days_logged": int(row.days_logged or 0),
        })

    # Add rank
    for i, r in enumerate(result):
        r["rank"] = i + 1

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


# === Points Calculator ===


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
    total, cal_p, pro_p, carb_p, fat_p = calculate_daily_points(daily)
    daily.points_calories = cal_p
    daily.points_protein = pro_p
    daily.points_carbs = carb_p
    daily.points_fat = fat_p
    daily.total_points = total
    user = db.query(User).filter(User.id == daily.user_id).first()
    if user:
        all_points = db.query(func.sum(DailyLog.total_points)).filter(DailyLog.user_id == user.id).scalar() or 0
        user.total_points = all_points
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
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    tdee = tdee_service.calculate_tdee(weight_kg, height_cm, age, gender, activity_level)
    daily_goal = tdee_service.calculate_goal(tdee, goal_type)
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
        "macro_goals": tdee_service.calculate_macros(
            user.daily_calorie_goal or 2000,
            user.protein_pct or 30,
            user.carbs_pct or 40,
            user.fat_pct or 30,
        ) if user.daily_calorie_goal else None,
    }


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
    daily.goal_met = daily.total_calories <= daily.goal_calories

    # Recalculate challenge points
    update_daily_points(daily, db)

    db.commit()
    db.refresh(meal)

    # Delete photo after AI processing (save space, no retention needed)
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
        daily.goal_met = daily.total_calories <= daily.goal_calories if daily.goal_calories else False
        update_daily_points(daily, db)
        db.commit()
    return {"ok": True}


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
            "goal": daily.goal_calories if daily else (user.daily_calorie_goal or 2000),
            "goal_protein": daily.goal_protein if daily else default_goals["protein_g"],
            "goal_carbs": daily.goal_carbs if daily else default_goals["carbs_g"],
            "goal_fat": daily.goal_fat if daily else default_goals["fat_g"],
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


# === Serve Frontend ===
@app.get("/", response_class=HTMLResponse)
async def index():
    with open(os.path.join(os.path.dirname(__file__), "..", "static", "index.html"), "r") as f:
        return f.read()


@app.get("/app", response_class=HTMLResponse)
async def app_page():
    with open(os.path.join(os.path.dirname(__file__), "..", "static", "app.html"), "r") as f:
        return f.read()


# Run with: uvicorn backend.main:app --reload
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)