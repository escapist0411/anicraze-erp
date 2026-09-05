-- products table placeholder
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sku TEXT UNIQUE NOT NULL,
    category_id INTEGER,
    price REAL DEFAULT 0,
    stock_quantity INTEGER DEFAULT 0
);
