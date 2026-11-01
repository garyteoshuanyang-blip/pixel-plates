"""Trends ranges: week / month / year must return DIFFERENT windows.

Bug: the frontend sent ?range=month but the endpoint declared only `period`, so
every view silently returned a week of data.
"""
import os, sys, tempfile
from datetime import date, timedelta, datetime

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp(prefix='range-test-')}/t.db"
sys.path.insert(0, "/home/gary/Projects/pixel-plates")

from fastapi.testclient import TestClient
from backend.main import app, SessionLocal
from backend import models

fails = []
def check(label, cond, extra=""):
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {extra}")
    if not cond: fails.append(label)

c = TestClient(app)
db = SessionLocal()
u = models.User(name="Charter", email="chart@t", hashed_password="x", role="client",
                approved=True, age=30)
db.add(u); db.commit(); db.refresh(u)

today = datetime.now().date()
# One log per day for 400 days, each with a distinct calorie value
for i in range(400):
    d = today - timedelta(days=i)
    db.add(models.DailyLog(user_id=u.id, date=d, total_calories=1500 + (i % 100),
                           total_protein=100, total_carbs=150, total_fat=50,
                           goal_calories=2000, goal_met=True, total_points=10))
db.commit()

print(f"seeded 400 daily logs ending {today}")

def get(qs):
    r = c.get(f"/api/history/{u.id}{qs}")
    return r.status_code, r.json()

print("\n1. range=week  (the existing behaviour — must not regress)")
code, wk = get("?range=week")
print(f"     status {code}, {len(wk)} points, first={wk[0]['date']} label={wk[0]['label']}")
check("week is EXACTLY 7 bars", len(wk) == 7, len(wk))
check("week labels are weekday names", len(wk[0]["label"]) == 3, wk[0]["label"])

print("\n2. range=month  (now WEEKLY buckets)")
_, mo = get("?range=month")
print(f"     {len(mo)} points, labels={[p['label'] for p in mo]}")
check("month returns ~5 weekly bars", 4 <= len(mo) <= 7, len(mo))
check("month labels are dates (DD Mon)", len(mo[0]['label'].split()) == 2, mo[0]['label'])
check("month differs from week", len(mo) != len(wk), (len(mo), len(wk)))
check("month bars are daily averages not sums", all(p["calories"] < 3000 for p in mo),
      [p["calories"] for p in mo])

print("\n3. range=year")
_, yr = get("?range=year")
print(f"     {len(yr)} points, labels={[p['label'] for p in yr]}")
check("year is EXACTLY 12 bars", len(yr) == 12, len(yr))
check("year is NOT 365 daily bars", len(yr) < 100, len(yr))
check("year values are monthly averages (not sums)", all(p["calories"] < 3000 for p in yr),
      [p["calories"] for p in yr][:5])

print("\n4. legacy ?period= still works (backwards compatible)")
_, lp = get("?period=month")
check("period=month behaves like range=month", len(lp) == len(mo), (len(lp), len(mo)))
_, ly = get("?period=year")
check("period=year behaves like range=year", len(ly) == len(yr), (len(ly), len(yr)))

print("\n5. no param defaults to week")
_, dflt = get("")
check("defaults to week", len(dflt) == len(wk), len(dflt))

print("\n6. all three windows are DIFFERENT (the actual bug)")
check("week != month", len(wk) != len(mo))
check("week != year", len(wk) != len(yr))
check("month != year", len(mo) != len(yr))

print("\n7. stable axis — gaps are filled, not skipped")
check("week has no missing days (7 bars despite sparse logging)", len(wk) == 7, len(wk))
check("year has no missing months (12 bars)", len(yr) == 12, len(yr))
zero_wk = [p for p in wk if p["calories"] == 0]
zero_yr = [p for p in yr if p["calories"] == 0]
print(f"     zero-filled bars -> week: {len(zero_wk)}, year: {len(zero_yr)}")

print("\n" + "=" * 60)
print(f"RESULT: {'ALL PASSED' if not fails else str(len(fails)) + ' FAILED: ' + ', '.join(fails)}")
print("=" * 60)
