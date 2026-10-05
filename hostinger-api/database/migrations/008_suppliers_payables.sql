CREATE TABLE suppliers (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 supplier_code VARCHAR(60) NOT NULL UNIQUE,
 display_name VARCHAR(180) NOT NULL,
 company_name VARCHAR(180) NOT NULL,
 email VARCHAR(320) NULL,
 phone VARCHAR(30) NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
 notes TEXT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 KEY idx_supplier_name (display_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE stock_receipts
 ADD KEY idx_receipt_supplier (supplier_id),
 ADD CONSTRAINT fk_receipt_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT;

CREATE TABLE purchase_payables (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 idempotency_key VARCHAR(160) NOT NULL UNIQUE,
 reference_number VARCHAR(60) NOT NULL UNIQUE,
 supplier_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 supplier_name_snapshot VARCHAR(180) NOT NULL,
 stock_receipt_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL UNIQUE,
 invoice_number VARCHAR(100) NULL,
 invoice_date DATE NOT NULL,
 total_amount DECIMAL(18,2) NOT NULL,
 amount_paid DECIMAL(18,2) NOT NULL DEFAULT 0,
 status VARCHAR(25) NOT NULL DEFAULT 'UNPAID',
 due_date DATE NULL,
 reminder_enabled TINYINT(1) NOT NULL DEFAULT 0,
 notes TEXT NULL,
 created_by_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 KEY idx_payable_supplier (supplier_id),
 KEY idx_payable_status_due (status, due_date),
 CONSTRAINT fk_payable_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT,
 CONSTRAINT fk_payable_receipt FOREIGN KEY (stock_receipt_id) REFERENCES stock_receipts(id) ON DELETE RESTRICT,
 CONSTRAINT fk_payable_user FOREIGN KEY (created_by_id) REFERENCES users(id) ON DELETE RESTRICT,
 CONSTRAINT chk_payable_amount CHECK (total_amount > 0 AND amount_paid >= 0 AND amount_paid <= total_amount)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE purchase_payments (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 payable_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 idempotency_key VARCHAR(160) NOT NULL UNIQUE,
 amount DECIMAL(18,2) NOT NULL,
 payment_method VARCHAR(30) NOT NULL,
 payment_date DATE NOT NULL,
 reference_number VARCHAR(120) NULL,
 notes TEXT NULL,
 created_by_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 KEY idx_purchase_payment_payable (payable_id),
 CONSTRAINT fk_purchase_payment_parent FOREIGN KEY (payable_id) REFERENCES purchase_payables(id) ON DELETE RESTRICT,
 CONSTRAINT fk_purchase_payment_user FOREIGN KEY (created_by_id) REFERENCES users(id) ON DELETE RESTRICT,
 CONSTRAINT chk_purchase_payment_amount CHECK (amount > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE payment_reminders (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 payable_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 remind_at DATETIME(6) NOT NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'SCHEDULED',
 triggered_at DATETIME(6) NULL,
 dismissed_at DATETIME(6) NULL,
 snoozed_from_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 KEY idx_reminder_schedule (status, remind_at),
 KEY idx_reminder_payable (payable_id),
 CONSTRAINT fk_reminder_payable FOREIGN KEY (payable_id) REFERENCES purchase_payables(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
