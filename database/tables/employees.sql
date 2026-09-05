-- employees table placeholder
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    employee_code TEXT UNIQUE NOT NULL,
    department TEXT,
    hire_date DATE
);
