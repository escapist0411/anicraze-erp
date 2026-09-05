-- sales table placeholder
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    store_id INTEGER,
    customer_name TEXT,
    total_amount REAL DEFAULT 0
);
