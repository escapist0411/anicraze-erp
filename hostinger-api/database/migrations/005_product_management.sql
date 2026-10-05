CREATE TABLE brands (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 code VARCHAR(40) NOT NULL UNIQUE,
 name VARCHAR(160) NOT NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE characters (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 code VARCHAR(40) NOT NULL UNIQUE,
 name VARCHAR(160) NOT NULL,
 anime_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
 KEY idx_characters_anime (anime_id),
 CONSTRAINT fk_characters_anime FOREIGN KEY (anime_id) REFERENCES anime_franchises(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE product_sku_counters (
 counter_key VARCHAR(30) PRIMARY KEY,
 current_value BIGINT UNSIGNED NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE categories ADD COLUMN description TEXT NULL;

ALTER TABLE products
 ADD COLUMN brand_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
 ADD COLUMN character_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
 ADD COLUMN short_description VARCHAR(500) NULL,
 ADD COLUMN description TEXT NULL,
 ADD COLUMN material VARCHAR(120) NULL,
 ADD COLUMN manufacturer VARCHAR(160) NULL,
 ADD COLUMN country_of_origin VARCHAR(100) NULL,
 ADD COLUMN landed_cost DECIMAL(14,2) NULL,
 ADD COLUMN mrp DECIMAL(14,2) NULL,
 ADD COLUMN minimum_selling_price DECIMAL(14,2) NULL,
 ADD COLUMN discount_percentage DECIMAL(5,2) NOT NULL DEFAULT 0,
 ADD COLUMN reorder_level INT NOT NULL DEFAULT 0,
 ADD COLUMN unit_of_measure VARCHAR(40) NOT NULL DEFAULT 'piece',
 ADD COLUMN weight DECIMAL(12,3) NULL,
 ADD COLUMN length DECIMAL(12,3) NULL,
 ADD COLUMN width DECIMAL(12,3) NULL,
 ADD COLUMN height DECIMAL(12,3) NULL,
 ADD COLUMN is_serialized TINYINT(1) NOT NULL DEFAULT 0,
 ADD COLUMN is_featured TINYINT(1) NOT NULL DEFAULT 0,
 ADD COLUMN deleted_at DATETIME(6) NULL,
 ADD KEY idx_products_brand (brand_id),
 ADD KEY idx_products_character (character_id),
 ADD CONSTRAINT fk_products_brand FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE RESTRICT,
 ADD CONSTRAINT fk_products_character FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE RESTRICT;

CREATE TABLE product_images (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 product_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 storage_key VARCHAR(255) NOT NULL UNIQUE,
 mime_type VARCHAR(40) NOT NULL,
 size_bytes INT UNSIGNED NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 KEY idx_images_product (product_id),
 CONSTRAINT fk_images_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
