from datetime import timedelta
from decimal import Decimal
from sqlalchemy import func, or_, select
from app.exceptions.domain import ConflictError, NotFoundError
from app.models.auth import AuditLog
from app.models.billing import Customer, Invoice, InvoiceStatus, Payment, Refund, Return
from app.models.crm import *
from app.models.procurement import ProcurementSequence
from app.repositories.management import ManagementRepository
from app.services.billing import ReturnService
from app.schemas.billing import ReturnCreate, ReturnItemInput
from app.utils.time import utc_now
from app.utils.phone import normalize_indian_phone,phone_candidates
class CRMBase:
 def __init__(self,s,actor,ip=None,user_agent=None): self.s=s; self.actor=actor; self.audit_repo=ManagementRepository(s); self.ip=ip; self.user_agent=user_agent
 async def audit(self,a,k,i,m=None): await self.audit_repo.audit(AuditLog(actor_user_id=self.actor.id,action=a,entity_type=k,entity_id=i,metadata_json=m,ip_address=self.ip,user_agent=self.user_agent,created_at=utc_now()))
 async def next(self,key,prefix):
  x=await self.s.scalar(select(ProcurementSequence).where(ProcurementSequence.key==key).with_for_update())
  if not x: x=ProcurementSequence(key=key,current_value=0); self.s.add(x); await self.s.flush()
  x.current_value+=1; return f"{prefix}-{x.current_value:06d}"
class CustomerService(CRMBase):
 async def create(self,d):
  mobile=normalize_indian_phone(d.mobile); email=str(d.email).lower() if d.email else None
  if mobile and await self.s.scalar(select(Customer).where(Customer.phone.in_(phone_candidates(mobile)),Customer.deleted_at.is_(None))): raise ConflictError("Customer mobile exists","CUSTOMER_MOBILE_EXISTS")
  if email and await self.s.scalar(select(Customer).where(func.lower(Customer.email)==email,Customer.deleted_at.is_(None))): raise ConflictError("Customer email exists","CUSTOMER_EMAIL_EXISTS")
  c=Customer(name=d.full_name,phone=mobile,email=email,gstin=d.gst_number,address=None,created_by_id=self.actor.id,updated_by_id=self.actor.id); self.s.add(c); await self.s.flush(); p=CustomerProfile(customer_id=c.id,customer_code="WALK-IN" if d.customer_type==CustomerType.WALK_IN else await self.next("customer","ANI-CUS"),customer_type=d.customer_type,first_name=d.first_name,last_name=d.last_name,alternate_mobile=d.alternate_mobile,date_of_birth=d.date_of_birth,gender=d.gender,company_name=d.company_name,preferred_store_id=d.preferred_store_id,preferred_language=d.preferred_language,communication_opt_in=d.communication_opt_in,sms_opt_in=d.sms_opt_in,whatsapp_opt_in=d.whatsapp_opt_in,email_opt_in=d.email_opt_in,loyalty_enrolled=d.loyalty_enrolled,total_orders=0,total_spend=0,average_order_value=0,status=CustomerStatus.ACTIVE,created_by_id=self.actor.id,updated_by_id=self.actor.id); self.s.add(p); await self.s.flush()
  if d.loyalty_enrolled and d.customer_type!=CustomerType.WALK_IN: self.s.add(LoyaltyAccount(customer_id=c.id,points_balance=0,lifetime_points_earned=0,lifetime_points_redeemed=0,lifetime_points_expired=0,status=LoyaltyStatus.ACTIVE,created_by_id=self.actor.id,updated_by_id=self.actor.id))
  await self.audit("CUSTOMER_CREATED","customer",c.id); return c,p
 async def rows(self,search=None):
  q=select(Customer,CustomerProfile,LoyaltyAccount).join(CustomerProfile,CustomerProfile.customer_id==Customer.id).outerjoin(LoyaltyAccount,LoyaltyAccount.customer_id==Customer.id).where(Customer.deleted_at.is_(None),CustomerProfile.deleted_at.is_(None));
  if search: q=q.where(or_(Customer.name.ilike(f"%{search}%"),Customer.phone.ilike(f"%{search}%"),Customer.email.ilike(f"%{search}%"),CustomerProfile.customer_code.ilike(f"%{search}%")))
  return (await self.s.execute(q.order_by(Customer.created_at.desc()))).all()
 def response(self,c,p,a=None):
  return dict(id=c.id,customer_code=p.customer_code,full_name=c.name,mobile=c.phone,email=c.email,customer_type=p.customer_type,preferred_store_id=p.preferred_store_id,loyalty_enrolled=p.loyalty_enrolled,total_orders=p.total_orders,total_spend=p.total_spend,average_order_value=p.average_order_value,loyalty_points_balance=a.points_balance if a else 0,status=p.status,created_at=c.created_at)
 async def update(self,id,d):
  row=(await self.s.execute(select(Customer,CustomerProfile).join(CustomerProfile).where(Customer.id==id,Customer.deleted_at.is_(None)).with_for_update())).first()
  if not row: raise NotFoundError("Customer not found","CUSTOMER_NOT_FOUND")
  c,p=row; values=d.model_dump(exclude_unset=True)
  values.pop("notes",None)
  for key,target in (("full_name","name"),("mobile","phone"),("email","email")):
   if key in values:setattr(c,target,normalize_indian_phone(values.pop(key)) if key=="mobile" else values.pop(key))
  for k,v in values.items():setattr(p,k,v)
  await self.audit("CUSTOMER_UPDATED","customer",c.id);return c,p
 async def status(self,id,status,reason=None):
  row=(await self.s.execute(select(Customer,CustomerProfile).join(CustomerProfile).where(Customer.id==id).with_for_update())).first()
  if not row:raise NotFoundError("Customer not found","CUSTOMER_NOT_FOUND")
  c,p=row;p.status=status;await self.audit("CUSTOMER_STATUS_CHANGED","customer",id,{"status":status.value,"reason":reason});return c,p
 async def delete(self,id):
  row=(await self.s.execute(select(Customer,CustomerProfile).join(CustomerProfile).where(Customer.id==id).with_for_update())).first()
  if not row:raise NotFoundError("Customer not found","CUSTOMER_NOT_FOUND")
  c,p=row
  if p.customer_code=="WALK-IN":raise ConflictError("Walk-in customer cannot be deleted","CUSTOMER_WALKIN_PROTECTED")
  c.deleted_at=utc_now();p.deleted_at=utc_now();p.status=CustomerStatus.ARCHIVED;await self.audit("CUSTOMER_DELETED","customer",id)
