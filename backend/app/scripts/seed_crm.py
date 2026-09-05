import asyncio
from decimal import Decimal
from sqlalchemy import select
from app.database.session import AsyncSessionFactory
from app.models.auth import User
from app.models.billing import Customer
from app.models.crm import *
from app.models.inventory import Store
from app.schemas.crm import CustomerCreateRequest,MembershipAssignmentRequest
from app.services.crm import CustomerService,LoyaltyService,MembershipService
NAMES=["Riya Naruto Fan","Arjun One Piece Collector","Kavya Jujutsu Buyer","Vikram Manga Reader","Ishita Figure Collector","Aditya Sharma","Sneha Kapoor","Rahul Mehta","Neha Joshi","Karan Malhotra","Ananya Rao","Rohan Desai","Maya Sen","Dev Patel","Tara Nair"]
async def seed():
 async with AsyncSessionFactory() as s:
  owner=await s.scalar(select(User).where(User.email=="owner@anicraze.com")); stores=list((await s.scalars(select(Store).where(Store.deleted_at.is_(None)).order_by(Store.code))).all()); cs=CustomerService(s,owner)
  walk=await s.scalar(select(Customer).where(Customer.name=="Walk-in Customer"))
  if not walk: walk,_=await cs.create(CustomerCreateRequest(full_name="Walk-in Customer",customer_type=CustomerType.WALK_IN))
  elif not await s.scalar(select(CustomerProfile).where(CustomerProfile.customer_id==walk.id)): s.add(CustomerProfile(customer_id=walk.id,customer_code="WALK-IN",customer_type=CustomerType.WALK_IN,preferred_language="en",communication_opt_in=False,sms_opt_in=False,whatsapp_opt_in=False,email_opt_in=False,loyalty_enrolled=False,total_orders=0,total_spend=0,average_order_value=0,status=CustomerStatus.ACTIVE,created_by_id=owner.id,updated_by_id=owner.id))
  customers=[]
  for i,name in enumerate(NAMES):
   mobile=f"98100{i:05d}"; c=await s.scalar(select(Customer).where(Customer.phone==mobile))
   if not c: c,p=await cs.create(CustomerCreateRequest(full_name=name,mobile=mobile,email=f"crm{i+1}@example.com",preferred_store_id=stores[i%len(stores)].id,loyalty_enrolled=True,notes="CRM demo customer"))
   customers.append(c)
  if not await s.scalar(select(LoyaltyConfig)):
   s.add(LoyaltyConfig(program_name="ANICRAZE Rewards",points_per_currency_unit=Decimal("0.01"),minimum_redeem_points=100,redemption_value_per_point=Decimal("0.50"),maximum_redemption_percentage=Decimal("20"),points_expiry_days=365,points_on_discounted_amount=True,points_on_tax_amount=False,allow_partial_redemption=True,is_active=True,created_by_id=owner.id,updated_by_id=owner.id))
  tiers=[]
  for level,(code,minimum,maximum,discount,multiplier) in enumerate((("SILVER",0,24999,0,1),("GOLD",25000,74999,5,Decimal("1.25")),("PLATINUM",75000,149999,10,Decimal("1.5")),("VIP",150000,None,15,2)),1):
   t=await s.scalar(select(MembershipTier).where(MembershipTier.code==code))
   if not t: t=MembershipTier(name=code.title(),code=code,level=level,minimum_spend=minimum,maximum_spend=maximum,discount_percentage=discount,loyalty_multiplier=multiplier,birthday_reward_points=level*100,free_shipping_placeholder=level>=3,priority_support=level>=3,benefits_json={"tier":code},color="#D4AF37",is_active=True,created_by_id=owner.id,updated_by_id=owner.id);s.add(t);await s.flush()
   tiers.append(t)
  for code,color in (("VIP","#7C3AED"),("HIGH_VALUE","#F59E0B"),("NARUTO_FAN","#F97316"),("ONE_PIECE_FAN","#EF4444"),("FREQUENT_BUYER","#10B981"),("MANGA_BUYER","#3B82F6")):
   if not await s.scalar(select(CustomerTag).where(CustomerTag.code==code)): s.add(CustomerTag(name=code.replace("_"," ").title(),code=code,color=color,is_active=True,created_by_id=owner.id,updated_by_id=owner.id))
  if not await s.scalar(select(CustomerSegment)):
   s.add_all([CustomerSegment(name="High Value",code="HIGH_VALUE",segment_type="DYNAMIC",rules_json={"total_spend":{"gt":"25000"}},is_dynamic=True,is_active=True,created_by_id=owner.id,updated_by_id=owner.id),CustomerSegment(name="Anime Fans",code="ANIME_FANS",segment_type="MANUAL",rules_json={},is_dynamic=False,is_active=True,created_by_id=owner.id,updated_by_id=owner.id)])
  ls=LoyaltyService(s,owner); ms=MembershipService(s,owner)
  for i,c in enumerate(customers[:8]):
   if not await s.scalar(select(LoyaltyTransaction).where(LoyaltyTransaction.customer_id==c.id)): await ls.adjust(c.id,150+i*25,"Opening demo loyalty points")
   if not await s.scalar(select(CustomerMembership).where(CustomerMembership.customer_id==c.id,CustomerMembership.status==MembershipStatus.ACTIVE)): await ms.assign(c.id,MembershipAssignmentRequest(tier_id=tiers[min(i//2,3)].id,reason="Demo tier assignment"))
   if not await s.scalar(select(CustomerCommunication).where(CustomerCommunication.customer_id==c.id)): s.add(CustomerCommunication(customer_id=c.id,communication_type="WELCOME",direction="OUTBOUND",channel=Channel.EMAIL,subject="Welcome to ANICRAZE",message_summary="Rewards membership welcome",status="SENT",sent_by_id=owner.id,sent_at=__import__('app.utils.time',fromlist=['utc_now']).utc_now(),created_by_id=owner.id,updated_by_id=owner.id))
  if not await s.scalar(select(StoreCreditLedger)):
   s.add(StoreCreditLedger(customer_id=customers[0].id,transaction_type="CREDIT",amount=Decimal("500"),balance_before=0,balance_after=Decimal("500"),reference_type="DEMO",description="Demo store credit",created_by_id=owner.id,created_at=__import__('app.utils.time',fromlist=['utc_now']).utc_now()))
  await s.commit()
if __name__=="__main__": asyncio.run(seed())
