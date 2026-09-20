# Purchase payments

Purchase payables are separate from customer POS payments. They reuse the Supplier master and can optionally link one-to-one to a simple stock receipt. Stock receipt completion never depends on payment status.

A payable stores the invoice total, due date, notes, supplier snapshot, and receipt reference. Paid and pending amounts are calculated from immutable payment transactions. Recording uses a row lock and rejects amounts above the remaining balance. Status is derived as unpaid, partially paid, paid, or overdue.

Owners can record Cash, Bank Transfer, UPI, Cheque, or Other payments and schedule a PostgreSQL-backed reminder. Scheduling cancels the previous scheduled reminder and links the replacement through `snoozed_from_id`. Due-reminder reconciliation uses row locks with `skip_locked`; notification dedupe keys prevent duplicates. Render Cron can call the owner-authorized reconciliation endpoint, or owner notification reconciliation will trigger due reminders during normal use.

All `/api/v1/purchase-payables` endpoints are OWNER-role protected. Managers and employees receive 403 even if they directly call the API.
