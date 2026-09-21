"""Idempotently create ANICRAZE's final users from local environment secrets."""
import asyncio
import os

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.auth.passwords import hash_password
from app.database.session import AsyncSessionFactory
from app.models.auth import Role, User, UserStatus, user_roles
from app.models.inventory import EmployeeLocationSequence, Store
from app.services.password_service import PasswordService

EXPECTED_DATABASE="anicraze_demo"
DEMO_EMAILS=("owner.demo@anicraze.in","manager.demo@anicraze.in","employee.demo@anicraze.in")
ACCOUNTS=(
 ("owner@anicraze.in","ANICRAZE Owner","OWNER",None,"ANICRAZE_OWNER_PASSWORD"),
 ("manager@anicraze.in","ANICRAZE Manager","MANAGER",None,"ANICRAZE_MANAGER_PASSWORD"),
 ("elpro@anicraze.in","ANICRAZE ELPRO","SALES","ELPRO","ANICRAZE_ELPRO_PASSWORD"),
 ("westend@anicraze.in","ANICRAZE WESTEND","SALES","WESTEND","ANICRAZE_WESTEND_PASSWORD"),
 ("civil@anicraze.in","ANICRAZE CIVIL","SALES","CIVIL","ANICRAZE_CIVIL_PASSWORD"),
 ("swargate@anicraze.in","ANICRAZE SWARGATE","SALES","SWARGATE","ANICRAZE_SWARGATE_PASSWORD"),
 ("kalyani@anicraze.in","ANICRAZE KALYANI","SALES","KALYANI","ANICRAZE_KALYANI_PASSWORD"),
 ("shivaji@anicraze.in","ANICRAZE SHIVAJI","SALES","SHIVAJI","ANICRAZE_SHIVAJI_PASSWORD"),
 ("event.1@anicraze.in","ANICRAZE EVENT 1","SALES","EVENT1","ANICRAZE_EVENT1_PASSWORD"),
 ("event.2@anicraze.in","ANICRAZE EVENT 2","SALES","EVENT2","ANICRAZE_EVENT2_PASSWORD"),
)

def credentials():
 values={key:os.environ.get(key,"") for *_,key in ACCOUNTS}
 missing=[key for key,value in values.items() if len(value)<12]
 if missing: raise RuntimeError("Missing or short password variables: "+", ".join(missing))
 return values

async def next_employee_code(session,store):
 await session.execute(insert(EmployeeLocationSequence).values(store_id=store.id,current_value=0).on_conflict_do_nothing(index_elements=[EmployeeLocationSequence.store_id]))
 sequence=await session.scalar(select(EmployeeLocationSequence).where(EmployeeLocationSequence.store_id==store.id).with_for_update())
 highest=await session.scalar(select(func.max(User.employee_code)).where(User.employee_code.like(f"EMP-{store.code.upper()}-%")))
 used=int(highest.rsplit("-",1)[-1]) if highest and highest.rsplit("-",1)[-1].isdigit() else 0
 sequence.current_value=max(sequence.current_value,used)+1
 return f"EMP-{store.code.upper()}-{sequence.current_value:03d}"

async def bootstrap():
 passwords=credentials()
 async with AsyncSessionFactory() as session:
  database=await session.scalar(text("select current_database()"))
  if database!=EXPECTED_DATABASE or os.environ.get("ANICRAZE_CONFIRM_DATABASE")!=EXPECTED_DATABASE:
   raise RuntimeError(f"Refusing user bootstrap for database {database!r}")
  await session.execute(text("select pg_advisory_xact_lock(1602028)"))
  roles={r.code:r for r in (await session.scalars(select(Role).where(Role.code.in_({x[2] for x in ACCOUNTS})))).all()}
  if set(roles)!={"OWNER","MANAGER","SALES"}: raise RuntimeError("Required OWNER, MANAGER, and SALES roles do not exist")
  codes={x[3] for x in ACCOUNTS if x[3]}
  stores={s.code:s for s in (await session.scalars(select(Store).where(Store.code.in_(codes),Store.deleted_at.is_(None)))).all()}
  if set(stores)!=codes: raise RuntimeError("Missing required selling locations: "+", ".join(sorted(codes-set(stores))))
  created=[]
  for email,name,role_code,store_code,password_key in ACCOUNTS:
   user=await session.scalar(select(User).options(selectinload(User.roles)).where(User.email==email))
   store=stores.get(store_code)
   if user is None:
    user=User(email=email,full_name=name,password_hash="")
    session.add(user);await session.flush()
   PasswordService().validate_new_password(passwords[password_key],user)
   user.full_name=name;user.password_hash=hash_password(passwords[password_key]);user.token_version+=1
   await session.execute(delete(user_roles).where(user_roles.c.user_id==user.id))
   await session.execute(insert(user_roles).values(user_id=user.id,role_id=roles[role_code].id))
   user.assigned_store_id=store.id if store else None
   if store and (not user.employee_code or not user.employee_code.startswith(f"EMP-{store.code}-")):
    user.employee_code=await next_employee_code(session,store)
   user.status=UserStatus.ACTIVE;user.is_active=True;user.deleted_at=None;user.must_change_password=False
   created.append((email,role_code,store_code,user.employee_code))
  demos=(await session.scalars(select(User).where(User.email.in_(DEMO_EMAILS)))).all()
  for user in demos:
   user.status=UserStatus.INACTIVE;user.is_active=False;user.token_version+=1
   await session.execute(delete(user_roles).where(user_roles.c.user_id==user.id))
  await session.commit()
  print(f"Configured {len(created)} final accounts; disabled {len(demos)} demo accounts. Passwords were not logged.")

if __name__=="__main__": asyncio.run(bootstrap())
