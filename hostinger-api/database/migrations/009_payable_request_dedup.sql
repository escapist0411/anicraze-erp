ALTER TABLE purchase_payables
 ADD COLUMN request_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL DEFAULT '';

ALTER TABLE purchase_payments
 ADD COLUMN request_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL DEFAULT '';

ALTER TABLE payment_reminders
 ADD COLUMN idempotency_key VARCHAR(160) NOT NULL UNIQUE,
 ADD COLUMN request_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL DEFAULT '';