class LoyaltyService(CRMBase):
 async def adjust(self,customer_id,points,description,kind=None):
  a=await self.s.scalar(select(LoyaltyAccount).where(LoyaltyAccount.customer_id==customer_id,LoyaltyAccount.deleted_at.is_(None)).with_for_update())
  if not a: raise NotFoundError("Loyalty account not found","LOYALTY_ACCOUNT_NOT_FOUND")
  before=a.points_balance
  if before+points<0: raise ConflictError("Insufficient loyalty balance","LOYALTY_INSUFFICIENT_POINTS")
  a.points_balance+=points; a.lifetime_points_earned+=max(points,0); a.lifetime_points_redeemed+=max(-points,0); t=LoyaltyTransaction(transaction_number=await self.next("loyalty","ANI-LOY"),customer_id=customer_id,loyalty_account_id=a.id,transaction_type=kind or (LoyaltyType.ADJUSTMENT_CREDIT if points>0 else LoyaltyType.ADJUSTMENT_DEBIT),points=points,balance_before=before,balance_after=a.points_balance,description=description,created_by_id=self.actor.id); self.s.add(t); await self.s.flush(); await self.audit("LOYALTY_POINTS_ADJUSTED","customer",customer_id,{"points":points}); return t
 async def redeem(self,d):
  cfg=await self.s.scalar(select(LoyaltyConfig).where(LoyaltyConfig.is_active.is_(True),LoyaltyConfig.deleted_at.is_(None)))
  if not cfg or d.points<cfg.minimum_redeem_points: raise ConflictError("Minimum redemption not met","LOYALTY_MINIMUM_REDEMPTION")
  return await self.adjust(d.customer_id,-d.points,"Loyalty redemption",LoyaltyType.REDEEM)
 async def reverse(self,txid,reason):
  tx=await self.s.scalar(select(LoyaltyTransaction).where(LoyaltyTransaction.id==txid))
  if not tx: raise NotFoundError("Loyalty transaction not found","LOYALTY_TRANSACTION_NOT_FOUND")
  if await self.s.scalar(select(LoyaltyTransaction).where(LoyaltyTransaction.reversed_transaction_id==tx.id)): raise ConflictError("Transaction already reversed","LOYALTY_ALREADY_REVERSED")
  r=await self.adjust(tx.customer_id,-tx.points,reason,LoyaltyType.REVERSAL); r.reversed_transaction_id=tx.id; return r
