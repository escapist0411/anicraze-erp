ALTER TABLE product_images
 ADD COLUMN alt_text VARCHAR(220) NULL,
 ADD COLUMN sort_order INT NOT NULL DEFAULT 0,
 ADD COLUMN is_primary TINYINT(1) NOT NULL DEFAULT 0,
 ADD KEY idx_images_primary (product_id, is_primary, sort_order);
