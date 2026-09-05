-- expenses table placeholder
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_date DATE NOT NULL,
    category TEXT,
    amount REAL NOT NULL,
    description TEXT
);
