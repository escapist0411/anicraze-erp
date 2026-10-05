ALTER TABLE inventory_movements
 ADD COLUMN reference_number VARCHAR(100) NULL,
 ADD COLUMN remarks TEXT NULL;

CREATE TABLE stock_adjustments (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 reference_number VARCHAR(100) NOT NULL UNIQUE,
 request_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 reason VARCHAR(255) NOT NULL,
 status VARCHAR(30) NOT NULL DEFAULT 'COMPLETED',
 created_by_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 KEY idx_adjustment_created (created_at),
 CONSTRAINT fk_adjustment_user FOREIGN KEY (created_by_id) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE stock_adjustment_items (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 adjustment_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 inventory_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 quantity_change INT NOT NULL,
 quantity_before INT NOT NULL,
 quantity_after INT NOT NULL,
 batch_number VARCHAR(100) NULL,
 remarks TEXT NULL,
 UNIQUE KEY uq_adjustment_inventory (adjustment_id, inventory_id),
 KEY idx_adjustment_item_inventory (inventory_id),
 CONSTRAINT fk_adjustment_item_parent FOREIGN KEY (adjustment_id) REFERENCES stock_adjustments(id) ON DELETE RESTRICT,
 CONSTRAINT fk_adjustment_item_inventory FOREIGN KEY (inventory_id) REFERENCES inventory(id) ON DELETE RESTRICT,
 CONSTRAINT chk_adjustment_quantity CHECK (quantity_change <> 0 AND quantity_after >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