class MembershipService(CRMBase):
 async def assign(self,cid,d):
  tier=await self.s.scalar(select(MembershipTier).where(MembershipTier.id==d.tier_id,MembershipTier.is_active.is_(True),MembershipTier.deleted_at.is_(None)))
  if not tier: raise NotFoundError("Membership tier not found","MEMBERSHIP_TIER_NOT_FOUND")
  old=await self.s.scalar(select(CustomerMembership).where(CustomerMembership.customer_id==cid,CustomerMembership.status==MembershipStatus.ACTIVE,CustomerMembership.deleted_at.is_(None)).with_for_update())
  if old and old.membership_tier_id==tier.id: return old
  if old: old.status=MembershipStatus.CANCELLED
  m=CustomerMembership(customer_id=cid,membership_tier_id=tier.id,started_at=utc_now(),expires_at=d.expires_at,status=MembershipStatus.ACTIVE,upgrade_reason=d.reason,previous_membership_id=old.id if old else None,created_by_id=self.actor.id,updated_by_id=self.actor.id); self.s.add(m); await self.s.flush(); await self.audit("MEMBERSHIP_ASSIGNED","customer",cid,{"tier":tier.code}); return m
class CRMAnalyticsService(CRMBase):
 async def dashboard(self):
  total=int(await self.s.scalar(select(func.count()).select_from(CustomerProfile).where(CustomerProfile.deleted_at.is_(None))) or 0); loyalty=int(await self.s.scalar(select(func.count()).select_from(LoyaltyAccount).where(LoyaltyAccount.deleted_at.is_(None))) or 0); spend=Decimal(await self.s.scalar(select(func.coalesce(func.sum(CustomerProfile.total_spend),0))) or 0); top=(await self.s.execute(select(CustomerProfile.customer_code,CustomerProfile.total_spend).order_by(CustomerProfile.total_spend.desc()).limit(5))).all(); return {"total_customers":total,"loyalty_members":loyalty,"total_lifetime_value":str(spend),"average_lifetime_value":str(spend/total if total else 0),"top_customers":[{"customer_code":x[0],"spend":str(x[1])} for x in top],"insights":[f"{loyalty} customers are enrolled in loyalty.",f"Average customer lifetime value is ₹{spend/total if total else 0:.2f}."]}
class CustomerCRMIntegration(CRMBase):
 async def invoice_completed(self,invoice):
  profile=await self.s.scalar(select(CustomerProfile).where(CustomerProfile.customer_id==invoice.customer_id,CustomerProfile.deleted_at.is_(None)).with_for_update())
  if not profile or profile.customer_type==CustomerType.WALK_IN: return
  profile.total_orders+=1; profile.total_spend+=invoice.grand_total; profile.average_order_value=profile.total_spend/profile.total_orders; profile.first_purchase_at=profile.first_purchase_at or invoice.created_at; profile.last_purchase_at=invoice.created_at
  if not profile.loyalty_enrolled: return
  if await self.s.scalar(select(LoyaltyTransaction).where(LoyaltyTransaction.invoice_id==invoice.id,LoyaltyTransaction.transaction_type==LoyaltyType.EARN)): return
  cfg=await self.s.scalar(select(LoyaltyConfig).where(LoyaltyConfig.is_active.is_(True),LoyaltyConfig.deleted_at.is_(None)))
  if not cfg: return
  base=invoice.taxable_amount if not cfg.points_on_tax_amount else invoice.grand_total; points=int(base*cfg.points_per_currency_unit)
  membership=await self.s.scalar(select(CustomerMembership).where(CustomerMembership.customer_id==invoice.customer_id,CustomerMembership.status==MembershipStatus.ACTIVE,CustomerMembership.deleted_at.is_(None)))
  if membership:
   tier=await self.s.scalar(select(MembershipTier).where(MembershipTier.id==membership.membership_tier_id)); points=int(Decimal(points)*tier.loyalty_multiplier)
  if points<=0:return
  tx=await LoyaltyService(self.s,self.actor,self.ip,self.user_agent).adjust(invoice.customer_id,points,f"Points earned on {invoice.invoice_number}",LoyaltyType.EARN); tx.invoice_id=invoice.id; tx.expires_at=utc_now()+timedelta(days=cfg.points_expiry_days)
