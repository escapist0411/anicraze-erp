-- purchase_orders table placeholder
CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL,
    order_date DATE NOT NULL,
    total_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'pending'
);
