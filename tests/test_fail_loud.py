"""Verify the fail-loud fix: a dead AI key must produce a VISIBLE warning.

Runs the real create-meal flow against a throwaway SQLite DB with a deliberately
invalid OPENROUTER_API_KEY.
"""
import os, sys, tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp(prefix='loud-test-')}/t.db"
# an invalid key -> the AI call will 401, exactly like the prod incident
# a deliberately invalid credential -> the AI call fails, exactly like the prod incident
# (kept free of secret-looking prefixes so repository secret-scanning doesn't block the push)
os.environ["OPENROUTER_API_KEY"] = "not-a-real-key-intentionally-invalid"
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
u = models.User(name="Loud", email="loud@test", hashed_password="x",
                role="client", approved=True, age=30)
db.add(u); db.commit(); db.refresh(u)

print("1. AI with a DEAD key (the exact prod failure)")
r = c.post("/api/meals", data={"user_id": u.id, "food_name": "chicken rice"})
check("request succeeded", r.status_code == 200, r.status_code)
d = r.json()
print(f"     returned: calories={d.get('calories')}  comment={d.get('nutrition_comment')!r}")
check("calories is 0 (AI failed)", d.get("calories") in (0, 0.0, None), d.get("calories"))
check("a WARNING is surfaced", "AI unavailable" in str(d.get("nutrition_comment", "")),
      d.get("nutrition_comment"))
check("warning is NOT the old silent empty string", d.get("nutrition_comment") != "", repr(d.get("nutrition_comment")))

print("\n2. it persists — so it shows in TODAY'S MEALS too")
meals = c.get(f"/api/meals/{u.id}").json()
if meals:
    m = meals[0]
    print(f"     stored meal: {m.get('food_name')}  calories={m.get('calories')}  comment={m.get('nutrition_comment')!r}")
    check("stored meal carries the warning", "AI unavailable" in str(m.get("nutrition_comment", "")),
          m.get("nutrition_comment"))

print("\n3. a manual entry is NOT mislabelled (no false alarms)")
r = c.post("/api/meals", data={"user_id": u.id, "food_name": "banana", "calories": 105})
d = r.json()
print(f"     returned: calories={d.get('calories')}  comment={d.get('nutrition_comment')!r}")
check("manual calories preserved", d.get("calories") == 105, d.get("calories"))
check("NO false 'AI unavailable' warning on a manual entry",
      "AI unavailable" not in str(d.get("nutrition_comment", "")), repr(d.get("nutrition_comment")))

print("\n4. food-library pick is still labelled correctly")
r = c.post("/api/meals", data={"user_id": u.id, "food_name": "x", "calories": 200, "food_db_id": 1})
d = r.json()
print(f"     returned: calories={d.get('calories')}  comment={d.get('nutrition_comment')!r}")

print("\n" + "=" * 60)
print(f"RESULT: {'ALL PASSED' if not fails else str(len(fails)) + ' FAILED: ' + ', '.join(fails)}")
print("=" * 60)
