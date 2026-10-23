"""Regression: a newly adopted spirit must start at 0 XP.

Bug: update_daily_points computed `lifetime // 10 - checkpoint // 10` with a
newborn pet's checkpoint at 0, so the first recalculation handed the new spirit
the user's ENTIRE lifetime score — egg -> adult in one meal log.
"""
import os, sys, tempfile
from datetime import date

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp(prefix='xp-test-')}/t.db"
os.environ.setdefault("OPENROUTER_API_KEY", "not-a-real-key-intentionally-invalid")
sys.path.insert(0, "/home/gary/Projects/pixel-plates")

from fastapi.testclient import TestClient
from backend.main import (app, SessionLocal, SPECIES, lifetime_points,
                          update_daily_points, UNLOCK_XP)
from backend import models

fails = []
def check(label, cond, extra=""):
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {extra}")
    if not cond: fails.append(label)

c = TestClient(app)
db = SessionLocal()

# A veteran user: 600 lifetime points = 60 XP (far past every threshold).
u = models.User(name="Vet", email="vet@t", hashed_password="x", role="client",
                approved=True, age=30, total_points=600)
db.add(u); db.commit(); db.refresh(u)
for i in range(30):
    db.add(models.DailyLog(user_id=u.id, date=date(2026, 9, i+1), total_calories=2000,
                           goal_calories=2000, goal_met=True, points_calories=20,
                           points_protein=0, points_carbs=0, points_fat=0,
                           total_points=20))
db.commit()

print(f"user lifetime points: {lifetime_points(db, u.id)}")

# Existing adult spirit, checkpointed at the lifetime total.
old = models.Pet(user_id=u.id, name="Old", species="chicken", is_active=True, xp=60,
                 level=4, happiness=100, hunger=100,
                 last_xp_checkpoint=lifetime_points(db, u.id))
db.add(old); db.commit()

print("\n1. adopt a new spirit")
r = c.post("/api/pet/adopt", data={"user_id": u.id})
check("adopt succeeded", r.status_code == 200, r.status_code)
new = db.query(models.Pet).filter(models.Pet.user_id == u.id,
                                  models.Pet.is_active == True).first()
print(f"     new spirit: {new.name}  xp={new.xp}  checkpoint={new.last_xp_checkpoint}")
check("new spirit starts at 0 XP", (new.xp or 0) == 0, new.xp)
check("checkpoint baselined to lifetime score",
      (new.last_xp_checkpoint or 0) == lifetime_points(db, u.id), new.last_xp_checkpoint)

print("\n2. a meal log must NOT jump it to adult")
daily = db.query(models.DailyLog).filter(models.DailyLog.user_id == u.id).first()
update_daily_points(daily, db)
db.refresh(new)
st = c.get(f"/api/pet/{u.id}").json()
print(f"     xp={new.xp}  stage={st.get('stage')}/{st.get('stages')}")
check("still 0 XP after recalc", (new.xp or 0) == 0, new.xp)
check("still an egg (stage 1)", st.get("stage") == 1, st.get("stage"))

print("\n3. it DOES earn from NEW points only")
db.add(models.DailyLog(user_id=u.id, date=date(2026, 10, 1), total_calories=2000,
                       goal_calories=2000, goal_met=True, points_calories=25,
                       points_protein=0, points_carbs=0, points_fat=0, total_points=25))
db.commit()
d2 = db.query(models.DailyLog).filter(models.DailyLog.date == date(2026, 10, 1)).first()
update_daily_points(d2, db)
db.refresh(new)
print(f"     xp={new.xp} (lifetime {lifetime_points(db, u.id)} -> expect ~2 XP from the +25)")
check("earns only the delta", 0 < (new.xp or 0) <= 3, new.xp)

print("\n4. self-heal: a legacy pet with xp=0 and checkpoint=0 is not credited")
legacy_u = models.User(name="Legacy", email="legacy@t", hashed_password="x", role="client",
                       approved=True, age=30, total_points=600)
db.add(legacy_u); db.commit(); db.refresh(legacy_u)
for i in range(30):
    db.add(models.DailyLog(user_id=legacy_u.id, date=date(2026, 8, i+1), total_calories=2000,
                           goal_calories=2000, goal_met=True, points_calories=20,
                           points_protein=0, points_carbs=0, points_fat=0, total_points=20))
db.commit()
db.add(models.Pet(user_id=legacy_u.id, name="Broken", species="duck", is_active=True,
                  xp=0, level=1, happiness=100, hunger=100, last_xp_checkpoint=0))
db.commit()
ld = db.query(models.DailyLog).filter(models.DailyLog.user_id == legacy_u.id).first()
update_daily_points(ld, db)
lp = db.query(models.Pet).filter(models.Pet.user_id == legacy_u.id).first()
print(f"     legacy pet xp={lp.xp} checkpoint={lp.last_xp_checkpoint}")
check("legacy pet not handed lifetime XP", (lp.xp or 0) == 0, lp.xp)

print("\n" + "=" * 60)
print(f"RESULT: {'ALL PASSED' if not fails else str(len(fails)) + ' FAILED: ' + ', '.join(fails)}")
print("=" * 60)
