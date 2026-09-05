import re

def normalize_indian_phone(value:str|None)->str|None:
    digits=re.sub(r"\D","",value or "")
    if not digits:return None
    if len(digits)==10:return f"91{digits}"
    if len(digits)==12 and digits.startswith("91"):return digits
    if len(digits)==11 and digits.startswith("0"):return f"91{digits[1:]}"
    return digits

def phone_candidates(value:str|None)->set[str]:
    canonical=normalize_indian_phone(value)
    return {x for x in (canonical,canonical[-10:] if canonical and len(canonical)>=10 else None) if x}
