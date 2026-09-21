from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.crm import *
from app.models.billing import PaymentMethodCode
class Strict(BaseModel): model_config=ConfigDict(extra="forbid")
class CustomerCreateRequest(Strict): full_name:str=Field(min_length=2); mobile:str|None=None; email:EmailStr|None=None; customer_type:CustomerType=CustomerType.INDIVIDUAL; first_name:str|None=None; last_name:str|None=None; alternate_mobile:str|None=None; date_of_birth:date|None=None; gender:str|None=None; company_name:str|None=None; preferred_store_id:UUID|None=None; preferred_language:str="en"; communication_opt_in:bool=True; sms_opt_in:bool=True; whatsapp_opt_in:bool=True; email_opt_in:bool=True; loyalty_enrolled:bool=False; notes:str|None=None
class CustomerUpdateRequest(Strict): full_name:str|None=None; mobile:str|None=None; email:EmailStr|None=None; preferred_store_id:UUID|None=None; preferred_language:str|None=None; communication_opt_in:bool|None=None; sms_opt_in:bool|None=None; whatsapp_opt_in:bool|None=None; email_opt_in:bool|None=None; notes:str|None=None
class CustomerStatusUpdateRequest(Strict): status:CustomerStatus; reason:str|None=None
class CustomerResponse(BaseModel): id:UUID; customer_code:str; full_name:str; mobile:str|None; email:str|None; customer_type:CustomerType; preferred_store_id:UUID|None; loyalty_enrolled:bool; total_orders:int; total_spend:Decimal; average_order_value:Decimal; loyalty_points_balance:int; status:CustomerStatus; created_at:datetime
class LoyaltyAdjustmentRequest(Strict): customer_id:UUID|None=None; points:int; description:str=Field(min_length=2)
class LoyaltyRedeemRequest(Strict): customer_id:UUID; points:int=Field(gt=0); invoice_id:UUID|None=None
class LoyaltyReverseRequest(Strict): transaction_id:UUID; reason:str=Field(min_length=2)
class LoyaltyAccountResponse(BaseModel): model_config=ConfigDict(from_attributes=True); id:UUID; customer_id:UUID; points_balance:int; lifetime_points_earned:int; lifetime_points_redeemed:int; lifetime_points_expired:int; status:LoyaltyStatus
class LoyaltyTransactionResponse(BaseModel): model_config=ConfigDict(from_attributes=True); id:UUID; transaction_number:str; customer_id:UUID; transaction_type:LoyaltyType; points:int; balance_before:int; balance_after:int; monetary_value:Decimal|None; description:str; created_at:datetime
class MembershipTierRequest(Strict): name:str; code:str; level:int=Field(gt=0); minimum_spend:Decimal=Field(ge=0); maximum_spend:Decimal|None=Field(None,ge=0); discount_percentage:Decimal=Field(ge=0,le=100); loyalty_multiplier:Decimal=Field(ge=1); birthday_reward_points:int=Field(0,ge=0); benefits_json:dict={}; color:str|None=None; free_shipping_placeholder:bool=False; priority_support:bool=False; is_active:bool=True
class MembershipTierResponse(BaseModel): model_config=ConfigDict(from_attributes=True); id:UUID; name:str; code:str; level:int; minimum_spend:Decimal; maximum_spend:Decimal|None; discount_percentage:Decimal; loyalty_multiplier:Decimal; birthday_reward_points:int; benefits_json:dict; color:str|None; is_active:bool
class MembershipAssignmentRequest(Strict): tier_id:UUID; expires_at:datetime|None=None; reason:str|None=None
class CustomerMembershipResponse(BaseModel): model_config=ConfigDict(from_attributes=True); id:UUID; customer_id:UUID; membership_tier_id:UUID; started_at:datetime; expires_at:datetime|None; status:MembershipStatus; upgrade_reason:str|None
class TagRequest(Strict): name:str; code:str; color:str|None=None; description:str|None=None; is_active:bool=True
class TagResponse(BaseModel): model_config=ConfigDict(from_attributes=True); id:UUID; name:str; code:str; color:str|None; description:str|None; is_active:bool
class TagAssignment(Strict): tag_ids:list[UUID]=Field(min_length=1)
class SegmentRequest(Strict): name:str; code:str; description:str|None=None; segment_type:str; rules_json:dict; is_dynamic:bool=True; is_active:bool=True
class CommunicationRequest(Strict): customer_id:UUID; communication_type:str; direction:str; channel:Channel; subject:str|None=None; message_summary:str; message_body:str|None=None; status:str="LOGGED"; transactional:bool=False
class CommunicationResponse(BaseModel): model_config=ConfigDict(from_attributes=True); id:UUID; customer_id:UUID; communication_type:str; purpose:str; direction:str; channel:Channel; recipient:str|None; subject:str|None; message_summary:str; status:str; provider:str; provider_message_id:str|None; attempt_count:int; last_attempt_at:datetime|None; sent_at:datetime|None; delivered_at:datetime|None; read_at:datetime|None; failed_at:datetime|None; failure_code:str|None; failure_message:str|None; related_invoice_id:UUID|None; sent_by_id:UUID|None; created_at:datetime
class InvoiceCommunicationRequest(Strict): invoice_id:UUID
class SalesReturnCreateRequest(Strict): invoice_id:UUID; reason:str; items:list[dict]=Field(min_length=1); refund_method:PaymentMethodCode
