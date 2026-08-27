from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Date, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, date
import os

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Railway always injects DATABASE_URL via PostgreSQL plugin — if missing, refuse to start
    raise RuntimeError(
        "DATABASE_URL is not set. Railway PostgreSQL plugin must be attached. "
        "Run: railway plugin add postgresql"
    )
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    hashed_password = Column(String)

    # TDEE fields
    age = Column(Integer, nullable=True)
    height_cm = Column(Float, nullable=True)
    weight_kg = Column(Float, nullable=True)
    gender = Column(String, nullable=True)
    activity_level = Column(String, nullable=True)
    goal_type = Column(String, nullable=True)
    tdee = Column(Float, nullable=True)
    daily_calorie_goal = Column(Float, nullable=True)

    # Macro split (%) — defaults set on onboard
    protein_pct = Column(Float, default=30)
    carbs_pct = Column(Float, default=40)
    fat_pct = Column(Float, default=30)

    # Gamification
    credits = Column(Integer, default=0)
    weekly_streak = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)
    total_points = Column(Integer, default=0)

    # Approval system
    approved = Column(Boolean, default=False)
    role = Column(String, default='client')  # 'trainer' or 'client'

    days_as_king = Column(Integer, default=0)
    last_king_date = Column(Date, nullable=True)
    trainer_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Meal(Base):
    __tablename__ = "meals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    photo_path = Column(String, nullable=True)
    food_name = Column(String, nullable=True)
    ai_calories = Column(Float)
    ai_protein = Column(Float, nullable=True)
    ai_carbs = Column(Float, nullable=True)
    ai_fat = Column(Float, nullable=True)
    user_calories = Column(Float, nullable=True)
    user_protein = Column(Float, nullable=True)
    user_carbs = Column(Float, nullable=True)
    user_fat = Column(Float, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DailyLog(Base):
    __tablename__ = "daily_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(Date, default=date.today)
    total_calories = Column(Float, default=0)
    total_protein = Column(Float, default=0)
    total_carbs = Column(Float, default=0)
    total_fat = Column(Float, default=0)
    goal_calories = Column(Float, default=0)
    goal_protein = Column(Float, default=0)
    goal_carbs = Column(Float, default=0)
    goal_fat = Column(Float, default=0)
    goal_met = Column(Boolean, default=False)
    meal_count = Column(Integer, default=0)
    credits_earned = Column(Integer, default=0)
    points_calories = Column(Integer, default=0)
    points_protein = Column(Integer, default=0)
    points_carbs = Column(Integer, default=0)
    points_fat = Column(Integer, default=0)
    total_points = Column(Integer, default=0)


class ShopItem(Base):
    __tablename__ = "shop_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    item_type = Column(String)
    price = Column(Integer)
    pixel_colors = Column(String, nullable=True)
    available = Column(Boolean, default=True)


class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    item_id = Column(Integer, ForeignKey("shop_items.id"))
    equipped = Column(Boolean, default=False)
    purchased_at = Column(DateTime, default=datetime.utcnow)


class Pet(Base):
    __tablename__ = "pets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    name = Column(String, default="Pixel")
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    happiness = Column(Integer, default=50)
    hunger = Column(Integer, default=50)
    last_fed = Column(DateTime, default=datetime.utcnow)
    last_played = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


