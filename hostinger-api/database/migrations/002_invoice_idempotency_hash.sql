ALTER TABLE invoices ADD COLUMN request_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL AFTER idempotency_key;
