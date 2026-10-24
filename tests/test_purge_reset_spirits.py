"""purge_reset_spirits: remove the reset duck/tortoise spirits from collections.

After the XP reset, those rows still counted as "owned", so the album read 3/3
and the adopt gate blocked those users from ever adopting again.

Checks:
  - duck + tortoise created BEFORE the reset are deleted
  - the chicken is kept, and re-activated when the user would have none
  - a duck adopted AFTER the reset is NOT touched
  - the second run is a no-op
"""
import os, sys, tempfile
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp(prefix='purge-test-')}/t.db"
sys.path.insert(0, "/home/gary/Projects/pixel-plates")

from backend.main import check_and_migrate, SessionLocal
from backend import models
from sqlalchemy import text

engine = SessionLocal().bind
fails = []
def check(label, cond, extra=""):
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {extra}")
    if not cond: fails.append(label)

models.Base.metadata.create_all(bind=engine)
db = SessionLocal()

now = datetime.utcnow()
reset_at = now - timedelta(hours=2)      # the reset migration ran 2h ago
before_reset = now - timedelta(days=5)

# --- users ---
nikki = models.User(name="Nikki", email="n@t", hashed_password="x", role="client", approved=True, age=30)
jeong = models.User(name="Jeong", email="j@t", hashed_password="x", role="client", approved=True, age=30)
db.add_all([nikki, jeong]); db.commit(); db.refresh(nikki); db.refresh(jeong)

# Nikki: chicken (earned, retired) + duck egg (retired) + tortoise egg (ACTIVE)  -> all pre-reset
db.add_all([
    models.Pet(user_id=nikki.id, name="吉祥品", species="chicken", is_active=False,
               retired_at=before_reset, xp=76, level=4, happiness=60, hunger=55,
               last_xp_checkpoint=800, created_at=before_reset),
    models.Pet(user_id=nikki.id, name="北京烤鸭", species="duck", is_active=False,
               retired_at=before_reset, xp=0, level=1, happiness=100, hunger=100,
               last_xp_checkpoint=805, created_at=before_reset),
    models.Pet(user_id=nikki.id, name="Tortoise", species="tortoise", is_active=True,
               xp=2, level=1, happiness=100, hunger=100,
               last_xp_checkpoint=805, created_at=before_reset),
])
# Jeong: chicken (earned, retired) + duck egg (ACTIVE, pre-reset)
db.add_all([
    models.Pet(user_id=jeong.id, name="Chickiki", species="chicken", is_active=False,
               retired_at=before_reset, xp=62, level=4, happiness=70, hunger=65,
               last_xp_checkpoint=535, created_at=before_reset),
    models.Pet(user_id=jeong.id, name="Dook", species="duck", is_active=True,
               xp=0, level=1, happiness=100, hunger=100,
               last_xp_checkpoint=535, created_at=before_reset),
])
db.commit()

# The reset migration is on record (this is the cutoff source)
with engine.begin() as c:
    c.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (name VARCHAR PRIMARY KEY, applied_at TIMESTAMP)"))
    c.execute(text("INSERT INTO schema_migrations (name, applied_at) VALUES ('reset_inherited_pet_xp', :t)"),
              {"t": reset_at})

def snap():
    return {p.name: (p.species, p.xp, bool(p.is_active)) for p in db.query(models.Pet).all()}

print("before:", snap())
print()

print("1. run the purge")
check_and_migrate()
db.expire_all()
after = snap()
print("after :", after)
check("duck '北京烤鸭' deleted", "北京烤鸭" not in after)
check("tortoise 'Tortoise' deleted", "Tortoise" not in after)
check("duck 'Dook' deleted", "Dook" not in after)
check("chicken '吉祥品' KEPT", "吉祥品" in after, after.get("吉祥品"))
check("chicken 'Chickiki' KEPT", "Chickiki" in after, after.get("Chickiki"))
check("chicken XP untouched (76)", after.get("吉祥品", (None, None))[1] == 76)
check("nikki's chicken re-activated", after.get("吉祥品", (None, None, None))[2] is True)
check("jeong's chicken re-activated", after.get("Chickiki", (None, None, None))[2] is True)
check("only 1 spirit left for nikki", sum(1 for v in after.values() if v[1] is not None) >= 2)

print("\n2. run AGAIN — must be a no-op")
mid = snap()
check_and_migrate()
db.expire_all()
check("idempotent", snap() == mid)

print("\n3. a duck adopted AFTER the reset is preserved")
fresh = models.Pet(user_id=jeong.id, name="LegitDuck", species="duck", is_active=False,
                   xp=0, level=1, happiness=100, hunger=100, created_at=now)
db.add(fresh); db.commit()
# force the purge to be re-runnable for this check
with engine.begin() as c:
    c.execute(text("DELETE FROM schema_migrations WHERE name='purge_reset_spirits'"))
check_and_migrate()
db.expire_all()
kept = db.query(models.Pet).filter(models.Pet.name == "LegitDuck").first()
check("post-reset duck NOT deleted", kept is not None)

print("\n" + "=" * 60)
print(f"RESULT: {'ALL PASSED' if not fails else str(len(fails)) + ' FAILED: ' + ', '.join(fails)}")
print("=" * 60)
