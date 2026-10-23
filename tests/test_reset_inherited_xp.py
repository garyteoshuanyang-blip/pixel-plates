"""One-time repair: duck/tortoise spirits reset to a fresh egg.

Verifies the guarded migration in check_and_migrate():
  - duck + tortoise reset to xp=0, level=1, happiness=100, hunger=100, checkpoint=baseline
  - chicken left completely untouched
  - running it twice changes nothing (idempotent)
"""
import os, sys, tempfile
from datetime import date

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp(prefix='reset-test-')}/t.db"
sys.path.insert(0, "/home/gary/Projects/pixel-plates")

from backend.main import check_and_migrate, SessionLocal, lifetime_points

engine = SessionLocal().bind
from backend import models
from sqlalchemy import text

fails = []
def check(label, cond, extra=""):
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {extra}")
    if not cond: fails.append(label)

models.Base.metadata.create_all(bind=engine)
db = SessionLocal()

# A user with 800 lifetime points, and three spirits: chicken (earned), duck, tortoise.
u = models.User(name="Nikki", email="n@t", hashed_password="x", role="client",
                approved=True, age=30, total_points=800)
db.add(u); db.commit(); db.refresh(u)
for i in range(40):
    db.add(models.DailyLog(user_id=u.id, date=date(2026, 9, 1 + i % 28), total_calories=2000,
                           goal_calories=2000, goal_met=True, points_calories=20,
                           points_protein=0, points_carbs=0, points_fat=0, total_points=20))
db.commit()
lifetime = lifetime_points(db, u.id)
print(f"lifetime points: {lifetime}")

db.add_all([
    models.Pet(user_id=u.id, name="吉祥品", species="chicken", is_active=False, retired_at=None,
               xp=76, level=4, happiness=60, hunger=55, last_xp_checkpoint=lifetime),
    models.Pet(user_id=u.id, name="北京烤鸭", species="duck", is_active=False,
               xp=79, level=5, happiness=30, hunger=25, last_xp_checkpoint=lifetime),
    models.Pet(user_id=u.id, name="Tortoise", species="tortoise", is_active=True,
               xp=80, level=5, happiness=40, hunger=35, last_xp_checkpoint=lifetime),
])
db.commit()

def snap():
    rows = db.query(models.Pet).order_by(models.Pet.id).all()
    return {p.species: (p.xp, p.level, p.happiness, p.hunger, p.last_xp_checkpoint) for p in rows}

before = snap()
print("\nbefore:", before)

print("\n1. run the migration")
check_and_migrate()
db.expire_all()
after = snap()
print("after :", after)

check("duck reset to egg", after["duck"][:4] == (0, 1, 100, 100), after["duck"][:4])
check("tortoise reset to egg", after["tortoise"][:4] == (0, 1, 100, 100), after["tortoise"][:4])
check("chicken UNTOUCHED", after["chicken"] == before["chicken"], after["chicken"])
check("duck checkpoint baselined to lifetime", after["duck"][4] == lifetime, after["duck"][4])
check("tortoise checkpoint baselined to lifetime", after["tortoise"][4] == lifetime, after["tortoise"][4])

print("\n2. run it AGAIN (must be a no-op)")
mid = snap()
check_and_migrate()
db.expire_all()
again = snap()
print("again :", again)
check("idempotent — nothing changed on the second run", again == mid)

print("\n3. the marker row exists exactly once")
with engine.begin() as c:
    n = c.execute(text("SELECT COUNT(*) FROM schema_migrations WHERE name='reset_inherited_pet_xp'")).scalar()
check("exactly one marker row", n == 1, n)

print("\n4. a NEWLY adopted spirit is unaffected by the migration")
r = models.Pet(user_id=u.id, name="Duck2", species="duck", is_active=False, xp=0, level=1,
               happiness=100, hunger=100, last_xp_checkpoint=lifetime)
db.add(r); db.commit()
check_and_migrate()
db.expire_all()
fresh = db.query(models.Pet).filter(models.Pet.name == "Duck2").first()
check("fresh duck stays at 0 XP (migration already applied)", (fresh.xp or 0) == 0, fresh.xp)

print("\n" + "=" * 60)
print(f"RESULT: {'ALL PASSED' if not fails else str(len(fails)) + ' FAILED: ' + ', '.join(fails)}")
print("=" * 60)
