# Store and employee flow

Stores are selling locations with a stable code, name, type (`PERMANENT_STORE` or `EVENT_LOCATION`), optional address/contact number, and active status. The Central Warehouse remains a separate warehouse entity.

Every sales employee has one `assigned_store_id`. Login returns this assignment, and the phone POS loads it automatically. Billing, barcode lookup, inventory search, invoice access, returns, and refunds enforce this shop on the backend instead of trusting a frontend `store_id`.

Employee codes use stable location codes (for example `EMP-CHI-001`), never parsed display names. Owners can create, reassign, activate/deactivate, and reset employee passwords through the existing user-management APIs. Assignment changes and employee changes are audited without passwords or tokens.

The employee UI keeps Scan & Bill prominent, uses large touch targets, supports camera scanning with rear-camera preference and cleanup, and retains manual/HID scanner input.
