CREATE TABLE stock_receipt_scans (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 receipt_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 receipt_item_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 scan_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 code_normalized VARCHAR(64) NOT NULL,
 created_by_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 UNIQUE KEY uq_receipt_scan_request (receipt_id, scan_id),
 CONSTRAINT fk_scan_receipt FOREIGN KEY (receipt_id) REFERENCES stock_receipts(id) ON DELETE RESTRICT,
 CONSTRAINT fk_scan_item FOREIGN KEY (receipt_item_id) REFERENCES stock_receipt_items(id) ON DELETE RESTRICT,
 CONSTRAINT fk_scan_user FOREIGN KEY (created_by_id) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
