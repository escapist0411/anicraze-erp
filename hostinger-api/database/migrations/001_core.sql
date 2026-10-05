-- Hostinger PHP candidate core schema. Run only through the guarded migrator.
-- MariaDB/InnoDB; all timestamps are UTC DATETIME(6), money is DECIMAL.

CREATE TABLE roles (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 code VARCHAR(40) NOT NULL UNIQUE,
 name VARCHAR(120) NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE permissions (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 code VARCHAR(120) NOT NULL UNIQUE,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE role_permissions (
 role_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 permission_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 PRIMARY KEY (role_id, permission_id),
 CONSTRAINT fk_rp_role FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
 CONSTRAINT fk_rp_permission FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE stores (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 code VARCHAR(40) NOT NULL UNIQUE,
 name VARCHAR(180) NOT NULL,
 short_name VARCHAR(100) NULL,
 address TEXT NULL,
 location_type VARCHAR(30) NOT NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE warehouses (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 code VARCHAR(40) NOT NULL UNIQUE,
 name VARCHAR(180) NOT NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE users (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 email VARCHAR(320) NOT NULL UNIQUE,
 full_name VARCHAR(180) NOT NULL,
 password_hash VARCHAR(255) NOT NULL,
 phone VARCHAR(32) NULL,
 avatar_url VARCHAR(2048) NULL,
 preferred_language VARCHAR(16) NOT NULL DEFAULT 'en',
 timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Kolkata',
 status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
 is_active TINYINT(1) NOT NULL DEFAULT 1,
 token_version INT UNSIGNED NOT NULL DEFAULT 0,
 assigned_store_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
 employee_code VARCHAR(50) NULL UNIQUE,
 failed_login_attempts INT UNSIGNED NOT NULL DEFAULT 0,
 locked_until DATETIME(6) NULL,
 last_login_at DATETIME(6) NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 KEY idx_users_store (assigned_store_id),
 CONSTRAINT fk_users_store FOREIGN KEY (assigned_store_id) REFERENCES stores(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE user_roles (
 user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 role_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 PRIMARY KEY (user_id, role_id),
 CONSTRAINT fk_ur_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
 CONSTRAINT fk_ur_role FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE refresh_sessions (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL UNIQUE,
 token_version INT UNSIGNED NOT NULL,
 expires_at DATETIME(6) NOT NULL,
 revoked_at DATETIME(6) NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 KEY idx_sessions_user (user_id, revoked_at),
 CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE categories (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 code VARCHAR(40) NOT NULL UNIQUE,
 name VARCHAR(160) NOT NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
 sort_order INT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE anime_franchises (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 code VARCHAR(40) NOT NULL UNIQUE,
 name VARCHAR(160) NOT NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE products (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 sku VARCHAR(64) NOT NULL UNIQUE,
 barcode VARCHAR(64) NOT NULL UNIQUE,
 import_reference VARCHAR(120) NULL UNIQUE,
 name VARCHAR(220) NOT NULL,
 category_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 anime_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
 product_type VARCHAR(30) NOT NULL,
 edition VARCHAR(120) NULL,
 purchase_price DECIMAL(14,2) NOT NULL DEFAULT 0,
 selling_price DECIMAL(14,2) NOT NULL,
 status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 KEY idx_products_name (name),
 KEY idx_products_category (category_id),
 CONSTRAINT fk_products_category FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT,
 CONSTRAINT fk_products_anime FOREIGN KEY (anime_id) REFERENCES anime_franchises(id) ON DELETE RESTRICT,
 CONSTRAINT chk_product_prices CHECK (purchase_price >= 0 AND selling_price >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE inventory (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 product_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 store_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
 warehouse_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
 available_quantity INT NOT NULL DEFAULT 0,
 reserved_quantity INT NOT NULL DEFAULT 0,
 damaged_quantity INT NOT NULL DEFAULT 0,
 in_transit_quantity INT NOT NULL DEFAULT 0,
 average_cost DECIMAL(14,2) NOT NULL DEFAULT 0,
 last_purchase_cost DECIMAL(14,2) NOT NULL DEFAULT 0,
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 UNIQUE KEY uq_inventory_product_store (product_id, store_id),
 UNIQUE KEY uq_inventory_product_warehouse (product_id, warehouse_id),
 KEY idx_inventory_store (store_id),
 KEY idx_inventory_warehouse (warehouse_id),
 CONSTRAINT fk_inv_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
 CONSTRAINT fk_inv_store FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE RESTRICT,
 CONSTRAINT fk_inv_warehouse FOREIGN KEY (warehouse_id) REFERENCES warehouses(id) ON DELETE RESTRICT,
 CONSTRAINT chk_inv_location CHECK ((store_id IS NULL) <> (warehouse_id IS NULL)),
 CONSTRAINT chk_inv_quantities CHECK (available_quantity >= 0 AND reserved_quantity >= 0 AND damaged_quantity >= 0 AND in_transit_quantity >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE inventory_movements (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 inventory_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 product_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 movement_type VARCHAR(40) NOT NULL,
 quantity_delta INT NOT NULL,
 quantity_before INT NOT NULL,
 quantity_after INT NOT NULL,
 unit_cost DECIMAL(14,2) NOT NULL DEFAULT 0,
 reference_type VARCHAR(40) NOT NULL,
 reference_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 idempotency_key VARCHAR(160) NOT NULL UNIQUE,
 created_by_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 KEY idx_movements_inventory_time (inventory_id, created_at),
 KEY idx_movements_product_time (product_id, created_at),
 CONSTRAINT fk_mov_inv FOREIGN KEY (inventory_id) REFERENCES inventory(id) ON DELETE RESTRICT,
 CONSTRAINT fk_mov_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
 CONSTRAINT fk_mov_user FOREIGN KEY (created_by_id) REFERENCES users(id) ON DELETE RESTRICT,
 CONSTRAINT chk_movement_after CHECK (quantity_after >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE stock_receipts (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 receipt_number VARCHAR(60) NOT NULL UNIQUE,
 idempotency_key VARCHAR(160) NULL UNIQUE,
 status VARCHAR(30) NOT NULL DEFAULT 'READY_FOR_SCAN',
 supplier_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
 supplier_reference VARCHAR(120) NULL,
 notes TEXT NULL,
 created_by_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 finalized_at DATETIME(6) NULL,
 CONSTRAINT fk_receipt_user FOREIGN KEY (created_by_id) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE stock_receipt_items (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 receipt_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 product_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 quantity INT NOT NULL,
 scanned_quantity INT NOT NULL DEFAULT 0,
 purchase_cost DECIMAL(14,2) NOT NULL,
 UNIQUE KEY uq_receipt_product (receipt_id, product_id),
 CONSTRAINT fk_ri_receipt FOREIGN KEY (receipt_id) REFERENCES stock_receipts(id) ON DELETE RESTRICT,
 CONSTRAINT fk_ri_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
 CONSTRAINT chk_ri_qty CHECK (quantity > 0 AND scanned_quantity >= 0 AND scanned_quantity <= quantity AND purchase_cost >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE stock_transfers (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 transfer_number VARCHAR(60) NOT NULL UNIQUE,
 idempotency_key VARCHAR(160) NOT NULL UNIQUE,
 source_warehouse_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 target_store_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 status VARCHAR(30) NOT NULL DEFAULT 'COMPLETED',
 remarks TEXT NULL,
 created_by_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 CONSTRAINT fk_tr_warehouse FOREIGN KEY (source_warehouse_id) REFERENCES warehouses(id) ON DELETE RESTRICT,
 CONSTRAINT fk_tr_store FOREIGN KEY (target_store_id) REFERENCES stores(id) ON DELETE RESTRICT,
 CONSTRAINT fk_tr_user FOREIGN KEY (created_by_id) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE stock_transfer_items (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 transfer_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 product_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 quantity INT NOT NULL,
 unit_cost DECIMAL(14,2) NOT NULL DEFAULT 0,
 UNIQUE KEY uq_transfer_product (transfer_id, product_id),
 CONSTRAINT fk_ti_transfer FOREIGN KEY (transfer_id) REFERENCES stock_transfers(id) ON DELETE RESTRICT,
 CONSTRAINT fk_ti_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
 CONSTRAINT chk_ti_qty CHECK (quantity > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE invoice_counters (
 counter_key VARCHAR(40) PRIMARY KEY,
 current_value BIGINT UNSIGNED NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE invoices (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 invoice_number VARCHAR(60) NOT NULL UNIQUE,
 idempotency_key VARCHAR(160) NOT NULL UNIQUE,
 store_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 employee_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 customer_name_snapshot VARCHAR(180) NOT NULL,
 customer_phone_snapshot VARCHAR(30) NULL,
 subtotal DECIMAL(16,2) NOT NULL,
 discount DECIMAL(16,2) NOT NULL DEFAULT 0,
 grand_total DECIMAL(16,2) NOT NULL,
 payment_status VARCHAR(30) NOT NULL,
 invoice_status VARCHAR(30) NOT NULL,
 document_key VARCHAR(255) NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 KEY idx_invoice_store_time (store_id, created_at),
 CONSTRAINT fk_invoice_store FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE RESTRICT,
 CONSTRAINT fk_invoice_user FOREIGN KEY (employee_id) REFERENCES users(id) ON DELETE RESTRICT,
 CONSTRAINT chk_invoice_money CHECK (subtotal >= 0 AND discount >= 0 AND grand_total >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE invoice_items (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 invoice_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 product_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 inventory_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 product_name_snapshot VARCHAR(220) NOT NULL,
 sku_snapshot VARCHAR(64) NOT NULL,
 quantity INT NOT NULL,
 unit_price DECIMAL(14,2) NOT NULL,
 unit_cost_snapshot DECIMAL(14,2) NOT NULL,
 line_total DECIMAL(16,2) NOT NULL,
 KEY idx_item_invoice (invoice_id),
 CONSTRAINT fk_ii_invoice FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE RESTRICT,
 CONSTRAINT fk_ii_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
 CONSTRAINT fk_ii_inventory FOREIGN KEY (inventory_id) REFERENCES inventory(id) ON DELETE RESTRICT,
 CONSTRAINT chk_ii_qty CHECK (quantity > 0 AND unit_price >= 0 AND line_total >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE payments (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 invoice_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 method VARCHAR(20) NOT NULL,
 amount DECIMAL(16,2) NOT NULL,
 reference_number VARCHAR(120) NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 KEY idx_payment_invoice (invoice_id),
 CONSTRAINT fk_payment_invoice FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE RESTRICT,
 CONSTRAINT chk_payment_amount CHECK (amount > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE sales_returns (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 invoice_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 store_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 status VARCHAR(30) NOT NULL,
 total_amount DECIMAL(16,2) NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 CONSTRAINT fk_return_invoice FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE RESTRICT,
 CONSTRAINT fk_return_store FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE refunds (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 return_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 amount DECIMAL(16,2) NOT NULL,
 method VARCHAR(20) NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 CONSTRAINT fk_refund_return FOREIGN KEY (return_id) REFERENCES sales_returns(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE expenses (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 store_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
 amount DECIMAL(16,2) NOT NULL,
 expense_date DATE NOT NULL,
 category VARCHAR(100) NOT NULL,
 status VARCHAR(30) NOT NULL,
 CONSTRAINT fk_expense_store FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE audit_logs (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 actor_user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
 action VARCHAR(100) NOT NULL,
 entity_type VARCHAR(60) NOT NULL,
 entity_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
 context_json LONGTEXT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 KEY idx_audit_entity (entity_type, entity_id, created_at),
 CONSTRAINT fk_audit_actor FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE invoice_communications (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 invoice_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 channel VARCHAR(20) NOT NULL,
 status VARCHAR(30) NOT NULL,
 attempt_count INT NOT NULL DEFAULT 0,
 last_error_code VARCHAR(80) NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 CONSTRAINT fk_comms_invoice FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
